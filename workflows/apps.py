from django.apps import AppConfig


class WorkflowsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'workflows'

    def ready(self):
        """
        Django 启动时自动加载信号。
        必须在 ready() 里导入，否则信号不会生效。
        """
        import workflows.signals