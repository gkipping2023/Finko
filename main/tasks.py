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
    rents = Rent.objects.filter(next_invoice_date=today, is_active=True)

    # Track generated invoices by owner for summary email
    owner_invoices = {}

    for rent in rents:
        # Due date is the day after invoice generation
        # This gives tenant 5 days to pay before late fee on 6th day past due
        due_date = today + timedelta(days=1)
        
        # Create Invoice (NEW WORKFLOW)
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
            transaction_date=today,
            invoice=invoice,
            is_legacy_only=False
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
            
            send_mailgun_simple(
                subject=f"Nueva Factura - {rent.property.alias}",
                html=email_html,
                to_emails=tenant_email,
                from_email=settings.DEFAULT_FROM_EMAIL
            )
        except Exception as e:
            logger.error(f"Failed to send invoice email to {tenant_email}: {e}")

        # Update the next invoice date to 30 days from today
        rent.next_invoice_date = today + timedelta(days=30)
        rent.save()
    
    # Send summary email to each owner
    for owner_data in owner_invoices.values():
        try:
            send_owner_invoice_summary(owner_data['owner'], owner_data['invoices'], today)
        except Exception as e:
            logger.error(f"Failed to send invoice summary to owner {owner_data['owner'].email}: {e}")
    
    return {
        'status': 'success',
        'total_invoices': sum(len(data['invoices']) for data in owner_invoices.values()),
        'owners_notified': len(owner_invoices),
        'timestamp': str(today)
    }

@shared_task
def apply_late_fees():
    """
    Check for overdue invoices and apply late fees if configured.
    Late fees are applied when invoice is 6+ days past due.
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
        
        # Get the grace period from the rent (default 5 if not set)
        grace_days = rent.late_fee_grace_days if hasattr(rent, 'late_fee_grace_days') and rent.late_fee_grace_days is not None else 5
        
        # Check if invoice is past the grace period
        # Grace period of 5 means late fee applies on 6th day past due
        days_overdue = invoice.get_days_overdue()
        if days_overdue <= grace_days:
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


def send_owner_invoice_summary(owner, invoices, generation_date):
    """Send summary email to owner about generated invoices"""
    from main.mailgun_utils import send_mailgun_simple
    from django.conf import settings
    
    total_amount = sum(inv['amount'] for inv in invoices)
    invoice_count = len(invoices)
    
    # Build invoice rows HTML
    invoice_rows = ""
    for inv_data in invoices:
        invoice_rows += f"""
        <tr style="border-bottom: 1px solid #e9ecef;">
          <td style="padding: 12px 8px;">
            <strong style="color: #344767;">{inv_data['invoice'].invoice_number}</strong>
          </td>
          <td style="padding: 12px 8px; color: #67748e;">{inv_data['property']}</td>
          <td style="padding: 12px 8px; color: #67748e;">{inv_data['tenant']}</td>
          <td style="padding: 12px 8px; color: #344767; font-weight: 600;">
            ${inv_data['amount']:.2f}
          </td>
          <td style="padding: 12px 8px; color: #67748e;">
            {inv_data['due_date'].strftime('%d/%m/%Y')}
          </td>
        </tr>
        """
    
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
            max-width: 700px;
            margin: 40px auto;
            background: #fff;
            border-radius: 12px;
            box-shadow: 0 2px 8px rgba(44,62,80,0.08);
            padding: 32px 24px;
          }}
          .header {{
            text-align: center;
            margin-bottom: 24px;
          }}
          .summary-box {{
            background: linear-gradient(195deg, #17c1e8 0%, #1a73e8 100%);
            border-radius: 8px;
            padding: 20px;
            margin: 20px 0;
            color: #fff;
            text-align: center;
          }}
          .summary-stat {{
            display: inline-block;
            margin: 0 20px;
          }}
          .summary-label {{
            font-size: 12px;
            opacity: 0.8;
            display: block;
            margin-bottom: 4px;
          }}
          .summary-value {{
            font-size: 24px;
            font-weight: 700;
          }}
          table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
          }}
          th {{
            background: #f8f9fa;
            color: #67748e;
            font-weight: 600;
            font-size: 12px;
            text-transform: uppercase;
            padding: 12px 8px;
            text-align: left;
            border-bottom: 2px solid #e9ecef;
          }}
          .footer {{
            color: #8392ab;
            font-size: 13px;
            margin-top: 32px;
            text-align: center;
            padding-top: 20px;
            border-top: 1px solid #e9ecef;
          }}
        </style>
      </head>
      <body>
        <div class="container">
          <div class="header">
            <h2 style="color:#17c1e8; margin: 0;">Resumen de Facturas Generadas</h2>
            <p style="color: #67748e; margin: 8px 0 0 0;">
              {generation_date.strftime('%d de %B, %Y')}
            </p>
          </div>
          
          <div class="summary-box">
            <div class="summary-stat">
              <span class="summary-label">Total de Facturas</span>
              <span class="summary-value">{invoice_count}</span>
            </div>
            <div class="summary-stat">
              <span class="summary-label">Monto Total Esperado</span>
              <span class="summary-value">${total_amount:.2f}</span>
            </div>
          </div>
          
          <p style="color: #344767; margin: 20px 0;">
            Estimado/a {owner.get_full_name() if hasattr(owner, 'get_full_name') else owner.full_name},
          </p>
          <p style="color: #67748e; line-height: 1.6;">
            Se han generado y enviado las siguientes facturas de renta a tus inquilinos:
          </p>
          
          <table>
            <thead>
              <tr>
                <th>Número de Factura</th>
                <th>Propiedad</th>
                <th>Inquilino</th>
                <th>Monto</th>
                <th>Vencimiento</th>
              </tr>
            </thead>
            <tbody>
              {invoice_rows}
            </tbody>
          </table>
          
          <p style="color: #67748e; line-height: 1.6; margin-top: 24px;">
            Las facturas han sido enviadas automáticamente a los inquilinos. 
            Puedes revisar el estado de los pagos en tu panel de control.
          </p>
          
          <div style="text-align: center; margin-top: 24px;">
            <a href="{settings.SITE_URL if hasattr(settings, 'SITE_URL') else 'https://finko.com'}/properties" 
               style="display: inline-block; background: linear-gradient(195deg, #17c1e8 0%, #1a73e8 100%); 
                      color: #fff; padding: 12px 32px; border-radius: 6px; 
                      text-decoration: none; font-weight: 600;">
              Ver Panel de Control
            </a>
          </div>
          
          <div class="footer">
            Este es un mensaje automático de Finko - Property Management System.
          </div>
        </div>
      </body>
    </html>
    """
    
    send_mailgun_simple(
        subject=f"Resumen de Facturas - {invoice_count} factura{'s' if invoice_count != 1 else ''} generada{'s' if invoice_count != 1 else ''}",
        html=email_html,
        to_emails=owner.email,
        from_email=settings.DEFAULT_FROM_EMAIL
    )


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


