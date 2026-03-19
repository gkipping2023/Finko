# main/services.py
from decimal import Decimal
from datetime import date
from django.db.models import Sum, Q, F
from .models import Invoice, Payment, Rent


class RentAccountStatus:
    """
    Comprehensive rental account status calculation.
    Replaces get_days_past_due() with proper invoice-level tracking.
    """
    
    def __init__(self, rent):
        self.rent = rent
        self.today = date.today()
    
    def get_status(self):
        """
        Returns comprehensive status dict:
        {
            'is_past_due': bool,
            'days_past_due': int,
            'balance_owed': Decimal,
            'total_invoiced': Decimal,
            'total_paid': Decimal,
            'status': str ('good', 'partial', 'late', 'overdue_with_fee'),
            'next_due_date': date or None,
            'next_due_amount': Decimal,
            'late_fee_info': dict or None,
        }
        """
        invoices = self.rent.invoices.all()
        transactions = self.rent.transactions.all()
        
        if not invoices.exists() and not transactions.exists():
            return self._get_no_invoice_status()
        
        # Get all invoices and their status
        total_invoiced = invoices.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')
        
        total_paid = invoices.aggregate(
            total=Sum('paid_amount')
        )['total'] or Decimal('0.00')
        
        total_late_fees = invoices.aggregate(
            total=Sum('late_fee_amount')
        )['total'] or Decimal('0.00')
        
        # Sum transaction amounts (charges increase balance, payments decrease it)
        # Only count CONFIRMED transactions to avoid including pending payments
        # Charge transactions: invoice, fee, debit (only confirmed)
        charge_transactions = transactions.filter(
            type__in=['invoice', 'fee', 'debit'],
            status='confirmed'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        # Payment transactions: receipt, credit, pago (only confirmed)
        # These must be confirmed by owner before reducing balance
        payment_transactions = transactions.filter(
            type__in=['receipt', 'credit', 'pago'],
            status='confirmed'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        balance_owed = total_invoiced - total_paid + (total_late_fees or Decimal('0.00')) + charge_transactions - payment_transactions
        
        # Get most recent overdue invoice
        overdue_invoices = invoices.filter(
            due_date__lt=self.today,
            paid_amount__lt=F('amount')
        ).order_by('due_date')
        
        days_past_due = 0
        if overdue_invoices.exists():
            oldest_overdue = overdue_invoices.first()
            days_past_due = (self.today - oldest_overdue.due_date).days
        
        # Determine status
        status = self._determine_status(invoices, total_paid, total_invoiced, total_late_fees)
        
        # Get next invoice due
        next_invoice = invoices.filter(
            due_date__gte=self.today,
            status__in=['pending', 'partial']
        ).order_by('due_date').first()
        
        next_due_date = next_invoice.due_date if next_invoice else None
        next_due_amount = (next_invoice.amount - next_invoice.paid_amount) if next_invoice else Decimal('0.00')
        
        return {
            'is_past_due': days_past_due > 0,
            'days_past_due': days_past_due,
            'balance_owed': max(balance_owed, Decimal('0.00')),
            'total_invoiced': total_invoiced,
            'total_paid': total_paid,
            'total_late_fees': total_late_fees or Decimal('0.00'),
            'status': status,
            'next_due_date': next_due_date,
            'next_due_amount': next_due_amount,
            'late_fee_info': self._get_late_fee_info(invoices),
        }
    
    def _get_no_invoice_status(self):
        """Status when no invoices exist yet"""
        return {
            'is_past_due': False,
            'days_past_due': 0,
            'balance_owed': Decimal('0.00'),
            'total_invoiced': Decimal('0.00'),
            'total_paid': Decimal('0.00'),
            'total_late_fees': Decimal('0.00'),
            'status': 'good',
            'next_due_date': None,
            'next_due_amount': Decimal('0.00'),
            'late_fee_info': None,
        }
    
    def _determine_status(self, invoices, total_paid, total_invoiced, total_late_fees):
        """Determine overall account status"""
        from django.db.models import F
        
        balance_owed = total_invoiced - total_paid + (total_late_fees or Decimal('0.00'))
        
        # No balance owed = good
        if balance_owed <= 0:
            return 'good'
        
        # Check if any invoice has late fee
        has_late_fee = invoices.filter(
            late_fee_amount__gt=0
        ).exists()
        
        if has_late_fee:
            return 'overdue_with_fee'
        
        # Check if any invoice is overdue
        has_overdue = invoices.filter(
            due_date__lt=self.today,
            paid_amount__lt=F('amount')
        ).exists()
        
        if has_overdue:
            return 'late'
        
        # Check if any invoice is partial
        has_partial = invoices.filter(
            paid_amount__gt=0,
            paid_amount__lt=F('amount')
        ).exists()
        
        if has_partial:
            return 'partial'
        
        return 'good'
    
    def _get_late_fee_info(self, invoices):
        """Get information about applied late fees"""
        invoices_with_fees = invoices.filter(
            late_fee_amount__gt=0,
            late_fee_applied_date__isnull=False
        )
        
        if not invoices_with_fees.exists():
            return None
        
        return {
            'count': invoices_with_fees.count(),
            'total_fees': invoices_with_fees.aggregate(
                total=Sum('late_fee_amount')
            )['total'] or Decimal('0.00'),
            'earliest_applied': invoices_with_fees.order_by(
                'late_fee_applied_date'
            ).first().late_fee_applied_date,
        }
