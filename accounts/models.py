from django.contrib.auth.models import AbstractUser
from django.db import models


ROLE_SALES    = '销售人员'
ROLE_TECH     = '技术人员'
ROLE_BOSS     = '老板'
ROLE_DESIGNER = '设计师'


class Department(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name='部门名称')
    parent = models.ForeignKey(
        'self', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='children', verbose_name='上级部门'
    )
    order = models.IntegerField(default=0, verbose_name='排序')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = '部门'
        verbose_name_plural = '部门'
        ordering = ['order', 'name']

    def __str__(self):
        return self.name


class Position(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name='岗位名称')
    level = models.IntegerField(default=1, verbose_name='岗位级别')

    class Meta:
        verbose_name = '岗位'
        verbose_name_plural = '岗位'

    def __str__(self):
        return self.name


class Menu(models.Model):
    name = models.CharField(max_length=50, verbose_name='菜单名称')
    path = models.CharField(max_length=200, blank=True, verbose_name='路由路径')
    icon = models.CharField(max_length=100, blank=True, verbose_name='图标')
    parent = models.ForeignKey(
        'self', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='children', verbose_name='父菜单'
    )
    order = models.IntegerField(default=0, verbose_name='排序')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')

    class Meta:
        verbose_name = '菜单'
        verbose_name_plural = '菜单'
        ordering = ['order']

    def __str__(self):
        return self.name


class Role(models.Model):
    name = models.CharField(max_length=50, unique=True, verbose_name='角色名称')
    description = models.TextField(blank=True, verbose_name='角色描述')
    menus = models.ManyToManyField(
        Menu, blank=True,
        related_name='roles', verbose_name='菜单权限'
    )
    permissions = models.ManyToManyField(
        'auth.Permission', blank=True,
        related_name='roles', verbose_name='操作权限'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = '角色'
        verbose_name_plural = '角色'

    def __str__(self):
        return self.name


class User(AbstractUser):
    real_name = models.CharField(max_length=50, blank=True, verbose_name='真实姓名')
    phone = models.CharField(max_length=20, blank=True, verbose_name='手机号')
    department = models.ForeignKey(
        Department, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='members', verbose_name='所属部门'
    )
    position = models.ForeignKey(
        Position, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='holders', verbose_name='岗位'
    )
    avatar = models.ImageField(
        upload_to='avatars/%Y/%m/',
        null=True, blank=True, verbose_name='头像'
    )
    roles = models.ManyToManyField(
        Role, blank=True,
        related_name='users', verbose_name='角色'
    )

    class Meta:
        verbose_name = '用户'
        verbose_name_plural = '用户'

    def __str__(self):
        return self.real_name or self.username