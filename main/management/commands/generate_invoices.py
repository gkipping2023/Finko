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
        
        for rent in rents:
            try:
                # Use a default due date if rent_due_date is None
                rent_due_day = int(rent.rent_due_date or 5)  # Default to the 5th day of the month
                
                # Calculate due date for this month
                try:
                    due_date = date(today.year, today.month, rent_due_day)
                except ValueError:
                    # Handles months with fewer days (e.g., Feb 30)
                    last_day = monthrange(today.year, today.month)[1]
                    due_date = date(today.year, today.month, last_day)
                
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
                
                email_body = f"""
                Estimado/a {tenant_name},

                Su renta mensual de ${rent.rent_amount} vence el día {rent_due_day}.
                Por favor realice su pago puntualmente.

                Detalles de la factura:
                - Propiedad: {rent.property.alias}
                - Número de factura: {invoice.invoice_number}
                - Monto: ${rent.rent_amount}
                - Fecha de vencimiento: {invoice.due_date}
                - Número de transacción: {transaction.transaction_number}

                Gracias por su puntualidad.

                Saludos,
                Equipo Finko
                """
                
                # Send email using mailgun
                send_mailgun_simple(
                    to_emails=tenant_email,
                    subject=email_subject,
                    text=email_body
                )

                # Update the next invoice date
                next_month = today.replace(day=1) + timedelta(days=32)
                rent.next_invoice_date = next_month.replace(day=1)
                rent.save()
                
                invoices_generated += 1
                self.stdout.write(
                    self.style.SUCCESS(f'Factura generada para {tenant_email} - {rent.property.alias}')
                )
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error generando factura para {rent}: {str(e)}')
                )
        
        self.stdout.write(
            self.style.SUCCESS(f'Proceso completado. {invoices_generated} facturas generadas.')
        )
