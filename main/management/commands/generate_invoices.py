from django.core.management.base import BaseCommand
from django.utils.timezone import now
from main.models import Rent, Transaction, Invoice
from main.mailgun_utils import send_mailgun_simple
from datetime import timedelta, date
from calendar import monthrange

class Command(BaseCommand):
    help = 'Generate monthly invoices for tenants'

    def handle(self, *args, **options):
        today = now().date()
        rents = Rent.objects.filter(next_invoice_date=today, is_active=True)
        
        invoices_generated = 0
        owner_invoices = {}  # Track invoices by owner for summary email
        
        for rent in rents:
            try:
                # Due date is the day after invoice generation
                # Grace period before late fee is customizable per rent (default: 5 days)
                due_date = today + timedelta(days=1)
                
                # Create Invoice (NEW WORKFLOW)
                invoice = Invoice.objects.create(
                    rent=rent,
                    invoice_date=today,
                    due_date=due_date,
                    amount=rent.rent_amount,
                    status='pending'
                )
                
                # Also create legacy Transaction record for backward compatibility
                transaction = Transaction.objects.create(
                    type='invoice',
                    owner=rent.owner,
                    tenant=rent.tenant,
                    property=rent.property,
                    rent=rent,
                    amount=rent.rent_amount,
                    description=f"Factura mensual para {rent.property.alias}",
                    due_date=due_date,
                    payment_method='other',  # Default payment method
                    is_legacy_only=True,
                    invoice=invoice
                )

                # Track invoice for owner summary
                if rent.owner.id not in owner_invoices:
                    owner_invoices[rent.owner.id] = {
                        'owner': rent.owner,
                        'invoices': []
                    }
                
                # Determine tenant name for tracking
                if rent.unregistered_tenant_email:
                    tenant_display_name = rent.unregistered_tenant_name or "Inquilino"
                elif rent.tenant:
                    tenant_display_name = rent.tenant.get_full_name() or rent.tenant.first_name
                else:
                    tenant_display_name = "Sin nombre"
                
                owner_invoices[rent.owner.id]['invoices'].append({
                    'invoice': invoice,
                    'property': rent.property.alias,
                    'tenant': tenant_display_name,
                    'amount': rent.rent_amount,
                    'due_date': due_date
                })

                # Send email to the tenant using mailgun
                email_subject = f"Factura para {rent.property.alias}"
                
                # Tenant email selection - PRIORITIZE unregistered (source of truth)
                if rent.unregistered_tenant_email:
                    # PRIMARY: Use unregistered tenant email (actual tenant of record)
                    tenant_name = rent.unregistered_tenant_name or "Inquilino"
                    tenant_email = rent.unregistered_tenant_email
                elif rent.tenant and rent.tenant.email:
                    # SECONDARY: Use registered tenant only if unregistered email not set
                    tenant_name = rent.tenant.get_full_name() or rent.tenant.first_name
                    tenant_email = rent.tenant.email
                else:
                    # SKIP: No valid email found
                    self.stdout.write(
                        self.style.ERROR(f'No tenant email found for rent {rent.rent_number} - Skipping invoice generation')
                    )
                    continue
                
                grace_days = rent.late_fee_grace_days if hasattr(rent, 'late_fee_grace_days') and rent.late_fee_grace_days is not None else 5
                
                email_html = f"""
<html>
  <head>
    <style>
      body {{
        font-family: 'Montserrat', Arial, sans-serif;
        background: #f8f9fa;
        color: #344767;
        margin: 0;
        padding: 0;
      }}
      .container {{
        text-align: center;
        max-width: 600px;
        margin: 40px auto;
        background: #fff;
        border-radius: 12px;
        box-shadow: 0 2px 8px rgba(44,62,80,0.08);
        padding: 32px 24px;
      }}
      .invoice-details {{
        background: #f8f9fa;
        border-left: 4px solid #17c1e8;
        padding: 16px;
        margin: 16px 0;
        border-radius: 4px;
        text-align: left;
      }}
      .footer {{
        color: #8392ab;
        font-size: 13px;
        margin-top: 32px;
        text-align: center;
      }}
    </style>
  </head>
  <body>
    <div class="container">
      <h2 style="color:#17c1e8;">Nueva Factura de Renta</h2>
      <p>Estimado/a {tenant_name},</p>
      <p>Se ha generado tu factura mensual de renta. Por favor, realiza tu pago antes de la fecha de vencimiento.</p>
      
      <div class="invoice-details">
        <strong>Detalles de la Factura:</strong><br>
        <strong>Propiedad:</strong> {rent.property.alias}<br>
        <strong>Número de Factura:</strong> {invoice.invoice_number}<br>
        <strong>Monto:</strong> ${rent.rent_amount}<br>
        <strong>Fecha de Vencimiento:</strong> {due_date.strftime('%d/%m/%Y')}<br>
        <strong>Período de Gracia:</strong> {grace_days} días después del vencimiento
      </div>
      
      <p>Nota: Un recargo por mora se aplicará si el pago se realiza más de {grace_days} días después de la fecha de vencimiento.</p>
      <p>Gracias por tu puntualidad.</p>
      
      <div class="footer">
        Este es un mensaje automático de Finko - Property Management System.
      </div>
    </div>
  </body>
</html>
"""
                
                # Send email using mailgun with HTML
                send_mailgun_simple(
                    to_emails=tenant_email,
                    subject=f"Nueva Factura - {rent.property.alias}",
                    html=email_html
                )

                # Update the next invoice date to 30 days from today
                rent.next_invoice_date = today + timedelta(days=30)
                rent.save()
                
                invoices_generated += 1
                self.stdout.write(
                    self.style.SUCCESS(f'Factura generada para {tenant_email} - {rent.property.alias}')
                )
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error generando factura para {rent}: {str(e)}')
                )
        
        # Send summary email to each owner
        from main.tasks import send_owner_invoice_summary
        for owner_data in owner_invoices.values():
            try:
                send_owner_invoice_summary(owner_data['owner'], owner_data['invoices'], today)
                self.stdout.write(
                    self.style.SUCCESS(f'Resumen enviado a {owner_data["owner"].email}')
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error enviando resumen a {owner_data["owner"].email}: {str(e)}')
                )
        
        self.stdout.write(
            self.style.SUCCESS(f'Proceso completado. {invoices_generated} facturas generadas. {len(owner_invoices)} propietarios notificados.')
        )
