import json
from decimal import Decimal, InvalidOperation

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from .models import (
    ApprovalProcess, ApprovalInstance, ApprovalAttachment, ApprovalRecord,
    Project, Document, Notification,
    Quotation, QuotationItem, QUOTATION_CATEGORY_CHOICES,
    PriceItem,
)
from .services import ApprovalService
from accounts.models import ROLE_SALES, ROLE_TECH, ROLE_BOSS, ROLE_DESIGNER


def _notify_quotation(recipients, quotation, message):
    for user in recipients:
        Notification.objects.create(
            recipient=user,
            quotation=quotation,
            message=message,
        )


def get_user_roles(user):
    return list(user.roles.values_list('name', flat=True))


def has_role(user, role_name):
    return user.roles.filter(name=role_name).exists()


@login_required
def dashboard(request):
    context = {'page_title': '工作台'}
    roles = get_user_roles(request.user)

    if ROLE_SALES in roles:
        context['my_applied'] = ApprovalService.get_my_applied(request.user)[:5]
        context['role_view'] = 'sales'

    if ROLE_TECH in roles:
        context['my_pending'] = ApprovalService.get_my_pending(request.user)[:5]
        context['role_view'] = 'designer'

    if ROLE_BOSS in roles:
        context['my_pending'] = ApprovalService.get_my_pending(request.user)[:5]
        context['all_instances'] = ApprovalInstance.objects.all().order_by('-created_at')[:10]
        context['role_view'] = 'boss'

    return render(request, 'workflows/dashboard.html', context)


@login_required
def my_pending(request):
    instances = ApprovalService.get_my_pending(request.user)
    q = request.GET.get('q', '').strip()
    if q:
        instances = instances.filter(title__icontains=q)
    return render(request, 'workflows/my_pending.html', {
        'instances': instances,
        'page_title': '我的待办',
        'q': q,
    })


@login_required
def my_applied(request):
    instances = ApprovalService.get_my_applied(request.user)
    q = request.GET.get('q', '').strip()
    status = request.GET.get('status', '')
    if q:
        instances = instances.filter(title__icontains=q)
    if status:
        instances = instances.filter(status=status)
    return render(request, 'workflows/my_applied.html', {
        'instances': instances,
        'page_title': '我发起的',
        'q': q,
        'status_filter': status,
    })


@login_required
def my_handled(request):
    instances = ApprovalService.get_my_handled(request.user)
    q = request.GET.get('q', '').strip()
    status = request.GET.get('status', '')
    if q:
        instances = instances.filter(title__icontains=q)
    if status:
        instances = instances.filter(status=status)
    return render(request, 'workflows/my_handled.html', {
        'instances': instances,
        'page_title': '我已处理的',
        'q': q,
        'status_filter': status,
    })


@login_required
def start_process(request):
    if not has_role(request.user, ROLE_SALES) and not request.user.is_superuser:
        messages.error(request, '只有销售人员可以发起申请')
        return redirect('dashboard')

    processes = ApprovalProcess.objects.filter(is_active=True)

    if request.method == 'POST':
        process_id = request.POST.get('process_id')
        title = request.POST.get('title')
        content = request.POST.get('content', '')
        customer_name = request.POST.get('customer_name', '')
        customer_phone = request.POST.get('customer_phone', '')
        house_address = request.POST.get('house_address', '')

        try:
            instance = ApprovalService.start_process(
                process_id=process_id,
                title=title,
                content={
                    'description': content,
                    'customer_name': customer_name,
                    'customer_phone': customer_phone,
                    'house_address': house_address,
                },
                applicant=request.user
            )
            files = request.FILES.getlist('attachments')
            for f in files:
                if f.size > 50 * 1024 * 1024:
                    messages.error(request, f'文件"{f.name}"超过50MB限制')
                    return redirect('start_process')
                if f.name:
                    ApprovalAttachment.objects.create(
                        instance=instance,
                        file=f,
                        filename=f.name,
                        uploaded_by=request.user
                    )
            messages.success(request, f'客户项目"{instance.title}"已成功提交！')
            return redirect('my_applied')
        except Exception as e:
            messages.error(request, f'提交失败：{str(e)}')

    return render(request, 'workflows/start_process.html', {
        'processes': processes,
        'page_title': '新建客户项目'
    })


@login_required
def withdraw(request, instance_id):
    get_object_or_404(ApprovalInstance, id=instance_id, applicant=request.user)
    if request.method == 'POST':
        try:
            ApprovalService.withdraw(instance_id, request.user)
            messages.success(request, '申请已成功撤回')
        except ValueError as e:
            messages.error(request, str(e))
    return redirect('instance_detail', instance_id=instance_id)


@login_required
def instance_detail(request, instance_id):
    instance = get_object_or_404(ApprovalInstance, id=instance_id)
    roles = get_user_roles(request.user)

    if request.method == 'POST':
        action = request.POST.get('action')
        comment = request.POST.get('comment', '')

        try:
            files = request.FILES.getlist('attachments')

            if action == 'approve':
                ApprovalService.approve(instance.id, request.user, comment)
                messages.success(request, '已通过，进入下一环节！')
            elif action == 'reject':
                ApprovalService.reject(instance.id, request.user, comment)
                messages.success(request, '已驳回！')

            approval_record = ApprovalRecord.objects.filter(
                instance=instance,
                operator=request.user
            ).order_by('-created_at').first()

            for f in files:
                if f.size > 50 * 1024 * 1024:
                    messages.error(request, f'文件"{f.name}"超过50MB限制')
                    break
                if f.name:
                    ApprovalAttachment.objects.create(
                        instance=instance,
                        record=approval_record,
                        file=f,
                        filename=f.name,
                        uploaded_by=request.user
                    )
            return redirect('my_pending')
        except Exception as e:
            messages.error(request, f'操作失败：{str(e)}')

    records = instance.records.all()
    attachments = instance.attachments.all()

    records_with_attachments = []
    for record in records:
        records_with_attachments.append({
            'record': record,
            'attachments': record.attachments.all()
        })

    initial_attachments = attachments.filter(record__isnull=True)

    already_handled = ApprovalRecord.objects.filter(
        instance=instance, operator=request.user
    ).exists()

    current_node = instance.process.nodes.filter(order=instance.current_step).first()
    is_current_approver = False
    if current_node and instance.applicant != request.user:
        is_current_approver = current_node.approvers.filter(id=request.user.id).exists()

    return render(request, 'workflows/instance_detail.html', {
        'instance': instance,
        'records': records,
        'records_with_attachments': records_with_attachments,
        'initial_attachments': initial_attachments,
        'attachments': attachments,
        'roles': roles,
        'already_handled': already_handled,
        'is_current_approver': is_current_approver,
        'page_title': instance.title
    })


@login_required
def file_manager(request, instance_id):
    instance = get_object_or_404(ApprovalInstance, id=instance_id)
    nodes = list(instance.process.nodes.all().order_by('order'))

    folders = []
    folders.append({
        'label': '提交附件',
        'step': 0,
        'files': instance.attachments.filter(record__isnull=True).select_related('uploaded_by'),
    })
    for node in nodes:
        folders.append({
            'label': f'第{node.order}步 — {node.name}',
            'step': node.order,
            'files': instance.attachments.filter(record__step=node.order).select_related('uploaded_by'),
        })

    return render(request, 'workflows/file_manager.html', {
        'instance': instance,
        'folders': folders,
        'page_title': f'文件管理 — {instance.title}',
    })


@login_required
def notifications(request):
    notif_list = Notification.objects.filter(recipient=request.user).select_related('instance')
    notif_list.filter(is_read=False).update(is_read=True)
    return render(request, 'workflows/notifications.html', {
        'notifications': notif_list,
        'page_title': '我的通知',
    })


@login_required
def project_list(request):
    if (has_role(request.user, ROLE_BOSS)
            or has_role(request.user, ROLE_DESIGNER)
            or request.user.is_superuser):
        projects = Project.objects.all().select_related('approval_instance', 'created_by')
    else:
        projects = Project.objects.filter(
            created_by=request.user
        ).select_related('approval_instance')

    return render(request, 'workflows/project_list.html', {
        'projects': projects,
        'page_title': '项目列表'
    })


@login_required
def project_detail(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    documents = project.documents.all()
    quotations = project.quotations.select_related('designer').all()
    can_create_quotation = has_role(request.user, ROLE_DESIGNER) or request.user.is_superuser
    return render(request, 'workflows/project_detail.html', {
        'project': project,
        'documents': documents,
        'quotations': quotations,
        'can_create_quotation': can_create_quotation,
        'page_title': project.name
    })


# ── 报价单 ─────────────────────────────────────────────────

@login_required
def quotation_list(request):
    if has_role(request.user, ROLE_BOSS) or request.user.is_superuser:
        qs = Quotation.objects.all()
    else:
        qs = Quotation.objects.filter(designer=request.user)

    qs = qs.select_related('project', 'designer')

    q = request.GET.get('q', '').strip()
    status = request.GET.get('status', '')
    if q:
        qs = qs.filter(Q(quote_no__icontains=q) | Q(project__name__icontains=q))
    if status:
        qs = qs.filter(status=status)

    return render(request, 'workflows/quotation_list.html', {
        'quotations': qs,
        'q': q,
        'status_filter': status,
        'page_title': '报价管理',
    })


@login_required
def quotation_create(request, project_id):
    if not (has_role(request.user, ROLE_DESIGNER) or request.user.is_superuser):
        messages.error(request, '只有设计师才能创建报价单')
        return redirect('project_detail', project_id)
    project = get_object_or_404(Project, id=project_id)
    if request.method == 'POST':
        construction_period = request.POST.get('construction_period', '').strip()
        warranty_period = request.POST.get('warranty_period', '').strip()
        notes = request.POST.get('notes', '').strip()
        quotation = Quotation.objects.create(
            project=project,
            designer=request.user,
            construction_period=construction_period or None,
            warranty_period=warranty_period or None,
            notes=notes,
        )
        messages.success(request, f'报价单 {quotation.quote_no} 已创建，请继续填写报价明细')
        return redirect('quotation_detail', quotation.id)
    return render(request, 'workflows/quotation_new.html', {
        'project': project,
        'page_title': '新建报价单',
    })


@login_required
def quotation_detail(request, quotation_id):
    quotation   = get_object_or_404(Quotation, id=quotation_id)
    is_designer = has_role(request.user, ROLE_DESIGNER) or request.user.is_superuser
    can_edit    = (quotation.status == Quotation.STATUS_DRAFT
                   and quotation.designer == request.user
                   and is_designer)
    is_approver    = has_role(request.user, ROLE_BOSS) or request.user.is_superuser
    can_do_approve = is_approver and quotation.status == Quotation.STATUS_SUBMITTED
    can_do_reset   = is_approver and quotation.status in (Quotation.STATUS_SUBMITTED, Quotation.STATUS_REJECTED)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action in ('save', 'submit') and can_edit:
            cp = request.POST.get('construction_period', '').strip()
            wp = request.POST.get('warranty_period', '').strip()
            quotation.construction_period = int(cp) if cp.isdigit() else None
            quotation.warranty_period = int(wp) if wp.isdigit() else None
            try:
                quotation.discount = Decimal(request.POST.get('discount', '100'))
            except InvalidOperation:
                quotation.discount = Decimal('100')
            quotation.notes = request.POST.get('notes', '')

            try:
                items_data = json.loads(request.POST.get('items_json', '[]'))
            except (json.JSONDecodeError, ValueError):
                items_data = []

            # 服务端价格区间校验
            pi_cache: dict = {}
            for item in items_data:
                pid = item.get('price_item_id')
                if not pid:
                    messages.error(request, f'项目"{item.get("name","")}"未从价格表选择，请重新操作')
                    return redirect('quotation_detail', quotation.id)
                if pid not in pi_cache:
                    try:
                        pi_cache[pid] = PriceItem.objects.get(id=pid, is_active=True)
                    except PriceItem.DoesNotExist:
                        messages.error(request, '所选价格项目已失效，请重新选择')
                        return redirect('quotation_detail', quotation.id)
                pi = pi_cache[pid]
                try:
                    unit_price = Decimal(str(item.get('unit_price', '0')))
                except InvalidOperation:
                    unit_price = Decimal('0')
                if unit_price < pi.min_price or unit_price > pi.max_price:
                    messages.error(
                        request,
                        f'"{pi.name}" 单价 ¥{unit_price} 超出允许范围 ¥{pi.min_price} ~ ¥{pi.max_price}'
                    )
                    return redirect('quotation_detail', quotation.id)

            quotation.items.all().delete()
            total = Decimal('0.00')
            for i, item in enumerate(items_data):
                try:
                    qty      = Decimal(str(item.get('quantity', '0')))
                    price    = Decimal(str(item.get('unit_price', '0')))
                    subtotal = (qty * price).quantize(Decimal('0.01'))
                    total   += subtotal
                    QuotationItem.objects.create(
                        quotation=quotation,
                        price_item_id=item.get('price_item_id'),
                        category=item.get('category', 'other'),
                        name=str(item.get('name', '')),
                        spec=str(item.get('spec', '')),
                        unit=str(item.get('unit', '项')),
                        quantity=qty,
                        unit_price=price,
                        total_price=subtotal,
                        notes=str(item.get('notes', '')),
                        sort_order=i,
                    )
                except (InvalidOperation, ValueError, TypeError):
                    continue

            quotation.total_amount = total
            quotation.final_amount = (total * quotation.discount / Decimal('100')).quantize(Decimal('0.01'))
            if action == 'submit':
                quotation.status = Quotation.STATUS_SUBMITTED
                quotation.save()
                User = get_user_model()
                boss_users = list(User.objects.filter(roles__name=ROLE_BOSS))
                _notify_quotation(
                    boss_users, quotation,
                    f'设计师 {request.user} 提交了报价单 {quotation.quote_no}，请审批'
                )
                messages.success(request, '报价单已提交，等待老板审批')
            else:
                quotation.save()
                messages.success(request, '草稿已保存')
            return redirect('quotation_detail', quotation.id)

        elif action == 'approve' and can_do_approve:
            quotation.status = Quotation.STATUS_APPROVED
            quotation.save()
            if quotation.designer:
                _notify_quotation(
                    [quotation.designer], quotation,
                    f'您的报价单 {quotation.quote_no} 已审批通过'
                )
            messages.success(request, '报价单已审批通过')
            return redirect('quotation_detail', quotation.id)

        elif action == 'reject' and can_do_approve:
            reject_reason = request.POST.get('reject_reason', '').strip()
            quotation.status = Quotation.STATUS_REJECTED
            quotation.reject_reason = reject_reason
            quotation.save()
            if quotation.designer:
                _notify_quotation(
                    [quotation.designer], quotation,
                    f'您的报价单 {quotation.quote_no} 已被驳回'
                    + (f'：{reject_reason}' if reject_reason else '')
                )
            messages.success(request, '报价单已驳回')
            return redirect('quotation_detail', quotation.id)

        elif action == 'reset' and can_do_reset:
            quotation.status = Quotation.STATUS_DRAFT
            quotation.save()
            messages.success(request, '报价单已退回草稿，可重新编辑')
            return redirect('quotation_detail', quotation.id)

    items = list(quotation.items.select_related('price_item').all())

    cat_labels = dict(QUOTATION_CATEGORY_CHOICES)
    cat_order  = [c[0] for c in QUOTATION_CATEGORY_CHOICES]
    seen: dict = {}
    for item in items:
        cat = item.category
        if cat not in seen:
            seen[cat] = {'label': cat_labels.get(cat, cat), 'items': [], 'subtotal': Decimal('0.00')}
        seen[cat]['items'].append(item)
        seen[cat]['subtotal'] += item.total_price
    items_grouped = [seen[c] for c in cat_order if c in seen]
    items_grouped += [g for c, g in seen.items() if c not in cat_order]

    items_list = [{
        'price_item_id': i.price_item_id,
        'category':    i.category,
        'name':        i.name,
        'spec':        i.spec,
        'unit':        i.unit,
        'quantity':    str(i.quantity),
        'unit_price':  str(i.unit_price),
        'total_price': str(i.total_price),
        'notes':       i.notes,
        'min_price':   str(i.price_item.min_price) if i.price_item else '',
        'max_price':   str(i.price_item.max_price) if i.price_item else '',
    } for i in items]

    price_items_qs = PriceItem.objects.filter(is_active=True).order_by('category', 'name')
    price_items_data = [{
        'id':          pi.id,
        'category':    pi.category,
        'name':        pi.name,
        'spec':        pi.spec,
        'unit':        pi.unit,
        'base_price':  str(pi.base_price),
        'min_price':   str(pi.min_price),
        'max_price':   str(pi.max_price),
        'fluctuation': str(pi.fluctuation),
    } for pi in price_items_qs]

    return render(request, 'workflows/quotation_detail.html', {
        'quotation':        quotation,
        'items_grouped':    items_grouped,
        'items_list':       items_list,
        'cat_choices':      list(QUOTATION_CATEGORY_CHOICES),
        'price_items_data': price_items_data,
        'can_edit':         can_edit,
        'can_do_approve':   can_do_approve,
        'can_do_reset':     can_do_reset,
        'page_title':       f'报价单 {quotation.quote_no}',
    })


# ── 价格表管理 ──────────────────────────────────────────────

def _require_boss(request):
    return has_role(request.user, ROLE_BOSS) or request.user.is_superuser


@login_required
def price_list(request):
    q          = request.GET.get('q', '').strip()
    cat_filter = request.GET.get('cat', '')
    qs = PriceItem.objects.all()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(spec__icontains=q))
    if cat_filter:
        qs = qs.filter(category=cat_filter)

    cat_labels = dict(QUOTATION_CATEGORY_CHOICES)
    seen: dict = {}
    for pi in qs:
        cat = pi.category
        if cat not in seen:
            seen[cat] = {'label': cat_labels.get(cat, cat), 'items': []}
        seen[cat]['items'].append(pi)
    cat_order = [c[0] for c in QUOTATION_CATEGORY_CHOICES]
    grouped = [seen[c] for c in cat_order if c in seen]
    grouped += [g for c, g in seen.items() if c not in cat_order]

    price_items_raw = [{
        'id': pi.id, 'category': pi.category, 'name': pi.name,
        'spec': pi.spec, 'unit': pi.unit,
        'base_price': str(pi.base_price), 'fluctuation': str(pi.fluctuation),
        'is_active': pi.is_active,
    } for pi in qs]

    return render(request, 'workflows/price_list.html', {
        'grouped':         grouped,
        'price_items_raw': price_items_raw,
        'cat_choices':     QUOTATION_CATEGORY_CHOICES,
        'q':               q,
        'cat_filter':      cat_filter,
        'can_manage':      _require_boss(request),
        'page_title':      '价格表管理',
    })


@login_required
def price_item_save(request):
    if not _require_boss(request):
        messages.error(request, '只有老板才能编辑价格表')
        return redirect('price_list')
    if request.method != 'POST':
        return redirect('price_list')

    pk = request.POST.get('pk', '').strip()
    try:
        base = Decimal(request.POST.get('base_price', '0'))
        fluc = Decimal(request.POST.get('fluctuation', '0'))
    except InvalidOperation:
        messages.error(request, '价格或浮动范围格式错误')
        return redirect('price_list')

    data = {
        'category':    request.POST.get('category', 'other'),
        'name':        request.POST.get('name', '').strip(),
        'spec':        request.POST.get('spec', '').strip(),
        'unit':        request.POST.get('unit', '项').strip(),
        'base_price':  base,
        'fluctuation': fluc,
        'is_active':   request.POST.get('is_active') == '1',
    }
    if not data['name']:
        messages.error(request, '项目名称不能为空')
        return redirect('price_list')

    if pk:
        PriceItem.objects.filter(id=pk).update(**data)
        messages.success(request, '价格项目已更新')
    else:
        PriceItem.objects.create(**data, created_by=request.user)
        messages.success(request, '价格项目已添加')
    return redirect('price_list')


@login_required
def price_item_delete(request, pk):
    if not _require_boss(request):
        messages.error(request, '只有老板才能删除价格项目')
        return redirect('price_list')
    if request.method == 'POST':
        PriceItem.objects.filter(id=pk).delete()
        messages.success(request, '价格项目已删除')
    return redirect('price_list')


# ── 报表 ─────────────────────────────────────────────────────

@login_required
def reports(request):
    from django.db.models import Sum, Count
    from django.db.models.functions import TruncMonth
    from datetime import date, timedelta

    is_boss = has_role(request.user, ROLE_BOSS) or request.user.is_superuser

    # ── 1. 项目统计 ──────────────────────────────────────────
    project_status_map = {'active': '进行中', 'completed': '已完成', 'archived': '已归档'}
    project_by_status = list(
        Project.objects.values('status').annotate(count=Count('id'))
    )
    for row in project_by_status:
        row['label'] = project_status_map.get(row['status'], row['status'])

    six_months_ago = date.today().replace(day=1) - timedelta(days=150)
    projects_monthly_qs = (
        Project.objects.filter(created_at__gte=six_months_ago)
        .annotate(month=TruncMonth('created_at'))
        .values('month')
        .annotate(count=Count('id'))
        .order_by('month')
    )
    projects_monthly = [
        {'month': r['month'].strftime('%Y-%m'), 'count': r['count']}
        for r in projects_monthly_qs
    ]

    # ── 2. 报价统计 ──────────────────────────────────────────
    q_status_map = {
        'draft': '草稿', 'submitted': '待审批',
        'approved': '已审批', 'rejected': '已驳回',
    }
    quotation_by_status = list(
        Quotation.objects.values('status')
        .annotate(count=Count('id'), total=Sum('final_amount'))
    )
    for row in quotation_by_status:
        row['label'] = q_status_map.get(row['status'], row['status'])
        row['total'] = row['total'] or Decimal('0.00')

    approved_total = sum(
        r['total'] for r in quotation_by_status if r['status'] == 'approved'
    ) or Decimal('0.00')

    designer_stats = list(
        Quotation.objects.filter(status='approved')
        .values('designer__username', 'designer__real_name')
        .annotate(count=Count('id'), total=Sum('final_amount'))
        .order_by('-total')
    )
    for row in designer_stats:
        row['name'] = row['designer__real_name'] or row['designer__username'] or '—'

    # ── 3. 价格表使用分析 ────────────────────────────────────
    cat_label_map = dict(QUOTATION_CATEGORY_CHOICES)
    hot_items = list(
        QuotationItem.objects.filter(price_item__isnull=False)
        .values('price_item__id', 'price_item__name', 'price_item__category')
        .annotate(usage_count=Count('id'), total_qty=Sum('quantity'))
        .order_by('-usage_count')[:10]
    )
    for row in hot_items:
        row['cat_label'] = cat_label_map.get(row['price_item__category'], row['price_item__category'])

    # ── 4. 报价明细分类汇总 ──────────────────────────────────
    category_summary = list(
        QuotationItem.objects.filter(quotation__status='approved')
        .values('category')
        .annotate(subtotal=Sum('total_price'), item_count=Count('id'))
        .order_by('-subtotal')
    )
    for row in category_summary:
        row['label'] = cat_label_map.get(row['category'], row['category'])
    category_total = sum(r['subtotal'] for r in category_summary) or Decimal('0.00')

    return render(request, 'workflows/reports.html', {
        'page_title': '报表统计',
        'is_boss': is_boss,
        'project_by_status':   project_by_status,
        'projects_monthly':    json.dumps(projects_monthly),
        'quotation_by_status': quotation_by_status,
        'approved_total':      approved_total,
        'designer_stats':      designer_stats,
        'hot_items':           hot_items,
        'category_summary':    category_summary,
        'category_total':      category_total,
    })
