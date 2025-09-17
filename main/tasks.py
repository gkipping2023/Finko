from celery import shared_task
from django.utils.timezone import now
from .models import Rent, Transaction
from django.core.mail import send_mail
from datetime import timedelta

@shared_task
def generate_invoices():
    today = now().date()
    rents = Rent.objects.filter(next_invoice_date=today)

    for rent in rents:
        # Use a default due date if rent_due_date is None
        rent_due_day = int(rent.rent_due_date or 5)  # Default to the 5th day of the month
        # Create an invoice transaction
        Transaction.objects.create(
            type='invoice',
            owner=rent.owner,
            tenant=rent.tenant,
            property=rent.property,
            rent=rent,
            amount=rent.rent_amount,
            description=f"Monthly rent for {rent.property.alias}",
            due_date=today.replace(day=rent_due_day),
        )

        # Send email to the tenant
        send_mail(
            subject=f"Invoice for {rent.property.alias}",
            message=f"Dear {rent.tenant.full_name},\n\nYour monthly rent of ${rent.rent_amount} is due on {rent.rent_due_date}. Please make your payment promptly.\n\nThank you.",
            from_email='noreply@rentu.com',
            recipient_list=[rent.tenant.email],
        )

        # Update the next invoice date
        rent.next_invoice_date = today.replace(day=1) + timedelta(days=32)
        rent.next_invoice_date = rent.next_invoice_date.replace(day=rent.rent_due_date)
        rent.save()

