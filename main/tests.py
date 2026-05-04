from decimal import Decimal
from datetime import date, timedelta

from django.test import TestCase, Client
from django.urls import reverse

from .models import User, Properties, Rent, Invoice, Payment, Credit, Debit
from .services import RentAccountStatus


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def make_owner(**kw):
    defaults = dict(email='owner@test.com', role='O', first_name='Ana', last_name='Owner')
    defaults.update(kw)
    u = User(**defaults)
    u.set_password('pass123')
    u.save()
    return u


def make_tenant(**kw):
    defaults = dict(email='tenant@test.com', role='T', first_name='Juan', last_name='Tenant')
    defaults.update(kw)
    u = User(**defaults)
    u.set_password('pass123')
    u.save()
    return u


def make_property(owner, **kw):
    defaults = dict(
        owner=owner, alias='Apt 1', location='Calle 1',
        category='residential', bedrooms=2, bathrooms=1,
        description='Test property',
    )
    defaults.update(kw)
    return Properties.objects.create(**defaults)


def make_rent(owner, prop, tenant=None, **kw):
    defaults = dict(
        owner=owner, property=prop, tenant=tenant,
        rent_amount=Decimal('500.00'), rent_due_date=1,
        start_date=date.today() - timedelta(days=30),
        end_date=date.today() + timedelta(days=335),
        is_active=True,
    )
    defaults.update(kw)
    return Rent.objects.create(**defaults)


def make_invoice(rent, **kw):
    defaults = dict(
        rent=rent,
        invoice_date=date.today(),
        due_date=date.today() + timedelta(days=5),
        amount=Decimal('500.00'),
        status='pending',
    )
    defaults.update(kw)
    return Invoice.objects.create(**defaults)


# ─────────────────────────────────────────────
# Model Tests
# ─────────────────────────────────────────────

class InvoiceNumberingTest(TestCase):
    def setUp(self):
        self.owner = make_owner()
        self.prop = make_property(self.owner)
        self.rent = make_rent(self.owner, self.prop)

    def test_invoice_number_auto_generated(self):
        inv = make_invoice(self.rent)
        self.assertRegex(inv.invoice_number, r'^INV-\d+-\d{6}-\d+$')

    def test_invoice_numbers_are_sequential(self):
        inv1 = make_invoice(self.rent)
        inv2 = make_invoice(self.rent)
        seq1 = int(inv1.invoice_number.split('-')[3])
        seq2 = int(inv2.invoice_number.split('-')[3])
        self.assertEqual(seq2, seq1 + 1)

    def test_invoice_get_balance_owed(self):
        inv = make_invoice(self.rent, amount=Decimal('500.00'), paid_amount=Decimal('200.00'))
        self.assertEqual(inv.get_balance_owed(), Decimal('300.00'))

    def test_invoice_get_balance_owed_with_late_fee(self):
        inv = make_invoice(
            self.rent,
            amount=Decimal('500.00'),
            paid_amount=Decimal('0.00'),
            late_fee_amount=Decimal('50.00'),
        )
        self.assertEqual(inv.get_balance_owed(), Decimal('550.00'))


class PaymentNumberingTest(TestCase):
    def setUp(self):
        self.owner = make_owner()
        self.prop = make_property(self.owner)
        self.rent = make_rent(self.owner, self.prop)
        self.inv = make_invoice(self.rent)

    def test_payment_number_auto_generated(self):
        p = Payment.objects.create(
            invoice=self.inv, amount=Decimal('500.00'),
            payment_date=date.today(), payment_method='cash', status='confirmed',
        )
        self.assertRegex(p.payment_number, r'^PAY-\d+-\d+$')

    def test_payment_numbers_are_sequential(self):
        p1 = Payment.objects.create(
            invoice=self.inv, amount=Decimal('200.00'),
            payment_date=date.today(), payment_method='cash', status='confirmed',
        )
        p2 = Payment.objects.create(
            invoice=self.inv, amount=Decimal('100.00'),
            payment_date=date.today(), payment_method='cash', status='confirmed',
        )
        seq1 = int(p1.payment_number.split('-')[2])
        seq2 = int(p2.payment_number.split('-')[2])
        self.assertEqual(seq2, seq1 + 1)


class CreditNumberingTest(TestCase):
    def setUp(self):
        self.owner = make_owner()
        self.prop = make_property(self.owner)
        self.rent = make_rent(self.owner, self.prop)

    def test_credit_number_auto_generated(self):
        c = Credit.objects.create(
            rent=self.rent, amount=Decimal('50.00'),
            credit_date=date.today(), description='Descuento', created_by=self.owner,
        )
        self.assertRegex(c.credit_number, r'^CRED-\d+-\d+$')


class DebitNumberingTest(TestCase):
    def setUp(self):
        self.owner = make_owner()
        self.prop = make_property(self.owner)
        self.rent = make_rent(self.owner, self.prop)

    def test_debit_number_auto_generated(self):
        d = Debit.objects.create(
            rent=self.rent, amount=Decimal('30.00'),
            debit_date=date.today(), description='Cargo extra', created_by=self.owner,
        )
        self.assertRegex(d.debit_number, r'^DEB-\d+-\d+$')


# ─────────────────────────────────────────────
# Signal Tests (Invoice paid_amount / status update)
# ─────────────────────────────────────────────

class InvoiceSignalTest(TestCase):
    def setUp(self):
        self.owner = make_owner()
        self.prop = make_property(self.owner)
        self.rent = make_rent(self.owner, self.prop)
        self.inv = make_invoice(self.rent, amount=Decimal('500.00'))

    def test_confirmed_payment_updates_invoice_paid_amount(self):
        Payment.objects.create(
            invoice=self.inv, amount=Decimal('300.00'),
            payment_date=date.today(), payment_method='cash', status='confirmed',
        )
        self.inv.refresh_from_db()
        self.assertEqual(self.inv.paid_amount, Decimal('300.00'))

    def test_invoice_status_becomes_paid_on_full_payment(self):
        Payment.objects.create(
            invoice=self.inv, amount=Decimal('500.00'),
            payment_date=date.today(), payment_method='cash', status='confirmed',
        )
        self.inv.refresh_from_db()
        self.assertEqual(self.inv.status, 'paid')

    def test_invoice_status_becomes_partial_on_partial_payment(self):
        Payment.objects.create(
            invoice=self.inv, amount=Decimal('250.00'),
            payment_date=date.today(), payment_method='cash', status='confirmed',
        )
        self.inv.refresh_from_db()
        self.assertEqual(self.inv.status, 'partial')

    def test_pending_payment_does_not_update_invoice(self):
        Payment.objects.create(
            invoice=self.inv, amount=Decimal('500.00'),
            payment_date=date.today(), payment_method='cash', status='pending',
        )
        self.inv.refresh_from_db()
        self.assertEqual(self.inv.paid_amount, Decimal('0.00'))
        self.assertEqual(self.inv.status, 'pending')

    def test_multiple_confirmed_payments_accumulate(self):
        Payment.objects.create(
            invoice=self.inv, amount=Decimal('200.00'),
            payment_date=date.today(), payment_method='cash', status='confirmed',
        )
        Payment.objects.create(
            invoice=self.inv, amount=Decimal('300.00'),
            payment_date=date.today(), payment_method='transfer', status='confirmed',
        )
        self.inv.refresh_from_db()
        self.assertEqual(self.inv.paid_amount, Decimal('500.00'))
        self.assertEqual(self.inv.status, 'paid')


# ─────────────────────────────────────────────
# RentAccountStatus Service Tests
# ─────────────────────────────────────────────

class RentAccountStatusTest(TestCase):
    def setUp(self):
        self.owner = make_owner()
        self.prop = make_property(self.owner)
        self.rent = make_rent(self.owner, self.prop)

    def test_zero_balance_with_no_activity(self):
        status = RentAccountStatus(self.rent).get_status()
        self.assertEqual(status['balance_owed'], Decimal('0.00'))
        self.assertFalse(status['is_past_due'])

    def test_balance_equals_unpaid_invoice(self):
        make_invoice(self.rent, amount=Decimal('500.00'), status='pending')
        status = RentAccountStatus(self.rent).get_status()
        self.assertEqual(status['balance_owed'], Decimal('500.00'))

    def test_balance_reduced_by_confirmed_payment(self):
        inv = make_invoice(self.rent, amount=Decimal('500.00'), status='pending')
        Payment.objects.create(
            invoice=inv, amount=Decimal('300.00'),
            payment_date=date.today(), payment_method='cash', status='confirmed',
        )
        inv.refresh_from_db()
        status = RentAccountStatus(self.rent).get_status()
        self.assertEqual(status['balance_owed'], Decimal('200.00'))

    def test_credit_reduces_balance(self):
        make_invoice(self.rent, amount=Decimal('500.00'), status='pending')
        Credit.objects.create(
            rent=self.rent, amount=Decimal('50.00'),
            credit_date=date.today(), description='Descuento', created_by=self.owner,
        )
        status = RentAccountStatus(self.rent).get_status()
        self.assertEqual(status['balance_owed'], Decimal('450.00'))

    def test_debit_increases_balance(self):
        make_invoice(self.rent, amount=Decimal('500.00'), status='pending')
        Debit.objects.create(
            rent=self.rent, amount=Decimal('100.00'),
            debit_date=date.today(), description='Cargo extra', created_by=self.owner,
        )
        status = RentAccountStatus(self.rent).get_status()
        self.assertEqual(status['balance_owed'], Decimal('600.00'))

    def test_late_fee_included_in_balance(self):
        make_invoice(
            self.rent,
            amount=Decimal('500.00'),
            late_fee_amount=Decimal('50.00'),
            status='overdue_with_fee',
        )
        status = RentAccountStatus(self.rent).get_status()
        self.assertEqual(status['balance_owed'], Decimal('550.00'))
        self.assertEqual(status['total_late_fees'], Decimal('50.00'))

    def test_pending_payment_not_counted(self):
        inv = make_invoice(self.rent, amount=Decimal('500.00'), status='pending')
        Payment.objects.create(
            invoice=inv, amount=Decimal('500.00'),
            payment_date=date.today(), payment_method='cash', status='pending',
        )
        status = RentAccountStatus(self.rent).get_status()
        # balance should still be 500 (pending payment not counted)
        self.assertEqual(status['balance_owed'], Decimal('500.00'))


# ─────────────────────────────────────────────
# View Tests
# ─────────────────────────────────────────────

class DashboardViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.owner = make_owner()
        self.tenant = make_tenant()

    def test_dashboard_redirects_unauthenticated(self):
        response = self.client.get(reverse('dashboard'))
        self.assertRedirects(response, '/log_in?next=/dashboard', fetch_redirect_response=False)

    def test_dashboard_loads_for_owner(self):
        self.client.login(username='owner@test.com', password='pass123')
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_dashboard_loads_for_tenant(self):
        self.client.login(username='tenant@test.com', password='pass123')
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)


class InvoicesViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.owner = make_owner()
        self.prop = make_property(self.owner)
        self.rent = make_rent(self.owner, self.prop)
        make_invoice(self.rent)

    def test_invoices_view_loads(self):
        self.client.login(username='owner@test.com', password='pass123')
        response = self.client.get(reverse('invoices'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('invoices', response.context)


class AdjustmentsViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.owner = make_owner()
        self.prop = make_property(self.owner)
        self.rent = make_rent(self.owner, self.prop)

    def test_adjustments_view_loads_for_owner(self):
        self.client.login(username='owner@test.com', password='pass123')
        response = self.client.get(reverse('adjustments'))
        self.assertEqual(response.status_code, 200)

    def test_tenant_redirected_from_adjustments(self):
        tenant = make_tenant(email='t2@test.com')
        self.client.login(username='t2@test.com', password='pass123')
        response = self.client.get(reverse('adjustments'))
        self.assertEqual(response.status_code, 302)

    def test_create_credit_via_post(self):
        self.client.login(username='owner@test.com', password='pass123')
        response = self.client.post(reverse('adjustments'), {
            'action': 'add_credit',
            'rent': self.rent.id,
            'amount': '50.00',
            'credit_date': date.today().isoformat(),
            'description': 'Test credit',
        })
        self.assertRedirects(response, reverse('adjustments'))
        self.assertEqual(Credit.objects.filter(rent=self.rent).count(), 1)

    def test_create_debit_via_post(self):
        self.client.login(username='owner@test.com', password='pass123')
        response = self.client.post(reverse('adjustments'), {
            'action': 'add_debit',
            'rent': self.rent.id,
            'amount': '30.00',
            'debit_date': date.today().isoformat(),
            'description': 'Test debit',
        })
        self.assertRedirects(response, reverse('adjustments'))
        self.assertEqual(Debit.objects.filter(rent=self.rent).count(), 1)


class ConfirmPaymentViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.owner = make_owner()
        self.tenant = make_tenant()
        self.prop = make_property(self.owner)
        self.rent = make_rent(self.owner, self.prop, tenant=self.tenant)
        self.inv = make_invoice(self.rent)
        self.payment = Payment.objects.create(
            invoice=self.inv, amount=Decimal('500.00'),
            payment_date=date.today(), payment_method='cash', status='pending',
        )

    def test_owner_can_confirm_payment(self):
        self.client.login(username='owner@test.com', password='pass123')
        self.client.post(reverse('confirm_payment', args=[self.payment.id]))
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, 'confirmed')

    def test_tenant_cannot_confirm_payment(self):
        self.client.login(username='tenant@test.com', password='pass123')
        self.client.post(reverse('confirm_payment', args=[self.payment.id]))
        self.payment.refresh_from_db()
        self.assertNotEqual(self.payment.status, 'confirmed')


class PublicPaymentPortalTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.owner = make_owner()
        self.prop = make_property(self.owner)
        self.rent = make_rent(self.owner, self.prop)
        self.inv = make_invoice(self.rent, status='pending')

    def test_portal_loads_without_login(self):
        response = self.client.get(reverse('public_payment_portal'))
        self.assertEqual(response.status_code, 200)

    def test_valid_submission_creates_payment(self):
        self.client.post(reverse('public_payment_portal'), {
            'rent_number': self.rent.rent_number,
            'tenant_email': 'tenant@test.com',
            'amount': '500.00',
            'payment_date': date.today().isoformat(),
            'payment_method': 'cash',
        })
        self.assertEqual(Payment.objects.filter(invoice=self.inv, status='pending').count(), 1)

    def test_invalid_rent_number_stays_on_form(self):
        response = self.client.post(reverse('public_payment_portal'), {
            'rent_number': 'INVALID-999',
            'tenant_email': 'tenant@test.com',
            'amount': '500.00',
            'payment_date': date.today().isoformat(),
            'payment_method': 'cash',
        })
        self.assertEqual(response.status_code, 200)
