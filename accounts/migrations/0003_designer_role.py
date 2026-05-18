from django.db import migrations


def create_designer_role(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    Role.objects.get_or_create(name='设计师', defaults={'description': '负责报价单编制'})


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0002_menu_role_user_roles'),
    ]
    operations = [
        migrations.RunPython(create_designer_role, migrations.RunPython.noop),
    ]
