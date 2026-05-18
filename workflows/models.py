import os
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone


def attachment_upload_path(att, filename):
    """按审批实例和步骤分文件夹存储附件"""
    ai = att.instance
    if att.record_id is None:
        folder = '0_提交附件'
    else:
        step = att.record.step
        node = ai.process.nodes.filter(order=step).first()
        node_name = node.name if node else f'步骤{step}'
        folder = f'{step}_{node_name}'
    return f'projects/{ai.id}/{folder}/{filename}'

USER_MODEL = settings.AUTH_USER_MODEL


class ApprovalProcess(models.Model):
    name = models.CharField(max_length=100, verbose_name='流程名称')
    description = models.TextField(blank=True, verbose_name='流程说明')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    created_by = models.ForeignKey(
        USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='created_processes',
        verbose_name='创建人'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = '审批流程模板'
        verbose_name_plural = '审批流程模板'

    def __str__(self):
        return self.name


class ApprovalProcessNode(models.Model):
    TYPE_APPROVE = 'approve'
    TYPE_COUNTERSIGN = 'countersign'
    TYPE_CHOICES = [
        (TYPE_APPROVE, '或签'),
        (TYPE_COUNTERSIGN, '会签'),
    ]

    process = models.ForeignKey(
        ApprovalProcess, on_delete=models.CASCADE,
        related_name='nodes', verbose_name='所属流程'
    )
    name = models.CharField(max_length=50, verbose_name='节点名称')
    approvers = models.ManyToManyField(
        USER_MODEL, related_name='approval_nodes',
        verbose_name='审批人'
    )
    approver_roles = models.ManyToManyField(
        'accounts.Role',
        blank=True,
        related_name='approval_nodes',
        verbose_name='审批角色'
    )
    node_type = models.CharField(
        max_length=20, choices=TYPE_CHOICES,
        default=TYPE_APPROVE, verbose_name='审批类型'
    )
    order = models.IntegerField(default=1, verbose_name='审批顺序')

    class Meta:
        verbose_name = '流程节点定义'
        verbose_name_plural = '流程节点定义'
        ordering = ['order']

    def __str__(self):
        return f'{self.process.name} - {self.name}'


class ApprovalInstance(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_WITHDRAWN = 'withdrawn'
    STATUS_CHOICES = [
        (STATUS_PENDING, '审批中'),
        (STATUS_APPROVED, '已通过'),
        (STATUS_REJECTED, '已驳回'),
        (STATUS_WITHDRAWN, '已撤回'),
    ]

    process = models.ForeignKey(
        ApprovalProcess, on_delete=models.PROTECT,
        related_name='instances', verbose_name='流程模板'
    )
    title = models.CharField(max_length=200, verbose_name='申请标题')
    content = models.JSONField(default=dict, verbose_name='申请内容')
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES,
        default=STATUS_PENDING, verbose_name='状态'
    )
    current_step = models.IntegerField(default=1, verbose_name='当前步骤')
    applicant = models.ForeignKey(
        USER_MODEL, on_delete=models.PROTECT,
        related_name='applied_instances', verbose_name='申请人'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = '审批实例'
        verbose_name_plural = '审批实例'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.title} - {self.get_status_display()}'


class ApprovalRecord(models.Model):
    ACTION_APPROVE = 'approve'
    ACTION_REJECT = 'reject'
    ACTION_TRANSFER = 'transfer'
    ACTION_ADD = 'add'
    ACTION_CHOICES = [
        (ACTION_APPROVE, '同意'),
        (ACTION_REJECT, '驳回'),
        (ACTION_TRANSFER, '转交'),
        (ACTION_ADD, '加签'),
    ]

    instance = models.ForeignKey(
        ApprovalInstance, on_delete=models.CASCADE,
        related_name='records', verbose_name='审批实例'
    )
    step = models.IntegerField(verbose_name='审批步骤')
    operator = models.ForeignKey(
        USER_MODEL, on_delete=models.PROTECT,
        related_name='approval_records', verbose_name='操作人'
    )
    action = models.CharField(
        max_length=20, choices=ACTION_CHOICES,
        verbose_name='操作'
    )
    comment = models.TextField(blank=True, verbose_name='审批意见')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = '审批记录'
        verbose_name_plural = '审批记录'
        ordering = ['created_at']

    def __str__(self):
        return f'{self.instance.title} - {self.operator} - {self.get_action_display()}'


class ApprovalAttachment(models.Model):
    instance = models.ForeignKey(
        ApprovalInstance, on_delete=models.CASCADE,
        related_name='attachments', verbose_name='审批实例'
    )
    # 关联到具体的审批记录，方便在审批历史中显示对应附件
    record = models.ForeignKey(
        'ApprovalRecord', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='attachments', verbose_name='关联审批记录'
    )
    file = models.FileField(
        upload_to=attachment_upload_path,
        null=True, blank=True,
        verbose_name='附件'
    )
    filename = models.CharField(max_length=255, blank=True, verbose_name='文件名')
    uploaded_by = models.ForeignKey(
        USER_MODEL, on_delete=models.PROTECT,
        null=True, blank=True,
        related_name='uploaded_attachments', verbose_name='上传人'
    )
    uploaded_at = models.DateTimeField(auto_now_add=True, null=True)

    class Meta:
        verbose_name = '审批附件'
        verbose_name_plural = '审批附件'

    def __str__(self):
        return self.filename


class Project(models.Model):
    STATUS_ACTIVE = 'active'
    STATUS_COMPLETED = 'completed'
    STATUS_ARCHIVED = 'archived'
    STATUS_CHOICES = [
        (STATUS_ACTIVE, '进行中'),
        (STATUS_COMPLETED, '已完成'),
        (STATUS_ARCHIVED, '已归档'),
    ]

    name = models.CharField(max_length=200, verbose_name='项目名称')
    approval_instance = models.OneToOneField(
        ApprovalInstance, on_delete=models.PROTECT,
        related_name='project', verbose_name='关联审批'
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES,
        default=STATUS_ACTIVE, verbose_name='项目状态'
    )
    folder_path = models.CharField(max_length=500, blank=True, verbose_name='文件夹路径')
    created_by = models.ForeignKey(
        USER_MODEL, on_delete=models.PROTECT,
        related_name='created_projects', verbose_name='创建人'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = '项目'
        verbose_name_plural = '项目'
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class Document(models.Model):
    TYPE_CONTRACT = 'contract'
    TYPE_ATTACHMENT = 'attachment'
    TYPE_REPORT = 'report'
    TYPE_OTHER = 'other'
    TYPE_CHOICES = [
        (TYPE_CONTRACT, '合同'),
        (TYPE_ATTACHMENT, '附件'),
        (TYPE_REPORT, '报告'),
        (TYPE_OTHER, '其他'),
    ]

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE,
        related_name='documents', verbose_name='所属项目'
    )
    name = models.CharField(max_length=200, verbose_name='文档名称')
    file = models.FileField(
        upload_to='temp/',
        verbose_name='文件'
    )
    doc_type = models.CharField(
        max_length=20, choices=TYPE_CHOICES,
        default=TYPE_ATTACHMENT, verbose_name='文档类型'
    )
    version = models.IntegerField(default=1, verbose_name='版本号')
    uploaded_by = models.ForeignKey(
        USER_MODEL, on_delete=models.PROTECT,
        related_name='uploaded_documents', verbose_name='上传人'
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = '文档'
        verbose_name_plural = '文档'
        ordering = ['-uploaded_at']

    def __str__(self):
        return f'{self.name} v{self.version}'


class Notification(models.Model):
    recipient = models.ForeignKey(
        USER_MODEL, on_delete=models.CASCADE,
        related_name='notifications', verbose_name='接收人'
    )
    instance = models.ForeignKey(
        ApprovalInstance, on_delete=models.CASCADE,
        related_name='notifications', verbose_name='关联申请',
        null=True, blank=True
    )
    quotation = models.ForeignKey(
        'Quotation', on_delete=models.CASCADE,
        related_name='notifications', verbose_name='关联报价单',
        null=True, blank=True
    )
    message = models.CharField(max_length=255, verbose_name='消息内容')
    is_read = models.BooleanField(default=False, verbose_name='已读')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = '站内通知'
        verbose_name_plural = '站内通知'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.recipient} - {self.message}'


class PriceItem(models.Model):
    """价格表：由老板维护的标准报价项目，含允许浮动范围"""
    category    = models.CharField(max_length=32, verbose_name='分类')
    name        = models.CharField(max_length=200, verbose_name='项目名称')
    spec        = models.CharField(max_length=200, blank=True, verbose_name='规格说明')
    unit        = models.CharField(max_length=16, default='项', verbose_name='单位')
    base_price  = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='基准价格(元)')
    fluctuation = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.00'),
        verbose_name='浮动范围(%)', help_text='0 = 固定价格；10 = 允许上下浮动 10%'
    )
    is_active   = models.BooleanField(default=True, verbose_name='是否启用')
    created_by  = models.ForeignKey(
        USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name='created_price_items', verbose_name='创建人'
    )
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    @property
    def min_price(self):
        return (self.base_price * (Decimal('1') - self.fluctuation / Decimal('100'))).quantize(Decimal('0.01'))

    @property
    def max_price(self):
        return (self.base_price * (Decimal('1') + self.fluctuation / Decimal('100'))).quantize(Decimal('0.01'))

    class Meta:
        verbose_name = '价格项目'
        verbose_name_plural = '价格表'
        ordering = ['category', 'name']

    def __str__(self):
        return f'{self.name}（{self.unit}）¥{self.base_price}'


QUOTATION_CATEGORY_CHOICES = [
    ('design',        '设计费'),
    ('demolition',    '拆除工程'),
    ('water_electric','水电工程'),
    ('tiling',        '瓦工工程'),
    ('carpentry',     '木工工程'),
    ('painting',      '油漆工程'),
    ('main_material', '主材'),
    ('soft_furnishing','软装'),
    ('other',         '其他'),
]


class Quotation(models.Model):
    STATUS_DRAFT     = 'draft'
    STATUS_SUBMITTED = 'submitted'
    STATUS_APPROVED  = 'approved'
    STATUS_REJECTED  = 'rejected'
    STATUS_CHOICES = [
        ('draft',     '草稿'),
        ('submitted', '已提交'),
        ('approved',  '已审批'),
        ('rejected',  '已驳回'),
    ]

    project = models.ForeignKey(
        'Project', on_delete=models.CASCADE,
        related_name='quotations', verbose_name='关联项目'
    )
    quote_no = models.CharField(max_length=32, unique=True, editable=False, verbose_name='报价单号')
    designer = models.ForeignKey(
        USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='quotations_created', verbose_name='创建人'
    )
    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES,
        default=STATUS_DRAFT, verbose_name='状态'
    )
    total_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name='总金额(元)'
    )
    discount = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('100.00'), verbose_name='折扣(%)'
    )
    final_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name='成交金额(元)'
    )
    construction_period = models.PositiveIntegerField(null=True, blank=True, verbose_name='施工周期(天)')
    warranty_period     = models.PositiveIntegerField(null=True, blank=True, verbose_name='质保期(年)')
    notes = models.TextField(blank=True, verbose_name='备注说明')
    reject_reason = models.TextField(blank=True, verbose_name='驳回原因')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True,     verbose_name='更新时间')

    class Meta:
        verbose_name = '报价单'
        verbose_name_plural = '报价单'
        ordering = ['-created_at']

    def __str__(self):
        return self.quote_no

    def save(self, *args, **kwargs):
        if not self.quote_no:
            today = timezone.now().strftime('%Y%m%d')
            count = Quotation.objects.filter(quote_no__startswith=f'QT{today}').count()
            self.quote_no = f'QT{today}{count + 1:04d}'
        super().save(*args, **kwargs)


class QuotationItem(models.Model):
    quotation = models.ForeignKey(
        Quotation, on_delete=models.CASCADE,
        related_name='items', verbose_name='报价单'
    )
    price_item = models.ForeignKey(
        PriceItem, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='quotation_items', verbose_name='参照价格项目'
    )
    category = models.CharField(
        max_length=32, choices=QUOTATION_CATEGORY_CHOICES,
        default='other', verbose_name='分类'
    )
    name       = models.CharField(max_length=200, verbose_name='项目名称')
    spec       = models.CharField(max_length=200, blank=True, verbose_name='规格说明')
    unit       = models.CharField(max_length=16, default='项', verbose_name='单位')
    quantity   = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('1.00'), verbose_name='数量')
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name='单价(元)')
    total_price= models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name='小计(元)')
    notes      = models.CharField(max_length=500, blank=True, verbose_name='备注')
    sort_order = models.PositiveIntegerField(default=0, verbose_name='排序')

    class Meta:
        verbose_name = '报价明细'
        verbose_name_plural = '报价明细'
        ordering = ['category', 'sort_order', 'id']

    def __str__(self):
        return f'{self.quotation.quote_no} - {self.name}'