# Generated migration for adding notification preference fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0002_add_role_confirmed'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='notify_invoice_generated',
            field=models.BooleanField(default=True, verbose_name='Notificaciones de Facturas'),
        ),
        migrations.AddField(
            model_name='user',
            name='notify_invoice_summary',
            field=models.BooleanField(default=True, verbose_name='Resumen de Facturas'),
        ),
        migrations.AddField(
            model_name='user',
            name='notify_late_fee_applied',
            field=models.BooleanField(default=True, verbose_name='Alertas de Recargos'),
        ),
        migrations.AddField(
            model_name='user',
            name='notify_payment_confirmed',
            field=models.BooleanField(default=True, verbose_name='Confirmación de Pagos'),
        ),
        migrations.AddField(
            model_name='user',
            name='notify_payment_received',
            field=models.BooleanField(default=True, verbose_name='Pagos Recibidos'),
        ),
        migrations.AddField(
            model_name='user',
            name='notify_lease_renewal',
            field=models.BooleanField(default=True, verbose_name='Renovación de Contrato'),
        ),
        migrations.AddField(
            model_name='user',
            name='notify_maintenance',
            field=models.BooleanField(default=True, verbose_name='Alertas de Mantenimiento'),
        ),
        migrations.AddField(
            model_name='user',
            name='notify_property_alerts',
            field=models.BooleanField(default=True, verbose_name='Alertas de Propiedad'),
        ),
    ]
