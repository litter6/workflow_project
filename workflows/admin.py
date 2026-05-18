from django.contrib import admin
from django.utils.html import format_html
from accounts.models import ROLE_BOSS
from .models import (
    ApprovalProcess, ApprovalProcessNode,
    ApprovalInstance, ApprovalRecord,
    ApprovalAttachment, Project, Document, Notification,
    Quotation, QuotationItem, PriceItem,
)


class ApprovalProcessNodeInline(admin.TabularInline):
    model = ApprovalProcessNode
    extra = 1
    filter_horizontal = ['approvers', 'approver_roles']
    fields = ['order', 'name', 'node_type', 'approvers', 'approver_roles']


@admin.register(ApprovalProcess)
class ApprovalProcessAdmin(admin.ModelAdmin):
    list_display = ['name', 'node_count', 'is_active', 'created_by', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name']
    inlines = [ApprovalProcessNodeInline]

    def node_count(self, obj):
        return obj.nodes.count()
    node_count.short_description = '节点数'


@admin.register(ApprovalInstance)
class ApprovalInstanceAdmin(admin.ModelAdmin):
    list_display = ['title', 'process', 'applicant', 'status_badge', 'current_step', 'created_at']
    list_filter = ['status', 'process', 'created_at']
    search_fields = ['title', 'applicant__username', 'applicant__real_name']
    readonly_fields = ['status', 'current_step', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'
    list_per_page = 20

    def status_badge(self, obj):
        colors = {
            'pending':   ('#fef3c7', '#b45309'),
            'approved':  ('#d1fae5', '#065f46'),
            'rejected':  ('#fee2e2', '#991b1b'),
            'withdrawn': ('#f1f5f9', '#475569'),
        }
        bg, fg = colors.get(obj.status, ('#f1f5f9', '#475569'))
        return format_html(
            '<span style="background:{};color:{};padding:2px 10px;border-radius:5px;font-size:12px;">{}</span>',
            bg, fg, obj.get_status_display()
        )
    status_badge.short_description = '状态'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(applicant=request.user)


@admin.register(ApprovalRecord)
class ApprovalRecordAdmin(admin.ModelAdmin):
    list_display = ['instance', 'step', 'operator', 'action_badge', 'comment_short', 'created_at']
    list_filter = ['action', 'created_at']
    search_fields = ['instance__title', 'operator__username', 'operator__real_name']
    readonly_fields = ['instance', 'step', 'operator', 'action', 'comment', 'created_at']
    date_hierarchy = 'created_at'
    list_per_page = 20

    def action_badge(self, obj):
        colors = {
            'approve':  ('#d1fae5', '#065f46'),
            'reject':   ('#fee2e2', '#991b1b'),
            'transfer': ('#dbeafe', '#1d4ed8'),
            'add':      ('#fef3c7', '#b45309'),
        }
        bg, fg = colors.get(obj.action, ('#f1f5f9', '#475569'))
        return format_html(
            '<span style="background:{};color:{};padding:2px 10px;border-radius:5px;font-size:12px;">{}</span>',
            bg, fg, obj.get_action_display()
        )
    action_badge.short_description = '操作'

    def comment_short(self, obj):
        return (obj.comment[:30] + '…') if len(obj.comment) > 30 else obj.comment or '—'
    comment_short.short_description = '审批意见'


class DocumentInline(admin.TabularInline):
    model = Document
    extra = 0
    readonly_fields = ['name', 'file', 'doc_type', 'version', 'uploaded_by', 'uploaded_at']


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'status_badge', 'created_by', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['name', 'created_by__username']
    readonly_fields = ['folder_path', 'created_at', 'updated_at']
    inlines = [DocumentInline]
    date_hierarchy = 'created_at'
    list_per_page = 20

    def status_badge(self, obj):
        colors = {
            'active':    ('#dbeafe', '#1d4ed8'),
            'completed': ('#d1fae5', '#065f46'),
            'archived':  ('#f1f5f9', '#475569'),
        }
        bg, fg = colors.get(obj.status, ('#f1f5f9', '#475569'))
        return format_html(
            '<span style="background:{};color:{};padding:2px 10px;border-radius:5px;font-size:12px;">{}</span>',
            bg, fg, obj.get_status_display()
        )
    status_badge.short_description = '状态'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(created_by=request.user)


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ['name', 'project', 'doc_type', 'version', 'uploaded_by', 'uploaded_at']
    list_filter = ['doc_type']
    search_fields = ['name', 'project__name']


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['message', 'recipient', 'instance', 'is_read', 'created_at']
    list_filter = ['is_read', 'created_at']
    search_fields = ['recipient__username', 'message']
    readonly_fields = ['recipient', 'instance', 'message', 'created_at']
    list_per_page = 30

    def has_add_permission(self, _request):
        return False


@admin.register(PriceItem)
class PriceItemAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'unit', 'base_price', 'fluctuation', 'price_range', 'is_active', 'updated_at']
    list_filter  = ['category', 'is_active']
    search_fields = ['name', 'spec']
    list_editable = ['is_active']
    list_per_page = 30

    def price_range(self, obj):
        if obj.fluctuation == 0:
            return f'¥{obj.base_price}（固定）'
        return f'¥{obj.min_price} ~ ¥{obj.max_price}'
    price_range.short_description = '允许区间'

    def has_add_permission(self, request):
        return request.user.is_superuser or request.user.roles.filter(name=ROLE_BOSS).exists()

    def has_change_permission(self, request, _obj=None):
        return request.user.is_superuser or request.user.roles.filter(name=ROLE_BOSS).exists()

    def has_delete_permission(self, request, _obj=None):
        return request.user.is_superuser or request.user.roles.filter(name=ROLE_BOSS).exists()


class QuotationItemInline(admin.TabularInline):
    model = QuotationItem
    extra = 0
    fields = ['category', 'name', 'spec', 'unit', 'quantity', 'unit_price', 'total_price', 'notes']
    readonly_fields = ['total_price']


@admin.register(Quotation)
class QuotationAdmin(admin.ModelAdmin):
    list_display = ['quote_no', 'project', 'designer', 'status_badge', 'total_amount', 'discount', 'final_amount', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['quote_no', 'project__name', 'designer__username']
    readonly_fields = ['quote_no', 'total_amount', 'final_amount', 'created_at', 'updated_at']
    inlines = [QuotationItemInline]
    date_hierarchy = 'created_at'
    list_per_page = 20

    def status_badge(self, obj):
        colors = {
            'draft':     ('#f1f5f9', '#475569'),
            'submitted': ('#fef3c7', '#b45309'),
            'approved':  ('#d1fae5', '#065f46'),
            'rejected':  ('#fee2e2', '#991b1b'),
        }
        bg, fg = colors.get(obj.status, ('#f1f5f9', '#475569'))
        return format_html(
            '<span style="background:{};color:{};padding:2px 10px;border-radius:5px;font-size:12px;">{}</span>',
            bg, fg, obj.get_status_display()
        )
    status_badge.short_description = '状态'
