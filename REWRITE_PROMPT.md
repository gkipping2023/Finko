# Finko — Full Project Rewrite Prompt
**Purpose:** This document is a detailed, authoritative specification for rewriting the Finko/Rentu Django project from scratch with a clean, invoice-centric accounting model. It is written to be used directly as input to an AI coding agent.

---

## 1. Context & Background

### What is Finko?
Finko is a **property management SaaS** (Sistema de Gestión de Propiedades) targeting Panama. It manages the full lifecycle of residential and commercial rentals: properties, tenants, leases, invoicing, payments, and document generation.

### Tech Stack (keep all of these)
- **Backend:** Django 5.1, Python
- **Auth:** django-allauth (email/password + Google + Facebook social login)
- **Task queue:** Celery + Redis
- **Email:** Mailgun HTTP API (`mailgun_utils.py`)
- **PDF generation:** WeasyPrint
- **Payments:** Stripe (subscription billing for the SaaS plan — separate from rent payments)
- **Filters:** django-filter
- **Templates:** Django templates (widget_tweaks, bootstrap-based UI)
- **Countries:** django-countries
- **DB (dev):** SQLite; **DB (prod):** MySQL on PythonAnywhere
- **Compliance:** Panama Ley 81 (data protection)
- **Language:** Spanish UI throughout

### Project Layout
```
rentu/          # Django project settings (settings.py, urls.py, celery.py, wsgi.py, asgi.py)
main/           # Single Django app with all models, views, forms, tasks, signals, etc.
  models.py
  views.py
  forms.py
  filters.py
  signals.py
  tasks.py
  services.py
  admin.py
  urls.py
  mailgun_utils.py
  adapters.py
  form_mixins.py
  form_labels.py
  admin_views.py
  tests.py
  templates/main/   # All HTML templates
  management/commands/
main/migrations/    # Django migrations (will be rebuilt from scratch)
static/             # Static assets (CSS, JS, images — do not change)
templates/          # Global templates (index.html, navbar.html)
media/              # Uploaded files
requirements.txt    # All dependencies (do not change)
rentu/settings.py   # Already configured correctly
```

---

## 2. The Core Problem: Hybrid Model

The current codebase has a **hybrid financial model** that is complex and error-prone:

### Current (BROKEN) Architecture
```
Financial Event
    ↓
Transaction (legacy model) ← PRIMARY record in most views
    ↓ (Django signal, fragile)
Invoice / Payment (modern models) ← SECONDARY, partially used
```

- The `Transaction` model has 25+ fields and handles 6 different types: `invoice`, `receipt`, `credit`, `debit`, `fee`, `pago`
- Most views, forms, filters, and PDF templates still reference `Transaction` as the primary model
- `generate_invoices` Celery task creates **both** an `Invoice` AND a `Transaction` for every monthly rent invoice
- `report_payments` view creates **both** a `Payment` AND a `Transaction` when registering a payment
- `confirm_payment` view acts on a `Transaction`, then creates a `Payment` as a side effect
- The dashboard mixes `Transaction` queries and `Invoice` queries to compute the same financial totals
- `services.py` `RentAccountStatus` has complex logic to handle both systems simultaneously
- Many views fall back to legacy `Transaction` data when no `Invoice` records exist

### Target (CLEAN) Architecture
```
Balance Owed per Rent = (Invoices + Debits) − (confirmed Payments + Credits)
```

| Model | Effect on Balance | Purpose |
|---|---|---|
| `Invoice` | **+** (adds) | Automated monthly rent charge |
| `Debit` | **+** (adds) | Manual charge adjustment (e.g. extra fee, correction) |
| `Payment` | **−** (subtracts) | Money received from tenant |
| `Credit` | **−** (subtracts) | Manual credit adjustment (e.g. remove late fee, correct overcharge) |

No `Transaction` model at all. Every financial operation goes through one of these four models.

---

## 3. No Migration Needed

**The project has NO active users yet.** You can:
- Drop all existing migrations and create a fresh `0001_initial.py`
- Delete the `db.sqlite3` database
- Rewrite all models cleanly without backward compatibility shims
- Remove the `Transaction` model entirely

---

## 4. New Data Model Specification

### Models to KEEP (unchanged or lightly updated)

#### `PromoCode`
Keep exactly as-is.

#### `User` (AbstractUser)
Keep exactly as-is. All existing fields stay including:
- `first_name`, `last_name`, `full_name`, `phone`, `email`, `personal_id`, `id_type`, `nac`, `dob`, `sex`
- `role` (choices: `'O'` = Propietario, `'T'` = Inquilino)
- `plan` (free/standard/enterprise), `promo_code`
- `stripe_customer_id`, `stripe_subscription_id`
- All Ley 81 data protection fields (`privacy_policy_accepted`, `terms_accepted`, etc.)
- `USERNAME_FIELD = 'email'`

#### `Properties`
Keep exactly as-is.

#### `Rent`
Keep exactly as-is. All fields including:
- `owner`, `tenant`, `property`, `start_date`, `end_date`, `rent_amount`, `rent_due_date`
- `next_invoice_date`, `status`, `is_active`, `rent_number`, `rent_sequence_number`
- All unregistered tenant fields
- `late_fee_type`, `late_fee_amount`, `late_fee_grace_days`
- `get_late_fee()` method and `save()` auto-numbering logic

#### `AuditLog`
Keep exactly as-is.

#### `Feedback`
Keep exactly as-is.

#### `Invoice`
Keep all existing fields. Add:
- `payment_token` = `models.UUIDField(default=uuid.uuid4, editable=False, unique=True)` — used by the public payment portal to identify the invoice without exposing the integer PK

Existing fields to keep:
- `rent` (FK to Rent)
- `invoice_number` (auto-generated: `INV-{rent_id}-{YYYYMM}-{seq}`)
- `invoice_date`, `due_date`
- `amount`, `paid_amount`
- `late_fee_amount`, `late_fee_applied_date`
- `status` (pending / partial / paid / overdue / overdue_with_fee)
- `created_at`, `updated_at`
- All existing methods: `get_balance_owed()`, `get_days_overdue()`, `is_past_due()`, `mark_paid()`, `save()`

#### `Payment`
Replace the existing `Payment` model with a cleaner version. Remove the `transaction` OneToOneField entirely.

New `Payment` model fields:
```python
class Payment(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='payments')
    payment_number = models.CharField(max_length=100, unique=True, editable=False)  # auto-generated: PAY-{invoice_id}-{seq}
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateField()
    payment_method = models.CharField(max_length=100, choices=payment_method)
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    description = models.TextField(max_length=250, blank=True, null=True)
    confirmation_file = models.FileField(upload_to='payment_confirmations/', null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Meta, indexes, __str__, save() with auto payment_number generation
```

Auto-generate `payment_number`: format `PAY-{invoice.id}-{zero-padded sequence}`, e.g. `PAY-42-0001`.

### Models to ADD

#### `Credit`
Represents a manual credit adjustment issued by the owner against a specific rent. **Reduces the tenant's balance owed.** Used for corrections such as removing an incorrectly applied late fee, discounting a month, or fixing a billing error. Unlike `Payment`, a `Credit` does not represent money received — it is a bookkeeping adjustment.

```python
class Credit(models.Model):
    rent = models.ForeignKey(Rent, on_delete=models.CASCADE, related_name='credits')
    credit_number = models.CharField(max_length=100, unique=True, editable=False)  # CRED-{rent_id}-{seq}
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    credit_date = models.DateField()
    description = models.TextField(max_length=250)  # reason / explanation
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='issued_credits')
    
    # Meta, __str__, save() with auto credit_number generation
```

Auto-generate `credit_number`: format `CRED-{rent_id}-{zero-padded sequence}`, e.g. `CRED-7-0001`.

#### `Debit`
Represents a manual debit adjustment issued by the owner against a specific rent. **Adds to the tenant's balance owed.** Used for corrections such as adding a charge that was missed, billing for damages, or correcting an underbilling. Unlike `Invoice`, a `Debit` is a one-off manual charge, not an automated monthly invoice.

```python
class Debit(models.Model):
    rent = models.ForeignKey(Rent, on_delete=models.CASCADE, related_name='debits')
    debit_number = models.CharField(max_length=100, unique=True, editable=False)  # DEB-{rent_id}-{seq}
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    debit_date = models.DateField()
    description = models.TextField(max_length=250)  # reason / explanation
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='issued_debits')
    
    # Meta, __str__, save() with auto debit_number generation
```

Auto-generate `debit_number`: format `DEB-{rent_id}-{zero-padded sequence}`, e.g. `DEB-7-0001`.

### Model to REMOVE
- `Transaction` — delete entirely. Remove all references everywhere.

---

## 5. Business Rules & Flow

### Invoicing (Automated)
- The Celery `generate_invoices` task runs daily at 12:01 AM
- For each `Rent` where `next_invoice_date == today` and `is_active=True`:
  - Create one `Invoice` record
  - Send email to tenant (registered or unregistered)
  - Send summary email to owner
  - Advance `rent.next_invoice_date += 30 days`
- **Do NOT create any `Transaction` record** — invoices are the sole source of truth

### Late Fees (Automated)
- The Celery `apply_late_fees` task runs daily at 12:05 AM
- For each `Invoice` that is overdue beyond the grace period, apply the late fee
- Update `invoice.late_fee_amount` and `invoice.status`
- **Do NOT create any `Transaction` record**

### Owner Registers a Payment Received
- Owner selects a Rent → system shows unpaid Invoices via AJAX
- Owner selects Invoice, enters amount, date, method
- Creates a `Payment(status='confirmed')` linked to Invoice
- Signal `update_invoice_on_payment` fires, updates `Invoice.paid_amount` and `Invoice.status`
- Optionally sends receipt PDF to tenant (email via Mailgun, attach PDF of Payment)

### Tenant Reports a Payment Made
- Tenant selects their active Rent (which has an unpaid Invoice)
- Tenant enters amount, date, method, optional confirmation file
- Creates a `Payment(status='pending')` linked to Invoice
- System sends email to owner with a confirmation link
- Owner clicks link → opens `confirm_payment` view → can confirm or reject

### Owner Confirms a Pending Payment
- View `confirm_payment(payment_id)` — takes a Payment pk, not Transaction pk
- On confirm: `payment.status = 'confirmed'`, `payment.confirmed_at = now()`
- Signal fires, updates Invoice
- Generates PDF receipt and sends to tenant

### Public Payment Portal (No Login)
- URL: `/pay/`
- Tenant enters `rent_number` and their email
- System finds the matching Rent and its oldest unpaid Invoice
- Tenant enters amount, method, optional confirmation file
- Creates `Payment(status='pending')` linked to that Invoice
- Owner receives notification email with confirm link

### Credits (Manual Balance Reduction)
- Owner issues a credit adjustment against a specific Rent
- A `Credit` **directly reduces the tenant's balance owed** (same effect as a payment, but without money changing hands)
- Use cases: removing a wrongly applied late fee, correcting an overcharge, granting a discount for maintenance issues
- Credits generate a PDF document (`credit_pdf.html`) the owner can share with the tenant
- The `RentAccountStatus.get_status()` service must include `Credit.amount` when calculating balance

### Debits (Manual Balance Addition)
- Owner issues a debit charge against a specific Rent
- A `Debit` **directly adds to the tenant's balance owed** (same effect as an additional invoice, but ad-hoc)
- Use cases: charging for property damage, billing a missed fee, correcting an underbilling
- Debits generate a PDF document (`debit_pdf.html`) the owner can share with the tenant
- The `RentAccountStatus.get_status()` service must include `Debit.amount` when calculating balance

### Balance Formula
For any given Rent, the total balance owed is:
```
balance_owed = (
    sum(Invoice.get_balance_owed() for unpaid invoices)
    + sum(Debit.amount for active debits)
    - sum(Credit.amount for active credits)
)
```

---

## 6. Services Layer

Replace `services.py` completely. The new `RentAccountStatus` class must:
- Use only `Invoice`, `Payment`, `Credit`, and `Debit` data
- Remove all `Transaction` fallback logic
- Remove `is_legacy_only` filter (that field is gone)
- Apply the 4-model balance formula

```python
class RentAccountStatus:
    def __init__(self, rent):
        self.rent = rent
        self.today = date.today()
    
    def get_status(self):
        # Balance formula:
        # total_charged  = sum(Invoice.amount) + sum(Invoice.late_fee_amount) + sum(Debit.amount)
        # total_credited = sum(confirmed Payment.amount) + sum(Credit.amount)
        # balance_owed   = total_charged - total_credited
        #
        # Return dict:
        # { 'is_past_due', 'days_past_due', 'balance_owed', 'total_invoiced',
        #   'total_paid', 'total_credits', 'total_debits', 'total_late_fees',
        #   'status', 'next_due_date', 'next_due_amount', 'late_fee_info' }
```

---

## 7. Signals

`signals.py` — keep as-is (it only references `Payment` and `Invoice`, which is correct):

```python
@receiver(post_save, sender=Payment)
def update_invoice_on_payment(sender, instance, created, **kwargs):
    if instance.status == 'confirmed':
        # Recalculate Invoice.paid_amount from all confirmed payments
        # Update Invoice.status (paid / partial / overdue / overdue_with_fee / pending)
```

---

## 8. Forms

### Remove entirely
- `TransactionForm`
- `ReportPaymentForm`

### Keep (unchanged)
- `NewUserForm`
- `UpdateUserForm`
- `AddPropertyForm`
- `NewRentForm`
- `RenewLeaseForm`
- `NewTenantForm`

### Rewrite
- `OwnerPaymentForm` → clean version without Transaction fields. Fields: `rent`, `invoice`, `amount`, `payment_date`, `payment_method`, `description`, `send_receipt` (BooleanField). Keep AJAX invoice loading behavior.

### Add
- `TenantPaymentForm` — for tenants to report a payment. Fields: `rent` (filtered to active rents of the logged-in tenant), `invoice` (unpaid invoices for selected rent), `amount`, `payment_date`, `payment_method`, `description`, `confirmation_file`.

- `CreditForm` — for owners to issue a manual credit adjustment. Fields: `rent`, `amount`, `credit_date`, `description`. The `rent` queryset must be filtered to rents owned by the current user.

- `DebitForm` — for owners to issue a manual debit charge. Fields: `rent`, `amount`, `debit_date`, `description`. The `rent` queryset must be filtered to rents owned by the current user.

- `PublicPaymentForm` — rewrite to work without Transaction. Fields: `rent_number`, `tenant_email`, `amount`, `payment_date`, `payment_method`, `description`, `confirmation_file`.

---

## 9. Filters

Replace `filters.py` entirely:

### Remove
- `TransactionFilter`

### Add
```python
class InvoiceFilter(django_filters.FilterSet):
    status = django_filters.ChoiceFilter(choices=INVOICE_STATUS_CHOICES)
    rent = django_filters.ModelChoiceFilter(queryset=Rent.objects.none())
    date_range = django_filters.CharFilter(method='filter_date_range')
    class Meta:
        model = Invoice
        fields = ['status', 'rent', 'date_range']

class PaymentFilter(django_filters.FilterSet):
    status = django_filters.ChoiceFilter(choices=PAYMENT_STATUS_CHOICES)
    payment_method = django_filters.ChoiceFilter(choices=payment_method)
    date_range = django_filters.CharFilter(method='filter_date_range')
    class Meta:
        model = Payment
        fields = ['status', 'payment_method', 'date_range']

class DebitFilter(django_filters.FilterSet):
    rent = django_filters.ModelChoiceFilter(queryset=Rent.objects.none())
    date_range = django_filters.CharFilter(method='filter_date_range')
    class Meta:
        model = Debit
        fields = ['rent', 'date_range']

class CreditFilter(django_filters.FilterSet):
    rent = django_filters.ModelChoiceFilter(queryset=Rent.objects.none())
    date_range = django_filters.CharFilter(method='filter_date_range')
    class Meta:
        model = Credit
        fields = ['rent', 'date_range']
```

---

## 10. Views — Complete Rewrite Specification

### Views to REMOVE entirely
- `transaction_pdf()` — replaced by `payment_pdf()`
- `add_transaction()` — replaced by role-specific forms: `OwnerPaymentForm` (register payment), `CreditForm` (issue credit), `DebitForm` (issue debit charge)
- `preview_transaction_confirmation()` — remove

### Views to RENAME / REWRITE

#### `payments()` → `invoices()`
- URL: `/invoices`
- Shows a list of `Invoice` objects filtered by the logged-in owner
- Filter using `InvoiceFilter`
- Context: `invoices`, `filter`, summary stats (total billed, total paid, total outstanding)

#### `report_payments()` → `report_payment()`
- Owner path: use `OwnerPaymentForm`, create `Payment(status='confirmed')`
- Tenant path: use `TenantPaymentForm`, create `Payment(status='pending')`
- No Transaction creation anywhere
- Owner: signal auto-updates invoice; optionally send receipt
- Tenant: send notification email to owner with confirm link pointing to `/payment/{payment_id}/confirm/`

#### `confirm_payment(transaction_id)` → `confirm_payment(payment_id)`
- Takes a `Payment` PK (not Transaction PK)
- Check `payment.confirmed_at` to prevent duplicate confirmation
- On confirm: `payment.status = 'confirmed'`, `payment.confirmed_at = now()`, save → signal fires
- Generate PDF receipt (`payment_receipt.html` template) and email to tenant
- Support reject action
- Support resend action

#### `dashboard()`
- **Remove all `Transaction` queries completely**
- All financial metrics must come from `Invoice` and `Payment`:
  - `collected_income` = sum of confirmed `Payment.amount` this month for owner's invoices
  - `pending_income` = sum of `Invoice.amount - Invoice.paid_amount` for current month invoices
  - `expected_monthly_income` = sum of `Rent.rent_amount` for all active rents
  - `recent_payments` = last 5 confirmed `Payment` objects for this owner
  - `last_payment` = most recent confirmed `Payment`
  - `pending_confirmations` = count of pending `Payment` objects for this owner
  - `overdue_rent_alerts` = count of active rents with overdue invoices
- Tenant-specific context:
  - `tenant_total_paid` = sum of confirmed payments on tenant's invoices
  - `tenant_recent_payments` = last 5 confirmed Payment objects for tenant

#### `properties()`
- Remove `pending_transactions` (Transaction-based)
- Keep `pending_payments` = `Payment.objects.filter(invoice__rent__owner=owner, status='pending')`
- `payments` = last 10 `Invoice` objects for owner
- For tenant: `payments` = last 10 confirmed `Payment` objects
- `rent.last_payment_date` / `rent.last_payment_amount` — get from latest confirmed `Payment` for that rent:
  ```python
  last = Payment.objects.filter(invoice__rent=rent, status='confirmed').order_by('-payment_date').first()
  ```

#### `generate_documents()`
- `action='payment_history'`: query `Payment` objects (confirmed, status='confirmed') instead of `Transaction`
  - Filter by date range and property (via `payment.invoice.rent.property`)
  - Use existing PDF template but update context to pass `payments` instead of `transactions`
- `action='income_letter'`: query confirmed `Payment` objects grouped by property
- `action='statement'`: query `Invoice` objects and confirmed `Payment` objects for the month
- Remove all `Transaction` imports and queries

#### `public_payment_portal()`
- Find `Rent` by `rent_number`
- Find oldest unpaid `Invoice` for that rent
- Create `Payment(status='pending')` linked to Invoice
- Send owner notification email with `/payment/{payment_id}/confirm/` link
- Do NOT create a Transaction record

#### `adjustments()`
- URL: `/adjustments`
- Replaces the old empty `expenses()` stub
- Owner can view, create, and manage both `Credit` and `Debit` manual adjustments
- Two tabs or sections: "Débitos" (manual charges) and "Créditos" (manual reductions)
- Uses `CreditForm`, `DebitForm`, `CreditFilter`, `DebitFilter`
- Each row has a link to download the corresponding PDF

### New Views to ADD

#### `payment_pdf(payment_id)`
- Generate PDF for a confirmed Payment
- Use `payment_receipt.html` template
- Show: payment_number, date, amount, method, invoice reference, tenant info, owner info

#### `invoice_pdf(invoice_id)`
- Generate PDF for an Invoice
- Use `invoice_pdf.html` template
- Show: invoice_number, rent details, amount, due date, status, any payments made

#### `credit_pdf(credit_id)`
- Generate PDF for a Credit note
- Use `credit_pdf.html` template

#### `debit_pdf(debit_id)`
- Generate PDF for a manual Debit charge
- Use `debit_pdf.html` template

#### `adjustments()`
- URL: `/adjustments`
- Owner can view and create both `Credit` (balance reductions) and `Debit` (balance additions) manual adjustments
- Uses `CreditForm`, `DebitForm`, `CreditFilter`, `DebitFilter`

### Views to KEEP (no changes needed)
- `home()`, `features()`, `about()`, `contact()`
- `log_in()`, `logoutUser()`, `register_user()`, `user_profile()`
- `register_tenant()`, `tenants()`, `new_rent()`, `renew_lease()`, `finish_rent()`
- `properties_form()`, `update_property()`, `rent_details()`
- `contract_pdf()`, `render_contract_pdf()`
- `set_user_role()`, `tenant_portal()`
- `get_unpaid_invoices()` — keep as-is (already uses Invoice model)
- `maintenance()`, `documents()`, `reports()`
- `create_subscription_checkout_session()`
- `privacy_policy()`, `terms_of_service()`, `my_data()`, `export_my_data()`, `delete_my_account()`
- `feedback_form()`, `feedback_success()`
- `public_payment_success()`

---

## 11. URLs

Replace transaction-based URLs with invoice/payment-based ones:

### Remove
```python
path('transaction/<int:transaction_id>/pdf/', views.transaction_pdf, name='transaction_pdf'),
path('add_transaction', views.add_transaction, name='add_transaction'),
path('confirm-payment/<int:transaction_id>/', views.confirm_payment, name='confirm_payment'),
path('preview-transaction-confirmation/', views.preview_transaction_confirmation, ...),
```

### Add
```python
path('payments', views.invoices, name='payments'),          # renamed from payments→invoices but keep URL for nav
path('payment/<int:payment_id>/pdf/', views.payment_pdf, name='payment_pdf'),
path('invoice/<int:invoice_id>/pdf/', views.invoice_pdf, name='invoice_pdf'),
path('payment/<int:payment_id>/confirm/', views.confirm_payment, name='confirm_payment'),
path('adjustments', views.adjustments, name='adjustments'),
path('credit/<int:credit_id>/pdf/', views.credit_pdf, name='credit_pdf'),
path('debit/<int:debit_id>/pdf/', views.debit_pdf, name='debit_pdf'),
```

### Keep (with modification)
```python
path('report_payment', views.report_payment, name='report_payment'),
# Remove the old 'expenses' URL — replaced by 'adjustments'
```

---

## 12. PDF Templates to Rewrite

### Remove (Transaction-based)
- `transaction_receipt.html`
- `transaction_pago.html`
- `transaction_credit.html`
- `transaction_debit.html`
- `transaction_fee.html`
- `transaction_invoice.html`
- `transaction_confirmation.html`

### Create (Invoice/Payment-based)
All PDFs should maintain the existing visual style (Finko branding, #17c1e8 teal color, Montserrat font, white card layout, logo base64 embedded).

#### `payment_receipt.html`
Receipt for a confirmed payment. Shows:
- Finko logo header
- Title: "Recibo de Pago"
- `payment.payment_number`, `payment.payment_date`
- Invoice reference: `payment.invoice.invoice_number`
- Tenant name and email
- Property: `payment.invoice.rent.property.alias`
- Amount paid: `payment.amount`
- Payment method: `payment.get_payment_method_display()`
- Description (if any)
- Owner info
- Confirmation timestamp

#### `invoice_pdf.html`
Invoice document. Shows:
- Title: "Factura de Renta"
- `invoice.invoice_number`, `invoice.invoice_date`, `invoice.due_date`
- Rent/property details
- Tenant info
- Amount due: `invoice.amount`
- Late fee (if applicable): `invoice.late_fee_amount`
- Total owed: `invoice.get_balance_owed()`
- Status badge
- Payment history table (list of payments applied to this invoice)

#### `credit_pdf.html`
Manual credit adjustment document. Shows:
- Title: "Nota de Crédito"
- `credit.credit_number`, `credit.credit_date`
- Rent / property / tenant info
- Amount: `credit.amount` (shown as a reduction to balance)
- Description / reason for the credit
- Issued by (owner name and email)
- Note: "Este crédito reduce el saldo pendiente del arrendatario"

#### `debit_pdf.html`
Manual debit charge document. Shows:
- Title: "Nota de Débito"
- `debit.debit_number`, `debit.debit_date`
- Rent / property / tenant info
- Amount: `debit.amount` (shown as an addition to balance)
- Description / reason for the charge
- Issued by (owner name and email)
- Note: "Este débito incrementa el saldo pendiente del arrendatario"

### Templates to UPDATE (minor changes)

#### `payments.html` → rename conceptually to `invoices.html` (or keep filename)
- Replace Transaction table with Invoice table
- Columns: invoice_number, rent/property, tenant, invoice_date, due_date, amount, paid_amount, balance_owed, status, actions
- Add InvoiceFilter form at top
- Summary stats row: total billed, total paid, total outstanding

#### `dashboard.html`
- Replace `recent_payments` iteration (was Transaction) — now iterate `Payment` objects
- Remove any template tags referencing `transaction.transaction_number`, `transaction.type`, etc.
- Use `payment.payment_number`, `payment.amount`, `payment.payment_date`, `payment.invoice.invoice_number`
- Owner widget: `pending_confirmations` count is now pending `Payment` objects

#### `properties.html`
- Remove `pending_transactions` section (Transaction-based public portal payments)
- Keep `pending_payments` section showing pending `Payment` objects
- `payments` list now shows `Invoice` objects (not Transaction)

#### `report_payment.html`
- Owner form: use `OwnerPaymentForm` — select rent, invoice, fill amount/date/method
- Tenant form: use `TenantPaymentForm` — select rent, invoice, fill amount/date/method, upload confirmation file

#### `confirm_payment.html`
- Update to show `payment` object fields instead of `transaction` fields
- Show `payment.payment_number`, `payment.amount`, `payment.invoice.invoice_number`

#### `payment_history_pdf.html`
- Update context iteration: loop over `payments` (Payment objects) instead of `transactions`
- Show columns: payment_number, invoice_number, property, date, method, amount

#### `statement_pdf.html`
- Remove Transaction rows; show Invoice rows + Payment rows cleanly
- Invoice section: what was billed
- Payment section: what was paid
- Balance: outstanding

#### `home1.html`, `my_data.html`
- Replace any Transaction references with Invoice/Payment references

---

## 13. Admin

Replace `TransactionAdmin` with:

```python
@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'rent', 'invoice_date', 'due_date', 'amount', 'paid_amount', 'status')
    list_filter = ('status', 'invoice_date')
    search_fields = ('invoice_number', 'rent__rent_number', 'rent__property__alias')
    readonly_fields = ('invoice_number', 'created_at', 'updated_at')

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('payment_number', 'invoice', 'payment_date', 'amount', 'payment_method', 'status', 'confirmed_at')
    list_filter = ('status', 'payment_method', 'payment_date')
    search_fields = ('payment_number', 'invoice__invoice_number', 'invoice__rent__rent_number')
    readonly_fields = ('payment_number', 'confirmed_at', 'created_at', 'updated_at')

@admin.register(Credit)
class CreditAdmin(admin.ModelAdmin):
    list_display = ('credit_number', 'rent', 'amount', 'credit_date', 'status')
    list_filter = ('status',)
    search_fields = ('credit_number', 'rent__rent_number')

@admin.register(Debit)
class DebitAdmin(admin.ModelAdmin):
    list_display = ('debit_number', 'rent', 'amount', 'debit_date', 'created_by')
    list_filter = ('debit_date',)
    search_fields = ('debit_number', 'rent__rent_number', 'rent__property__alias')
    readonly_fields = ('debit_number', 'created_at')
```

---

## 14. Celery Tasks — Full Rewrite of `tasks.py`

### `generate_invoices()` 
Remove all `Transaction` creation. Only:
1. Create `Invoice`
2. Send email to tenant
3. Send summary email to owner
4. Advance `rent.next_invoice_date`

### `apply_late_fees()`
Keep as-is (already only touches Invoice). Remove any Transaction imports.

### Remove
- Any helper functions that reference Transaction

---

## 15. `services.py` — Full Rewrite

Remove all Transaction/legacy fallback logic. `RentAccountStatus.get_status()` must:
- Query `Invoice.objects.filter(rent=self.rent)`
- Query confirmed payments via Invoice
- No fallback to `Transaction` queries
- Return the same dict structure (backward compatible with existing template usage)

---

## 16. `adapters.py`

Keep as-is (handles social auth adapter). Remove any Transaction imports if present.

---

## 17. `form_mixins.py`

Keep as-is.

---

## 18. `mailgun_utils.py`

Keep as-is (send_mailgun_simple function is correct and final).

---

## 19. Send Receipt to Tenant — New Implementation

Replace `send_receipt_to_tenant(transaction)` with `send_payment_receipt(payment)`:

```python
def send_payment_receipt(payment):
    """Send PDF receipt to tenant when their payment is confirmed."""
    rent = payment.invoice.rent
    
    # Determine recipient
    if rent.tenant and rent.tenant.email:
        tenant_email = rent.tenant.email
        tenant_name = rent.tenant.first_name
    elif rent.unregistered_tenant_email:
        tenant_email = rent.unregistered_tenant_email
        tenant_name = rent.unregistered_tenant_name or "Inquilino"
    else:
        return  # No email to send to
    
    # Generate PDF
    pdf = render_to_string('main/payment_receipt.html', {
        'payment': payment,
        'logo_base64': get_logo_for_pdf()
    })
    pdf_bytes = HTML(string=pdf).write_pdf()
    
    # Send via Mailgun
    send_mailgun_simple(
        subject=f"Recibo de Pago - {payment.payment_number}",
        html=<email HTML with confirmation message>,
        to_emails=tenant_email,
        from_email=settings.DEFAULT_FROM_EMAIL,
        attachments=[(f"recibo_{payment.payment_number}.pdf", pdf_bytes)]
    )
```

---

## 20. Public Payment Portal — Rewrite

New flow for `public_payment_portal()`:

1. On GET: show `PublicPaymentForm` 
2. On POST (valid form):
   a. Lookup `Rent` by `rent_number` (case-insensitive)
   b. Validate tenant email matches rent's tenant (registered or unregistered)
   c. Find oldest unpaid `Invoice` for the rent
   d. If no unpaid invoice: show message "No tienes facturas pendientes"
   e. Create `Payment(status='pending', invoice=invoice, ...)`
   f. Build confirm URL: `/payment/{payment.id}/confirm/`
   g. Email owner: "Nuevo pago registrado. Confirmar en [link]"
   h. Redirect to `public_payment_success` with success message

---

## 21. Specific Implementation Notes

### Auto-numbering for Payment
```python
def save(self, *args, **kwargs):
    if not self.pk and not self.payment_number:
        from django.db import transaction as db_transaction
        with db_transaction.atomic():
            last = Payment.objects.filter(invoice=self.invoice).aggregate(
                Max('id')
            )['id__max'] or 0
            seq = Payment.objects.filter(invoice=self.invoice).count() + 1
            self.payment_number = f"PAY-{self.invoice.id}-{str(seq).zfill(4)}"
            # Duplicate check
            while Payment.objects.filter(payment_number=self.payment_number).exists():
                seq += 1
                self.payment_number = f"PAY-{self.invoice.id}-{str(seq).zfill(4)}"
    super().save(*args, **kwargs)
```

### Confirm Payment View — Duplicate Prevention
Use `payment.confirmed_at` field (not None check) to prevent re-confirmation, same pattern as existing `Transaction.confirmed_at`.

### Dashboard — Invoice-Only Queries
```python
# Collected this month (confirmed payments)
collected_income = Payment.objects.filter(
    invoice__rent__owner=user,
    invoice__rent__is_active=True,
    status='confirmed',
    payment_date__gte=month_start,
    payment_date__lte=month_end
).aggregate(total=Sum('amount'))['total'] or 0

# Pending this month (invoices not fully paid, adjusted for credits/debits)
# Use RentAccountStatus per rent for accuracy, or approximate at the invoice level
pending_income = Invoice.objects.filter(
    rent__owner=user,
    rent__is_active=True,
    invoice_date__gte=month_start,
    invoice_date__lte=month_end
).aggregate(total=Sum('amount') - Sum('paid_amount'))['total'] or 0

# Recent payments
recent_payments = Payment.objects.filter(
    invoice__rent__owner=user,
    status='confirmed'
).order_by('-payment_date').select_related('invoice__rent__property', 'invoice__rent__tenant')[:5]

# Recent adjustments (combined credits and debits for the owner's awareness)
recent_credits = Credit.objects.filter(
    rent__owner=user,
    credit_date__gte=month_start
).aggregate(total=Sum('amount'))['total'] or 0

recent_debits = Debit.objects.filter(
    rent__owner=user,
    debit_date__gte=month_start
).aggregate(total=Sum('amount'))['total'] or 0
```

### Properties View — Last Payment from Payment model
```python
last = Payment.objects.filter(
    invoice__rent=rent,
    status='confirmed'
).order_by('-payment_date').first()
rent.last_payment_date = last.payment_date if last else None
rent.last_payment_amount = last.amount if last else None
```

---

## 22. Constants & Choices to Keep

All existing choices at the top of `models.py` that are still needed:
- `ID_Type`, `PLAN_CHOICES`, `payment_method`, `Sex`, `Roles`, `Category`, `Duration_of_Lease`
- `LATE_FEE_CHOICES`, `INVOICE_STATUS_CHOICES`, `PAYMENT_STATUS_CHOICES`
- `Status`, `Due_Status`, `maint_status`

### Remove
- `TRANSACTION_TYPES` — no longer needed

---

## 23. Migrations

After rewriting all models:
1. Delete the `main/migrations/` folder (all migration files)
2. Run `python manage.py makemigrations main`
3. Run `python manage.py migrate`
4. The result should be a single clean `0001_initial.py`

---

## 24. Tests (`tests.py`)

Rewrite all tests to use the new models. Remove all Transaction-based test cases. Add:
- `InvoiceGenerationTest` — test `generate_invoices` task creates Invoice only (no Transaction)
- `PaymentConfirmationTest` — test Payment confirm flow updates Invoice
- `PublicPortalTest` — test public payment portal creates Payment
- `RentAccountStatusTest` — test balance formula: `balance = invoices + debits − confirmed_payments − credits`
- `CreditAdjustmentTest` — test that creating a Credit reduces balance owed
- `DebitAdjustmentTest` — test that creating a Debit increases balance owed

---

## 25. What NOT to Change

- `settings.py` (all configurations are correct)
- `rentu/urls.py` (top-level routing is fine)
- `rentu/celery.py` (Celery config is correct)
- `mailgun_utils.py` (email utility is production-ready)
- `adapters.py` (social auth adapter is fine — remove Transaction import only)
- `form_mixins.py` (base form classes are fine)
- `form_labels.py` (form label overrides — check if Transaction references exist and remove)
- `admin_views.py` (form labels admin — remove Transaction references if any)
- All static assets (`static/` folder)
- All non-financial templates: `landing.html`, `log_in.html`, `register_user.html`, `new_rent.html`, `properties_form.html`, `user_profile.html`, `tenants.html`, `maintenance.html`, `documents.html`, `pricing.html`, `privacy_policy.html`, `terms_of_service.html`, `feedback_form.html`, `role_modal.html`, `password_*.html`
- `rentu/settings_pythonanywhere.py` and `finko_pythonanywhere_com_wsgi.py`

---

## 26. Step-by-Step Implementation Order

Implement in this order to avoid dependency issues:

1. **`models.py`** — Rewrite with new model structure (no Transaction, add Credit/Debit, enhance Payment)
2. **Fresh migrations** — Delete old migrations, run makemigrations + migrate
3. **`signals.py`** — Already correct, just verify imports
4. **`services.py`** — Rewrite RentAccountStatus without Transaction
5. **`tasks.py`** — Remove Transaction creation from generate_invoices
6. **`filters.py`** — Replace TransactionFilter with InvoiceFilter/PaymentFilter/DebitFilter
7. **`forms.py`** — Remove TransactionForm/ReportPaymentForm, add TenantPaymentForm/CreditForm/DebitForm
8. **`views.py`** — Systematic rewrite of all affected views
9. **`admin.py`** — Replace TransactionAdmin, register Credit and Debit
10. **`urls.py`** — Update URL patterns
11. **PDF templates** — Create payment_receipt.html, invoice_pdf.html, credit_pdf.html, debit_pdf.html
12. **Update existing templates** — dashboard.html, payments.html, properties.html, report_payment.html, confirm_payment.html, payment_history_pdf.html, statement_pdf.html
13. **`tests.py`** — Rewrite tests

---

## 27. Summary of What Gets Simplified

| Before (Hybrid) | After (Invoice-Centric) |
|---|---|
| `Transaction` model with 25+ fields | Removed entirely |
| `generate_invoices` creates Transaction + Invoice | Creates Invoice only |
| `report_payments` creates Transaction + Payment | Creates Payment only |
| `confirm_payment` acts on Transaction, creates Payment | Acts directly on Payment |
| `dashboard` mixes Transaction + Invoice queries | Invoice + Payment queries only |
| `payments` view shows Transaction list | `invoices` view shows Invoice list |
| `TransactionFilter` | `InvoiceFilter` + `PaymentFilter` + `CreditFilter` + `DebitFilter` |
| 6 transaction PDF templates | 4 clean PDFs (payment, invoice, credit, debit) |
| `send_receipt_to_tenant(transaction)` | `send_payment_receipt(payment)` |
| `RentAccountStatus` with legacy fallbacks | 4-model balance formula (Invoice+Debit−Payment−Credit) |
| Signal updates both Transaction AND Invoice | Signal updates Invoice only |
| Public portal creates Transaction | Public portal creates Payment directly |
| `services.py` complex dual-system logic | Clean 4-model balance calculation |
| No clear manual adjustment mechanism | `Credit` reduces balance; `Debit` increases balance |

The resulting codebase will be significantly simpler, with a single source of truth for all financial data.
