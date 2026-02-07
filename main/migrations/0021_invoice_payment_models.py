# Generated migration for Invoice and Payment models

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0020_rent_late_fee_amount_rent_late_fee_type'),
    ]

    operations = [
        # Add Invoice model
        migrations.CreateModel(
            name='Invoice',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('invoice_number', models.CharField(editable=False, max_length=100, unique=True)),
                ('invoice_date', models.DateField()),
                ('due_date', models.DateField()),
                ('amount', models.DecimalField(decimal_places=2, max_digits=10)),
                ('paid_amount', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('late_fee_amount', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, default=0)),
                ('late_fee_applied_date', models.DateField(blank=True, null=True)),
                ('status', models.CharField(choices=[('pending', 'Pendiente'), ('partial', 'Parcialmente Pagado'), ('paid', 'Pagado'), ('overdue', 'Vencido'), ('overdue_with_fee', 'Vencido con Recargo')], default='pending', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('rent', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='invoices', to='main.rent')),
            ],
            options={
                'ordering': ['-due_date'],
            },
        ),
        
        # Add Payment model
        migrations.CreateModel(
            name='Payment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount', models.DecimalField(decimal_places=2, max_digits=10)),
                ('payment_date', models.DateField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('payment_method', models.CharField(choices=[('ach_yappy', 'ACH o Yappy'), ('cash', 'Efectivo'), ('other', 'Otros')], max_length=100)),
                ('status', models.CharField(choices=[('pending', 'Pendiente'), ('confirmed', 'Confirmado'), ('rejected', 'Rechazado')], default='pending', max_length=20)),
                ('description', models.TextField(blank=True, max_length=250, null=True)),
                ('invoice', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='payments', to='main.invoice')),
                ('transaction', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='payment_ref', to='main.transaction')),
            ],
            options={
                'ordering': ['-payment_date'],
            },
        ),
        
        # Add fields to Transaction
        migrations.AddField(
            model_name='transaction',
            name='is_legacy_only',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='transaction',
            name='invoice',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='legacy_transactions', to='main.invoice'),
        ),
        migrations.AddField(
            model_name='transaction',
            name='payment',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='transaction_ref', to='main.payment'),
        ),
        
        # Add indexes
        migrations.AddIndex(
            model_name='invoice',
            index=models.Index(fields=['rent', 'due_date'], name='main_invoice_rent_due_idx'),
        ),
        migrations.AddIndex(
            model_name='invoice',
            index=models.Index(fields=['status'], name='main_invoice_status_idx'),
        ),
        migrations.AddIndex(
            model_name='invoice',
            index=models.Index(fields=['invoice_date'], name='main_invoice_date_idx'),
        ),
        migrations.AddIndex(
            model_name='payment',
            index=models.Index(fields=['invoice', 'payment_date'], name='main_payment_invoice_date_idx'),
        ),
        migrations.AddIndex(
            model_name='payment',
            index=models.Index(fields=['status'], name='main_payment_status_idx'),
        ),
    ]
