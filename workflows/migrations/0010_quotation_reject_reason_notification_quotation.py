from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('workflows', '0009_price_item'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='quotation',
            name='reject_reason',
            field=models.TextField(blank=True, verbose_name='驳回原因'),
        ),
        migrations.AlterField(
            model_name='notification',
            name='instance',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='notifications',
                to='workflows.approvalinstance',
                verbose_name='关联申请',
            ),
        ),
        migrations.AddField(
            model_name='notification',
            name='quotation',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='notifications',
                to='workflows.quotation',
                verbose_name='关联报价单',
            ),
        ),
    ]
