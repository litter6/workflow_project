from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import ApprovalInstance
from .archive_service import ArchiveService


@receiver(post_save, sender=ApprovalInstance)
def auto_archive_on_approval(sender, instance, **kwargs):
    """
    当审批实例状态变为"已通过"时，自动创建项目并归档文件。
    post_save 信号在每次保存后触发，我们只处理状态变为 approved 的情况。
    """
    if instance.status == ApprovalInstance.STATUS_APPROVED:
        # 检查项目是否已经创建过，避免重复创建
        if not hasattr(instance, 'project'):
            try:
                ArchiveService.create_project_from_instance(instance)
            except Exception as e:
                print(f'归档失败：{e}')