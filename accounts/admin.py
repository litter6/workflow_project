from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from .models import User, Department, Position, Menu, Role


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ['name', 'parent', 'order', 'created_at']
    list_editable = ['order']
    search_fields = ['name']
    ordering = ['order', 'name']


@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    list_display = ['name', 'level']
    list_editable = ['level']
    ordering = ['level']


@admin.register(Menu)
class MenuAdmin(admin.ModelAdmin):
    list_display = ['name', 'path', 'parent', 'order', 'is_active']
    list_editable = ['order', 'is_active']
    list_filter = ['is_active', 'parent']
    search_fields = ['name', 'path']
    ordering = ['order']


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ['name', 'description', 'user_count', 'created_at']
    search_fields = ['name']
    filter_horizontal = ['menus', 'permissions']

    def user_count(self, obj):
        return obj.users.count()
    user_count.short_description = '用户数'


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ['username', 'real_name', 'department', 'position', 'role_tags', 'is_active', 'is_staff']
    list_filter = ['department', 'position', 'is_active', 'is_staff', 'roles']
    search_fields = ['username', 'real_name', 'phone']
    list_per_page = 20
    fieldsets = UserAdmin.fieldsets + (
        ('业务信息', {
            'fields': ('real_name', 'phone', 'department', 'position', 'avatar')
        }),
        ('角色权限', {
            'fields': ('roles',)
        }),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('业务信息', {
            'fields': ('real_name', 'phone', 'department', 'position')
        }),
    )
    filter_horizontal = ['roles', 'groups', 'user_permissions']

    def role_tags(self, obj):
        roles = obj.roles.all()
        if not roles:
            return '—'
        return format_html(
            ' '.join(
                f'<span style="background:#dbeafe;color:#1d4ed8;padding:2px 8px;border-radius:4px;font-size:12px;">{r.name}</span>'
                for r in roles
            )
        )
    role_tags.short_description = '角色'
