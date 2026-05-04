# FINKO — Property Management System
## Comprehensive Project Description
### For Content Generation: Scripts, Visual & Textual Media

---

## 1. WHAT IS FINKO?

**Finko** is a web-based SaaS (Software as a Service) Property Management System specifically designed for landlords and property managers in **Panama**. The platform centralizes every aspect of rental property administration — from tenant onboarding and contract management, to automatic invoice generation, payment tracking, financial reporting, and full compliance with Panama's **Ley 81 de Protección de Datos Personales** (Data Protection Law).

The product is aimed at individual landlords and small-to-medium property management companies who currently rely on spreadsheets, WhatsApp messages, and physical paperwork to manage their rental portfolios. Finko replaces all of that with a single, professional, automated platform.

**Tech stack:** Django 5 (Python), Bootstrap 5, Redis, Celery, WeasyPrint, Stripe, Mailgun, PythonAnywhere hosting.

**Primary language of the UI:** Spanish (Panama market).

---

## 2. TARGET USERS

### Owner (Propietario)
- A landlord who owns one or more rental properties.
- Has full administrative access to their portfolio.
- Manages tenants, contracts, invoices, payments, maintenance, and financial reports.
- Receives automated email notifications for every relevant event.

### Tenant (Inquilino)
- A renter living in one of the owner's properties.
- Can have a registered account or be an "unregistered tenant" (stored in the rent record by name/email only).
- Can report payments via a public portal without needing an account.
- Receives invoices, payment confirmations, and contract documents by email.

### Unregistered Tenant
- A tenant who does not have a Finko account but is still linked to a rent contract.
- The owner stores their personal details (name, email, phone, ID, nationality, DOB, sex) directly in the Rent record.
- They interact with the system exclusively through the public payment portal using their rent number.

---

## 3. SUBSCRIPTION PLANS

Finko operates on a freemium SaaS model with three tiers:

| Plan | Name (Spanish) | Description |
|---|---|---|
| `free` | Gratis / Básico | Basic access, limited features |
| `standard` | Estándar | Full feature set for individual landlords |
| `enterprise` | Empresarial | Multi-property, multi-user management |

- **Stripe** is integrated for subscription checkout and payment processing.
- **Promo codes** (`PromoCode` model) support discounts with expiry dates.
- Users can be upgraded/downgraded from the pricing page (`/pricing`).

---

## 4. CORE DATA MODELS

### User
Custom extension of Django's `AbstractUser`. Authentication is by **email** (not username). Every user has a **role**:
- **Owner (O)**: Manages properties, tenants, contracts, finances.
- **Tenant (T)**: Views their rent, transaction history, and documents.

Key fields: `full_name`, `phone`, `email`, `personal_id`, `id_type` (cédula / pasaporte), `nac` (country), `dob`, `sex`, `role`, `plan`, Stripe IDs, and all Ley 81 consent fields.

Social login is supported via **Google** and **Facebook** through `django-allauth`.

### Properties (Propiedades)
Represents a physical rental unit owned by a user.
- Types: Apartment (Apartamento), House (Casa), Loft, Commercial (Local), Other.
- Fields: `alias`, `location`, `category`, `size` (m²), `bedrooms`, `bathrooms`, `description`, `monthly_pmt` (owner's mortgage payment), `maint_fee`, `maint_status`, `available`.
- Tracks maintenance request status: cleared → requested → assigned → in_progress → finished.

### Rent (Contrato de Arrendamiento)
The central model linking an owner, a property, and a tenant into an active lease.
- Supports both **registered** and **unregistered** tenants.
- Auto-generates a unique `rent_number` (format: `RENT-{owner_id}-{property_id}-{sequence}`, e.g., `RENT-1-6-0001`).
- Tracks `start_date`, `end_date`, `rent_amount`, `rent_due_date` (day of month).
- Configurable **late fee policy**: none, 10%, 20% of rent, or a fixed amount.
- Configurable **grace period** in days before late fees apply (default: 5 days).
- `next_invoice_date`: Drives the automated daily invoice generation task.
- `is_active`: Marks whether the lease is still running or has been closed.

### Invoice (Factura)
One invoice is generated per month for each active rent.
- Auto-numbered: `INV-{rent_id}-{YYYYMM}-{sequence}`, e.g., `INV-5-202504-01`.
- Tracks: `amount` (original rent), `paid_amount`, `late_fee_amount`, `late_fee_applied_date`.
- Statuses: `pending` → `partial` → `paid` / `overdue` / `overdue_with_fee`.
- Contains a UUID `payment_token` used for public (unauthenticated) payment links.
- Methods: `get_balance_owed()`, `get_days_overdue()`, `is_past_due()`, `mark_paid()`.

### Payment (Pago)
A single payment applied against an Invoice.
- Auto-numbered: `PAY-{rent_id}-{sequence}`, e.g., `PAY-5-0012`.
- Statuses: `pending` → `confirmed` / `rejected`.
- Payment methods: ACH/Yappy, Cash (Efectivo), Other.
- Tenants may upload a confirmation file (image or PDF).
- When **confirmed**, a Django signal automatically updates the parent Invoice's `paid_amount` and recalculates its status.

### Credit
A manual credit (discount, overpayment refund) applied to a rent account by the owner.
- Auto-numbered: `CRED-{rent_id}-{sequence}`.
- Subtracts from the tenant's balance owed.

### Debit
A manual debit charge (damage repair, extra fee) applied to a rent account by the owner.
- Auto-numbered: `DEB-{rent_id}-{sequence}`.
- Adds to the tenant's balance owed.

### AuditLog
Tracks all sensitive data access events for Ley 81 compliance:
- Actions: view, edit, delete, export, login.
- Records: user, model_name, object_id, IP address, timestamp.

### Feedback
User-submitted feedback, bug reports, comments, and suggestions sent directly from within the app.

---

## 5. KEY FEATURES

### 5.1 Property Management
- Add, view, and edit rental properties with full details (location, type, size, bedrooms, bathrooms, description, mortgage payment, maintenance fees).
- Track availability status.
- Monitor property maintenance status from within the platform.
- Owners can manage multiple properties simultaneously.

### 5.2 Tenant Management
- Register tenants (with a Finko account) or add them as unregistered tenants with stored contact info.
- View all tenants linked to the owner's properties.
- Tenant portal: tenants can log in and see their rent details, invoices, payment history, and documents.

### 5.3 Lease / Rent Contract Management
- Create new lease contracts linking owner, property, and tenant.
- Define rent amount, start/end dates, payment due day, late fee policy, and grace period.
- Renew leases with extended dates.
- Close/finish a lease when a tenant vacates.
- Auto-generate a downloadable **PDF lease contract** with all terms, parties, and legal language (Spanish), including the rent amount written out in words.

### 5.4 Automated Invoice Generation (Celery Task)
- Every day at **12:01 AM**, the `generate_invoices` Celery task runs.
- For every active rent where `next_invoice_date = today`, a new Invoice is created.
- The invoice's due date is set to the following day.
- An email notification is automatically sent to the tenant with invoice details, amount, and due date.
- A summary email is sent to the owner listing all newly generated invoices.
- `next_invoice_date` advances by 30 days after each run.

### 5.5 Automated Late Fee Application (Celery Task)
- Every day at **12:05 AM** (after invoice generation), the `apply_late_fees` task runs.
- Detects all overdue Invoices where:
  - `due_date` is in the past.
  - The grace period has expired.
  - No late fee has been applied yet.
  - The invoice is not fully paid.
- Calculates and applies the late fee according to the rent's `late_fee_type` setting.
- Updates invoice status to `overdue_with_fee`.
- Sends a notification email to the owner.

### 5.6 Payment Flows

#### Flow A — Tenant Submits Payment (Pending Approval)
1. Tenant visits `/report_payment` (logged in) or `/pay/` (public portal, no login needed).
2. Tenant enters: rent number, email (for verification), payment date, amount, method, optional description, optional file upload.
3. A Payment record is created with `status='pending'`.
4. Owner receives an email notification with a link to confirm or reject.
5. Owner reviews and clicks **Confirm** or **Reject** from the dashboard.
6. On confirmation: Payment status → `confirmed`, Invoice `paid_amount` auto-updated by signal, receipt PDF available.

#### Flow B — Owner Registers Payment (Immediate Confirmation)
1. Owner visits `/report_payment` (logged in).
2. Owner selects the Rent and Invoice (AJAX call dynamically populates unpaid invoices with balance info).
3. Owner enters: amount, date, method, description. Optionally sends receipt email to tenant.
4. Payment is **immediately confirmed** — no separate approval step.
5. Invoice `paid_amount` updated automatically via signal.
6. Receipt PDF generated and optionally emailed to tenant.

### 5.7 Public Payment Portal (`/pay/`)
- Accessible to anyone with no login required.
- Tenant enters their **rent number** (provided by owner) and their email address.
- The system verifies the email matches the rent contract.
- Tenant fills in payment details and uploads an optional confirmation file.
- Owner and tenant both receive email notifications.
- Perfect for tenants who prefer not to create an account.

### 5.8 Financial Adjustments
- **Credits**: Owner can manually apply credits to a rent account (discounts, goodwill adjustments, overpayment returns).
- **Debits**: Owner can manually add charges (damage fees, extra costs, unpaid utilities).
- Both generate downloadable PDF documents with unique numbering.
- Both factor into the `RentAccountStatus` balance calculation.

### 5.9 Invoice & Payment Filtering
- Invoices and Payments are filterable by status, date range, and rent using `django-filter`.
- Separate filter classes: `InvoiceFilter`, `PaymentFilter`, `CreditFilter`, `DebitFilter`.

### 5.10 PDF Document Generation (WeasyPrint)
All PDFs are generated server-side using **WeasyPrint** and rendered from HTML templates. Available PDF documents:

| Document | URL Pattern | Description |
|---|---|---|
| Payment Receipt | `/payment/{id}/pdf/` | Receipt for a confirmed payment |
| Invoice | `/invoice/{id}/pdf/` | Monthly rent invoice |
| Credit Note | `/credit/{id}/pdf/` | Credit adjustment document |
| Debit Note | `/debit/{id}/pdf/` | Debit adjustment document |
| Lease Contract | `/contract/{rent_id}/pdf/` | Full rental contract in Spanish legal format |
| Income Letter | (form-based) | Proof of income letter for tenants |
| General Letter | (form-based) | Custom letter generator |
| Payment History | (report-based) | Full payment history summary |
| Statement | (report-based) | Financial statement |

All PDFs embed the Finko logo as a base64-encoded image for reliable rendering without external dependencies.

### 5.11 Email Notifications (Mailgun)
Finko uses **Mailgun** for transactional emails. Emails are sent for:
- New invoice generated → to tenant.
- Invoice generation summary → to owner.
- Late fee applied → to owner.
- Tenant submits payment → to owner (with confirm link).
- Tenant submits payment → to tenant (confirmation receipt).
- Payment confirmed by owner → to tenant.
- Payment rejected → to tenant.
- Account deletion request → to admin.

All emails are HTML-formatted with a consistent brand style matching the app's color palette (`#17c1e8` cyan brand color, Montserrat font).

### 5.12 Maintenance Tracking
- Owners can flag a property's maintenance status.
- Status progression: Cleared (Ninguno) → Requested (Solicitado) → Assigned (Asignado) → In Progress (En Progreso) → Finished (Terminado).
- Maintenance dashboard view groups open requests.

### 5.13 Reports & Dashboard
- Owner dashboard shows: active rents, pending payments, overdue invoices, balance owed per tenant, and financial KPIs.
- `RentAccountStatus` service class computes per-rent financial status:
  - `balance_owed` = (total invoiced + total late fees + total debits) − (total confirmed payments + total credits)
  - Status categories: `good`, `partial`, `late`, `overdue_with_fee`.
  - Next due date and next due amount.
  - Late fee history details.
- Generate documents page allows bulk PDF generation.
- Financial reports available (income letters, payment histories, statements).

### 5.14 Document & Letter Generation
- **Income Letter** (`/income_letter_form`): Generates a formal letter confirming a tenant's rent payment record, useful for visa or bank applications.
- **General Letter** (`/letter_form`): Owner can write custom letters on branded Finko letterhead as PDFs.
- **Lease Contract** (`/contract/{id}/pdf/`): Full bilingual-compatible lease agreement PDF with all legal clauses.

### 5.15 User Profile & Account Management
- Users can update their personal information, contact details, and ID information.
- Password reset via email (Django built-in reset flow).
- Social login via **Google** and **Facebook** using `django-allauth`.
- Role selection modal on first login for social accounts (owner or tenant).

### 5.16 Data Protection & Ley 81 Compliance (Panama)
Full compliance with **Panama's Ley 81 de Protección de Datos Personales**:

- **Consent tracking**: Privacy policy acceptance date, terms acceptance date, marketing consent, data retention consent — all stored with timestamps.
- **Right of Access** (`/my-data/`): Users can view all their personal data stored in the system.
- **Right of Portability** (`/export-my-data/`): Users can export their complete data as a JSON file.
- **Right of Erasure** (`/delete-account/`): Users can request account deletion; admin is notified.
- **Audit Log**: Every sensitive data access, export, or deletion request is logged with user, action, object, IP, and timestamp.
- Registration requires explicit checkboxes for privacy policy and terms of service.

### 5.17 Feedback System
- Users can submit feedback, bug reports, comments, or suggestions from within the app (`/feedback/`).
- Feedback types: Comment, Feedback, Issue, Suggestion.
- Admin can mark feedback as read and respond.

### 5.18 Admin Customizations
- Custom admin view for **Form Labels** (`/admin/form-labels/`): Admin can dynamically configure UI form labels per form, per field, without changing code.
- Form labels are exportable to CSV/JSON for translation or review.
- Django admin panels for all core models with custom filtering, read-only fields, and organized fieldsets.

---

## 6. AUTHENTICATION & AUTHORIZATION

- **Email-based login** (not username).
- Django session authentication for all protected views.
- `django-allauth` for social login (Google, Facebook) with custom adapter to assign role on first login.
- Role-based access control: owners see owner features, tenants see tenant features.
- `@login_required` decorators on all protected views.
- Object-level security: users can only access PDFs and data belonging to their own rents/properties.
- CSRF protection on all forms.
- X-Frame-Options enforcement on PDF views (`@xframe_options_sameorigin`).
- Password reset flow with email token validation.

---

## 7. AUTOMATED BACKGROUND TASKS (Celery + Redis)

Finko uses **Celery** with **Redis** as the message broker for background task processing.

| Task | Schedule | Description |
|---|---|---|
| `generate_invoices` | Daily 12:01 AM | Creates monthly invoices for qualifying rents; emails tenants and owners |
| `apply_late_fees` | Daily 12:05 AM | Detects overdue invoices past grace period; applies configured late fee; emails owners |

**Celery Beat** manages the schedule. In production (PythonAnywhere), tasks are triggered manually via `manage.py shell` commands or scheduled through the platform's task scheduler.

---

## 8. USER FLOWS (Step-by-Step)

### 8.1 Onboarding Flow (New Owner)
1. Owner visits the landing page at `/`.
2. Clicks "Registrarse" and fills out the registration form (name, email, phone, ID, DOB, country, sex, role=Owner, password).
3. Accepts privacy policy and terms of service checkboxes.
4. Account created → redirected to dashboard.
5. Owner adds their first property (`/properties_form`).
6. Owner registers tenant(s) (`/register_tenant`) or creates rent with unregistered tenant details.
7. Owner creates the first lease contract (`/new_rent`).
8. Owner configures late fee policy on the rent.
9. Owner sets `next_invoice_date` to start automated billing.
10. System begins sending monthly invoices automatically.

### 8.2 Monthly Rent Cycle
1. Celery task runs at midnight → creates Invoice for the rent.
2. Tenant receives email: "Nueva Factura de Renta" with amount and due date.
3. Owner receives summary email with all invoices created.
4. Tenant pays (via bank transfer, Yappy/ACH, or cash).
5. Tenant reports the payment:
   - **Option A**: Via public portal `/pay/` (no login) using rent number.
   - **Option B**: Via `/report_payment` (logged in).
   - **Option C**: Owner registers payment directly on tenant's behalf.
6. Owner confirms or rejects pending payment from dashboard.
7. On confirmation: Invoice status → `paid`, receipt PDF generated, email sent to tenant.
8. If unpaid after grace period: Late fee automatically applied at 12:05 AM.

### 8.3 Tenant Payment via Public Portal
1. Owner shares rent number (`RENT-X-X-XXXX`) with tenant.
2. Tenant visits `yourdomain.com/pay/`.
3. Enters rent number and registered email.
4. System validates the email against the rent record.
5. Tenant fills in: date, amount, method, description, optional file upload.
6. Submits form → Payment created (pending).
7. Owner receives email with payment details and confirmation link.
8. Tenant receives confirmation email.
9. Owner confirms from dashboard → receipt email sent to tenant.

### 8.4 Lease Renewal
1. Owner goes to rent detail / dashboard.
2. Clicks "Renovar Contrato" on an active rent.
3. Fills in new end date and optionally adjusts rent amount.
4. System saves the renewal with updated dates.
5. New PDF contract can be generated.

### 8.5 Closing a Rent
1. Owner clicks "Finalizar Contrato" from the rent view.
2. `is_active` set to `False` on the Rent.
3. Property availability updated to "Disponible".
4. Invoice generation stops (task filters `is_active=True` only).

---

## 9. TECHNOLOGY STACK

| Layer | Technology |
|---|---|
| **Framework** | Django 5.1 (Python) |
| **Frontend** | Bootstrap 5, jQuery, HTML5 |
| **PDF Generation** | WeasyPrint 65 |
| **Task Queue** | Celery 5 + Redis |
| **Email** | Mailgun API (`mailgun_utils.py`) |
| **Payments (subscriptions)** | Stripe |
| **Social Auth** | django-allauth (Google, Facebook) |
| **Country Fields** | django-countries |
| **Form Filtering** | django-filter |
| **Form Widgets** | django-widget-tweaks |
| **Database (dev)** | SQLite |
| **Database (prod)** | MySQL (PythonAnywhere) |
| **Hosting** | PythonAnywhere |
| **Environment Config** | python-dotenv |
| **Static Files** | Django staticfiles |

---

## 10. KEY UI PAGES

| Page | URL | Who Sees It | Description |
|---|---|---|---|
| Home / Landing | `/` | Public | Marketing landing page with features overview |
| Features | `/features/` | Public | Detailed feature list |
| About | `/about/` | Public | Company/product description |
| Contact | `/contact/` | Public | Contact form |
| Pricing | `/pricing/` | Public | Subscription plans and Stripe checkout |
| Register | `/register_user` | Public | New user registration |
| Login | `/log_in` | Public | Email + password login |
| Dashboard | `/dashboard` | Owners | Financial overview, active rents, pending payments |
| Properties | `/properties` | Owners | Property list and management |
| Tenants | `/tenants` | Owners | Tenant list |
| New Rent | `/new_rent` | Owners | Create lease contract |
| Invoices | `/invoices` | Owners | Invoice list with filter |
| Report Payment | `/report_payment` | Both | Submit or register payment |
| Public Payment Portal | `/pay/` | Public (no login) | Tenant payment submission |
| Maintenance | `/maintenance` | Owners | Maintenance request tracker |
| Documents | `/documents` | Both | Document center |
| Generate Documents | `/generate-documents/` | Owners | Bulk PDF generation |
| Adjustments | `/adjustments` | Owners | Credits and debits |
| Reports | `/reports` | Owners | Financial reports |
| My Data | `/my-data/` | All users | Personal data view (Ley 81) |
| Export My Data | `/export-my-data/` | All users | JSON data export (Ley 81) |
| Delete Account | `/delete-account/` | All users | Account deletion request (Ley 81) |
| Privacy Policy | `/privacy/` | Public | Full privacy policy |
| Terms of Service | `/terms/` | Public | Terms and conditions |
| Tenant Portal | `/tenant_portal` | Tenants | Tenant home view |
| User Profile | `/user_profile` | All users | Edit personal information |
| Feedback | `/feedback/` | All users | Submit feedback or report issues |

---

## 11. FINANCIAL MODEL (How Balance is Calculated)

The `RentAccountStatus` service class implements the complete balance formula:

```
balance_owed = 
    (Σ Invoice.amount) 
  + (Σ Invoice.late_fee_amount) 
  + (Σ Debit.amount) 
  - (Σ confirmed Payment.amount) 
  - (Σ Credit.amount)
```

**Status labels:**
- `good` — balance_owed ≤ 0 (fully paid up)
- `partial` — invoice partially paid, not yet overdue
- `late` — overdue invoice exists, no late fee yet
- `overdue_with_fee` — overdue invoice + late fee applied

---

## 12. DOCUMENT NUMBERING SYSTEM

All financial documents use structured auto-generated numbers for easy reference:

| Document Type | Format | Example |
|---|---|---|
| Rent Contract | `RENT-{owner_id}-{property_id}-{seq}` | `RENT-1-6-0001` |
| Invoice | `INV-{rent_id}-{YYYYMM}-{seq}` | `INV-5-202504-01` |
| Payment | `PAY-{rent_id}-{seq}` | `PAY-5-0012` |
| Credit | `CRED-{rent_id}-{seq}` | `CRED-5-0003` |
| Debit | `DEB-{rent_id}-{seq}` | `DEB-5-0001` |

---

## 13. BRAND & TONE OF VOICE

- **Brand name:** Finko
- **Primary language:** Spanish (Panama)
- **Tone:** Professional, approachable, trustworthy, modern
- **Primary color:** Cyan `#17c1e8`
- **Typography:** Montserrat
- **Logo:** Finko logo PNG embedded in all PDFs
- **Tagline (informal):** "Gestión Profesional de Propiedades" / "Administración de propiedades hecha fácil"
- **Key value propositions:**
  - Save time by automating 80% of administrative work
  - Centralize everything: contracts, payments, tenants, reports
  - No more spreadsheets, WhatsApp, or physical receipts
  - 100% compliant with Panama's Ley 81
  - Professional-grade PDFs and automatic email notifications
  - Accessible to tenants with no account required (public payment portal)

---

## 14. COMPETITIVE POSITIONING

Finko is positioned as:
- **Local**: Built specifically for Panama's legal and market context (Ley 81, cédula ID type, Yappy/ACH payment methods).
- **Bilingual-ready**: UI and documents in Spanish; architecture supports expansion.
- **Accessible**: Even tenants without accounts can participate through the public payment portal.
- **Automated**: Background tasks handle the most tedious recurring work (invoices, late fees) with zero manual intervention.
- **Transparent**: Owners always know exactly who owes what, since when, and how much.

---

## 15. SUMMARY FACTS FOR CONTENT CREATION

- **Category**: PropTech / SaaS / FinTech (rental-focused)
- **Market**: Panama (primary); Latin America (expansion potential)
- **Users**: Property owners, property managers, tenants
- **Core problem solved**: Manual, fragmented, error-prone rental administration
- **Key differentiator**: All-in-one platform built for Panama's specific legal and financial context
- **Automation highlights**: Auto invoices, auto late fees, instant email notifications, PDF generation
- **Compliance highlight**: Full Ley 81 data protection compliance with user rights portal
- **No-account access**: Public payment portal lets tenants report payments with just a rent number
- **Document generation**: Professional PDFs for contracts, invoices, receipts, credit/debit notes, letters
- **Subscription model**: Free tier + paid plans via Stripe
- **Built with**: Django, Python, Bootstrap 5, Celery, Redis, Mailgun, Stripe, WeasyPrint
