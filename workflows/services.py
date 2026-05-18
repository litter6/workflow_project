from django.db import transaction
from django.db.models import Exists, OuterRef
from .models import ApprovalProcess, ApprovalProcessNode, ApprovalInstance, ApprovalRecord, Notification


class ApprovalService:

    @staticmethod
    def _notify(recipients, instance, message):
        for user in recipients:
            Notification.objects.create(
                recipient=user,
                instance=instance,
                message=message,
            )

    @staticmethod
    @transaction.atomic
    def start_process(process_id, title, content, applicant):
        process = ApprovalProcess.objects.get(id=process_id, is_active=True)
        instance = ApprovalInstance.objects.create(
            process=process,
            title=title,
            content=content,
            applicant=applicant,
            status=ApprovalInstance.STATUS_PENDING,
            current_step=1
        )
        first_node = process.nodes.filter(order=1).first()
        if first_node:
            approvers = list(first_node.approvers.all())
            ApprovalService._notify(
                approvers, instance,
                f'您有新的待审批申请：{title}'
            )
        return instance

    @staticmethod
    @transaction.atomic
    def approve(instance_id, operator, comment=''):
        instance = ApprovalInstance.objects.get(id=instance_id)

        if instance.status != ApprovalInstance.STATUS_PENDING:
            raise ValueError('该流程已结束，无法操作')

        ApprovalRecord.objects.create(
            instance=instance,
            step=instance.current_step,
            operator=operator,
            action=ApprovalRecord.ACTION_APPROVE,
            comment=comment
        )

        current_node = instance.process.nodes.filter(order=instance.current_step).first()

        # 会签：所有审批人都同意才推进
        if current_node and current_node.node_type == ApprovalProcessNode.TYPE_COUNTERSIGN:
            required_approvers = set(current_node.approvers.values_list('id', flat=True))
            approved_operators = set(
                ApprovalRecord.objects.filter(
                    instance=instance,
                    step=instance.current_step,
                    action=ApprovalRecord.ACTION_APPROVE,
                ).values_list('operator_id', flat=True)
            )
            if not required_approvers.issubset(approved_operators):
                return instance

        next_node = instance.process.nodes.filter(order=instance.current_step + 1).first()

        if next_node:
            instance.current_step += 1
            instance.save()
            approvers = list(next_node.approvers.all())
            ApprovalService._notify(
                approvers, instance,
                f'申请「{instance.title}」已流转至您，请及时处理'
            )
        else:
            instance.status = ApprovalInstance.STATUS_APPROVED
            instance.save()
            ApprovalService._notify(
                [instance.applicant], instance,
                f'您的申请「{instance.title}」已审批通过'
            )

        return instance

    @staticmethod
    @transaction.atomic
    def reject(instance_id, operator, comment=''):
        instance = ApprovalInstance.objects.get(id=instance_id)

        if instance.status != ApprovalInstance.STATUS_PENDING:
            raise ValueError('该流程已结束，无法操作')

        ApprovalRecord.objects.create(
            instance=instance,
            step=instance.current_step,
            operator=operator,
            action=ApprovalRecord.ACTION_REJECT,
            comment=comment
        )
        instance.status = ApprovalInstance.STATUS_REJECTED
        instance.save()

        ApprovalService._notify(
            [instance.applicant], instance,
            f'您的申请「{instance.title}」已被驳回'
        )
        return instance

    @staticmethod
    @transaction.atomic
    def withdraw(instance_id, operator):
        instance = ApprovalInstance.objects.get(id=instance_id, applicant=operator)
        if instance.status != ApprovalInstance.STATUS_PENDING:
            raise ValueError('只有审批中的申请可以撤回')
        ApprovalRecord.objects.create(
            instance=instance,
            step=instance.current_step,
            operator=operator,
            action=ApprovalRecord.ACTION_REJECT,
            comment='申请人主动撤回'
        )
        instance.status = ApprovalInstance.STATUS_WITHDRAWN
        instance.save()
        return instance

    @staticmethod
    def get_my_pending(user):
        node_at_current_step = ApprovalProcessNode.objects.filter(
            process=OuterRef('process'),
            order=OuterRef('current_step'),
            approvers=user,
        )
        return ApprovalInstance.objects.filter(
            status=ApprovalInstance.STATUS_PENDING,
        ).exclude(
            applicant=user,
        ).filter(
            Exists(node_at_current_step),
        ).select_related('process', 'applicant')

    @staticmethod
    def get_my_applied(user):
        return ApprovalInstance.objects.filter(
            applicant=user
        ).select_related('process')

    @staticmethod
    def get_my_handled(user):
        handled_ids = ApprovalRecord.objects.filter(
            operator=user
        ).values_list('instance_id', flat=True).distinct()
        return ApprovalInstance.objects.filter(
            id__in=handled_ids
        ).select_related('process', 'applicant')
