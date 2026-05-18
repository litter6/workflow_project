import os
import shutil
from django.conf import settings
from django.utils import timezone
from .models import ApprovalInstance, Project, Document, ApprovalAttachment


class ArchiveService:

    @staticmethod
    def create_project_from_instance(instance):
        """
        审批通过后自动创建项目并归档文件。
        1. 创建项目记录
        2. 创建项目文件夹
        3. 把审批附件归档到项目文件夹
        """
        # 按年份和项目名创建文件夹路径
        year = timezone.now().strftime('%Y')
        # 清理项目名中的特殊字符，避免文件夹名称非法
        safe_name = "".join(
            c for c in instance.title if c.isalnum() or c in (' ', '-', '_')
        ).strip()
        folder_name = f'{safe_name}-{instance.id}'
        folder_path = os.path.join('projects', year, folder_name)

        # 在磁盘上创建文件夹结构
        full_path = os.path.join(settings.MEDIA_ROOT, folder_path)
        os.makedirs(os.path.join(full_path, '附件'), exist_ok=True)
        os.makedirs(os.path.join(full_path, '合同'), exist_ok=True)
        os.makedirs(os.path.join(full_path, '报告'), exist_ok=True)

        # 创建项目记录
        project = Project.objects.create(
            name=instance.title,
            approval_instance=instance,
            folder_path=folder_path,
            created_by=instance.applicant
        )

        # 把审批附件归档到项目文件夹
        attachments = ApprovalAttachment.objects.filter(instance=instance)
        for attachment in attachments:
            if attachment.file:
                ArchiveService.archive_attachment(attachment, project)

        return project

    @staticmethod
    def archive_attachment(attachment, project):
        """
        把审批附件移动到项目文件夹并创建文档记录。
        """
        if not attachment.file:
            return

        # 目标路径：项目文件夹/附件/文件名
        target_dir = os.path.join(
            settings.MEDIA_ROOT,
            project.folder_path,
            '附件'
        )
        filename = attachment.filename or os.path.basename(attachment.file.name)
        target_path = os.path.join(target_dir, filename)

        # 如果目标文件已存在，加上序号避免覆盖
        if os.path.exists(target_path):
            base, ext = os.path.splitext(filename)
            counter = 1
            while os.path.exists(target_path):
                target_path = os.path.join(target_dir, f'{base}_{counter}{ext}')
                counter += 1

        # 复制文件到项目文件夹
        source_path = os.path.join(settings.MEDIA_ROOT, attachment.file.name)
        if os.path.exists(source_path):
            shutil.copy2(source_path, target_path)

        # 创建文档记录，路径相对于 MEDIA_ROOT
        relative_path = os.path.relpath(target_path, settings.MEDIA_ROOT)
        Document.objects.create(
            project=project,
            name=filename,
            file=relative_path.replace('\\', '/'),  # Windows路径转换
            doc_type=Document.TYPE_ATTACHMENT,
            uploaded_by=attachment.uploaded_by or project.created_by
        )