from django.core.management.base import BaseCommand
from django.utils.timezone import now
from main.models import Rent, Transaction
from main.mailgun_utils import send_mailgun_simple
from datetime import timedelta

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
                
                # Create an invoice transaction
                transaction = Transaction.objects.create(
                    type='invoice',
                    owner=rent.owner,
                    tenant=rent.tenant,
                    property=rent.property,
                    rent=rent,
                    amount=rent.rent_amount,
                    description=f"Factura mensual para {rent.property.alias}",
                    due_date=today.replace(day=rent_due_day),
                    payment_method='other'  # Default payment method
                )

                # Send email to the tenant using mailgun
                email_subject = f"Factura para {rent.property.alias}"
                email_body = f"""
                Estimado/a {rent.tenant.first_name} {rent.tenant.last_name},

                Su renta mensual de ${rent.rent_amount} vence el día {rent_due_day}.
                Por favor realice su pago puntualmente.

                Detalles de la factura:
                - Propiedad: {rent.property.alias}
                - Monto: ${rent.rent_amount}
                - Fecha de vencimiento: {transaction.due_date}
                - Número de transacción: {transaction.transaction_number}

                Gracias por su puntualidad.

                Saludos,
                Equipo Rentu
                """
                
                # Send email using mailgun
                send_mailgun_simple(
                    to_emails=rent.tenant.email,
                    subject=email_subject,
                    text=email_body
                )

                # Update the next invoice date
                next_month = today.replace(day=1) + timedelta(days=32)
                rent.next_invoice_date = next_month.replace(day=1)
                rent.save()
                
                invoices_generated += 1
                self.stdout.write(
                    self.style.SUCCESS(f'Factura generada para {rent.tenant.email} - {rent.property.alias}')
                )
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error generando factura para {rent.tenant.email}: {str(e)}')
                )
        
        self.stdout.write(
            self.style.SUCCESS(f'Proceso completado. {invoices_generated} facturas generadas.')
        )