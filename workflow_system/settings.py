from pathlib import Path
from dotenv import load_dotenv
import os

# 基础路径与环境变量
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

SECRET_KEY = os.getenv('SECRET_KEY')
DEBUG = os.getenv('DEBUG', 'False') == 'True'
ALLOWED_HOSTS = ['*']

# 应用注册
INSTALLED_APPS = [
    'simpleui',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'django_filters',
    'guardian',
    'accounts',
    'workflows',
]

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'guardian.backends.ObjectPermissionBackend',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'accounts.views.admin_guard',
]

ROOT_URLCONF = 'workflow_system.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'workflows.context_processors.notifications',
            ],
        },
    },
]

WSGI_APPLICATION = 'workflow_system.wsgi.application'

# 数据库配置
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.getenv('DB_NAME'),
        'USER': os.getenv('DB_USER'),
        'PASSWORD': os.getenv('DB_PASSWORD'),
        'HOST': os.getenv('DB_HOST', '127.0.0.1'),
        'PORT': os.getenv('DB_PORT', '3306'),
        'OPTIONS': {
            'charset': 'utf8mb4',
        },
    }
}

# 自定义用户模型
AUTH_USER_MODEL = 'accounts.User'

# 国际化
LANGUAGE_CODE = 'zh-hans'
TIME_ZONE = 'Asia/Shanghai'
USE_I18N = True
USE_TZ = False

# 静态文件与媒体文件
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# DRF配置
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}

# 允许上传最大 50MB 的文件
DATA_UPLOAD_MAX_MEMORY_SIZE = 52428800  # 50MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 52428800  # 50MB
# 用户进行登录
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'

# ── SimpleUI 管理后台配置 ──────────────────────────────────
SIMPLEUI_LOGO = None
SIMPLEUI_HOME_INFO = False        # 关闭首页版本信息
SIMPLEUI_ANALYSIS = False         # 关闭使用分析上报
SIMPLEUI_DEFAULT_THEME = 'admin.lte.css'
SIMPLEUI_HOME_QUICK = True        # 首页快捷操作
SIMPLEUI_HOME_ACTION = True       # 首页最近动作

SIMPLEUI_CONFIG = {
    'system_keep': False,
    'menu_display': ['组织管理', '工作流管理'],
    'dynamic': True,
    'menus': [
        {
            'name': '组织管理',
            'icon': 'fa fa-sitemap',
            'models': [
                {'name': '用户管理',   'url': 'accounts/user/',       'icon': 'fa fa-user-circle'},
                {'name': '部门管理',   'url': 'accounts/department/', 'icon': 'fa fa-building'},
                {'name': '岗位管理',   'url': 'accounts/position/',   'icon': 'fa fa-id-badge'},
                {'name': '角色管理',   'url': 'accounts/role/',       'icon': 'fa fa-shield'},
                {'name': '菜单管理',   'url': 'accounts/menu/',       'icon': 'fa fa-bars'},
            ],
        },
        {
            'name': '工作流管理',
            'icon': 'fa fa-tasks',
            'models': [
                {'name': '审批流程模板', 'url': 'workflows/approvalprocess/',  'icon': 'fa fa-code-branch'},
                {'name': '审批实例',    'url': 'workflows/approvalinstance/', 'icon': 'fa fa-file-alt'},
                {'name': '审批记录',    'url': 'workflows/approvalrecord/',   'icon': 'fa fa-history'},
                {'name': '项目管理',    'url': 'workflows/project/',          'icon': 'fa fa-folder-open'},
                {'name': '报价管理',    'url': 'workflows/quotation/',        'icon': 'fa fa-file-invoice-dollar'},
                {'name': '站内通知',    'url': 'workflows/notification/',     'icon': 'fa fa-bell'},
            ],
        },
    ],
}