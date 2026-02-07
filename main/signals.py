# main/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db.models import Sum, F
from decimal import Decimal
from .models import Payment, Invoice


@receiver(post_save, sender=Payment)
def update_invoice_on_payment(sender, instance, created, **kwargs):
    """
    When a Payment is confirmed, update the Invoice status automatically.
    """
    if instance.status == 'confirmed':
        invoice = instance.invoice
        
        # Recalculate total paid
        total_paid = invoice.payments.filter(
            status='confirmed'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        invoice.paid_amount = total_paid
        
        # Update status
        if total_paid >= invoice.amount:
            invoice.status = 'paid'
        elif total_paid > 0:
            invoice.status = 'partial'
        else:
            if invoice.late_fee_amount:
                invoice.status = 'overdue_with_fee'
            elif invoice.is_past_due():
                invoice.status = 'overdue'
            else:
                invoice.status = 'pending'
        
        invoice.save()
