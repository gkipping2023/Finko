from celery import shared_task
from django.utils.timezone import now
from .models import Rent, Transaction, Invoice
from .mailgun_utils import send_mailgun_simple
from datetime import timedelta, date
from decimal import Decimal
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


@shared_task
def generate_invoices():
    today = now().date()
    rents = Rent.objects.filter(next_invoice_date=today)

    for rent in rents:
        # Use a default due date if rent_due_date is None
        rent_due_day = int(rent.rent_due_date or 5)  # Default to the 5th day of the month
        
        # Calculate due date
        try:
            due_date = today.replace(day=rent_due_day)
        except ValueError:
            # Handle months with fewer days (e.g., Feb 30)
            from calendar import monthrange
            last_day = monthrange(today.year, today.month)[1]
            due_date = today.replace(day=last_day)
        
        # Create Invoice (NEW WORKFLOW) ← This was missing!
        invoice = Invoice.objects.create(
            rent=rent,
            invoice_date=today,
            due_date=due_date,
            amount=rent.rent_amount,
            status='pending'
        )
        
        # Create Transaction for backward compatibility
        Transaction.objects.create(
            type='invoice',
            owner=rent.owner,
            tenant=rent.tenant,
            property=rent.property,
            rent=rent,
            amount=rent.rent_amount,
            description=f"Monthly rent for {rent.property.alias}",
            due_date=due_date,
            invoice=invoice,
            is_legacy_only=False
        )

        # Determine tenant email and name - PRIORITIZE unregistered tenant
        if rent.unregistered_tenant_email:
            # PRIMARY: Use unregistered tenant (actual tenant of record)
            tenant_name = rent.unregistered_tenant_name or "Inquilino"
            tenant_email = rent.unregistered_tenant_email
        elif rent.tenant and rent.tenant.email:
            # SECONDARY: Use registered tenant as fallback
            tenant_name = rent.tenant.get_full_name() or rent.tenant.first_name
            tenant_email = rent.tenant.email
        else:
            # SKIP: No valid email found
            continue
        
        # Send email to the tenant via Mailgun
        try:
            email_body = f"""Dear {tenant_name},

Your monthly rent of ${rent.rent_amount} is due on {due_date}. Please make your payment promptly.

Invoice Details:
- Property: {rent.property.alias}
- Amount: ${rent.rent_amount}
- Due Date: {due_date}

Thank you.
Finko Team"""
            
            send_mailgun_simple(
                subject=f"Invoice for {rent.property.alias}",
                text=email_body,
                to_emails=tenant_email,
                from_email=settings.DEFAULT_FROM_EMAIL
            )
        except Exception as e:
            logger.error(f"Failed to send invoice email to {tenant_email}: {e}")

        # Update the next invoice date properly
        next_month = today.replace(day=1) + timedelta(days=32)
        rent.next_invoice_date = next_month.replace(day=1)
        rent.save()

@shared_task
def apply_late_fees():
    """
    Check for overdue invoices and apply late fees if configured.
    Should run daily (e.g., 12:01 AM).
    """
    today = now().date()
    
    # Get all overdue invoices without late fees
    overdue_invoices = Invoice.objects.filter(
        due_date__lt=today,
        late_fee_amount=Decimal('0.00'),
        status__in=['pending', 'overdue', 'partial']
    )
    
    fees_applied = 0
    
    for invoice in overdue_invoices:
        rent = invoice.rent
        
        # Skip if no late fee configured
        if rent.late_fee_type == 'none':
            continue
        
        # Calculate late fee (reuse existing method)
        late_fee = rent.get_late_fee()
        
        if late_fee > Decimal('0.00'):
            invoice.late_fee_amount = late_fee
            invoice.late_fee_applied_date = today
            
            # Update status to reflect late fee
            if invoice.paid_amount >= invoice.amount:
                invoice.status = 'overdue_with_fee'
            else:
                invoice.status = 'overdue_with_fee'
            
            invoice.save()
            fees_applied += 1
            
            # Send notification to owner
            try:
                send_late_fee_notification(invoice)
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Failed to send late fee notification: {e}")
    
    return {
        'status': 'success',
        'fees_applied': fees_applied,
        'timestamp': str(today)
    }


def send_late_fee_notification(invoice):
    """Send email to owner about applied late fee"""
    from main.mailgun_utils import send_mailgun_simple
    from django.conf import settings
    
    rent = invoice.rent
    owner = rent.owner
    
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
          .alert {{
            background: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 16px;
            margin: 16px 0;
            border-radius: 4px;
          }}
        </style>
      </head>
      <body>
        <div class="container">
          <h2 style="color:#ffc107;">Recargo de Mora Aplicado</h2>
          <p>Se ha aplicado un recargo de mora a la siguiente factura:</p>
          
          <div class="alert">
            <strong>Factura:</strong> {invoice.invoice_number}<br>
            <strong>Propiedad:</strong> {rent.property.alias}<br>
            <strong>Inquilino:</strong> {rent.tenant.full_name if rent.tenant else rent.unregistered_tenant_name}<br>
            <strong>Monto Original:</strong> ${round(invoice.amount, 2)}<br>
            <strong>Recargo de Mora:</strong> ${invoice.late_fee_amount}<br>
            <strong>Total Adeudado:</strong> ${round(invoice.amount + invoice.late_fee_amount),2}
          </div>
          
          <p>Días de retraso: {invoice.get_days_overdue()}</p>
          <p>Puedes revisar los detalles en tu panel de control.</p>
        </div>
      </body>
    </html>
    """
    
    send_mailgun_simple(
        subject=f"Recargo de Mora Aplicado - {invoice.invoice_number}",
        html=email_html,
        to_emails=owner.email,
        from_email=settings.DEFAULT_FROM_EMAIL
    )


