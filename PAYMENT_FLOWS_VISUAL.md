# Two Payment Registration Flows - Visual Summary

## Flow 1: Tenant Reports Payment (Existing)

```
┌─────────────────────────────────────────────────────────────────┐
│ TENANT PAYMENT REPORTING FLOW                                   │
└─────────────────────────────────────────────────────────────────┘

1. Tenant clicks "Registrar Pago" in dashboard
                     ↓
2. Form displays: ReportPaymentForm (shows rent, property, amount, etc.)
                     ↓
3. Tenant fills form:
   - Selects rent from their rented properties
   - Selects property
   - Enters amount
   - Optional: uploads confirmation file
   - Selects payment method
                     ↓
4. Tenant submits form
                     ↓
5. View creates Transaction record with status='pending'
                     ↓
6. Email sent to OWNER with confirmation button
                     ↓
7. Owner receives email: "Nuevo pago pendiente de confirmación"
   - Owner clicks "Confirmar Pago" button
                     ↓
8. Owner's confirm_payment view:
   - Changes status to 'confirmed'
   - Creates Payment record (linked to Invoice)
   - Sends receipt PDF to tenant
                     ↓
9. ✅ Tenant receives receipt email with PDF
   ✅ Payment is confirmed
   ✅ Invoice status updated to paid/partial
```

---

## Flow 2: Owner Registers Payment (NEW)

```
┌─────────────────────────────────────────────────────────────────┐
│ OWNER PAYMENT REGISTRATION FLOW (NEW)                           │
└─────────────────────────────────────────────────────────────────┘

1. Owner clicks "Registrar Pago" in properties dashboard
                     ↓
2. Form displays: OwnerPaymentForm (SHOWS UNPAID INVOICES)
                     ↓
3. Owner selects Rent from dropdown
   - Only owner's active rents shown
                     ↓
4. AJAX Request fetches unpaid invoices for selected rent
                     ↓
5. Invoice dropdown populated with:
   - INV-1-202403-01 - Vencimiento: 05/03/2024 - Saldo: $1,000.00
   - INV-1-202402-01 - Vencimiento: 05/02/2024 - Saldo: $500.00
                     ↓
6. Owner selects Invoice
                     ↓
7. Balance display shows:
   - Saldo sin pagar: $1,000.00
   - Recargo por atraso: $50.00 (if applicable)
                     ↓
8. Amount field auto-filled with balance ($1,000.00)
   - Owner can edit if paying partial amount
                     ↓
9. Owner fills remaining fields:
   - Payment Date
   - Payment Method (ACH/Yappy, Cash, Other)
   - Description (optional)
   - "Enviar Recibo al Inquilino" checkbox (default: checked)
                     ↓
10. Owner submits form
                     ↓
11. View creates TWO records IMMEDIATELY:
    a) Payment record with status='confirmed' ✅ (NO CONFIRMATION NEEDED!)
    b) Legacy Transaction record (for audit trail)
                     ↓
12. Payment signal automatically:
    - Updates Invoice.paid_amount
    - Updates Invoice.status (paid/partial/overdue)
                     ↓
13. If "Enviar Recibo" is checked:
    - PDF receipt generated
    - Sent to tenant email
                     ↓
14. ✅ Owner sees success message and redirects to properties
    ✅ Payment is IMMEDIATELY confirmed (no extra step!)
    ✅ Tenant receives receipt (optional)
    ✅ Invoice status updated automatically
```

---

## Key Differences

| Step | Tenant Flow | Owner Flow |
|------|-------------|-----------|
| **Form Type** | ReportPaymentForm | OwnerPaymentForm |
| **Invoice Selection** | ❌ No | ✅ Yes (required) |
| **Invoice Filtering** | N/A | ✅ AJAX filtered by rent |
| **Balance Display** | ❌ No | ✅ Yes (with late fees) |
| **Confirmation Required** | ✅ Yes (by owner) | ❌ No (auto-confirmed) |
| **Receipt Timing** | After owner confirms | Immediately (optional) |
| **Records Created** | Transaction (pending) | Payment + Transaction (both confirmed) |
| **Time to Close** | Depends on owner | Instant |

---

## Same URL, Different Forms

```
┌─────────────────────┐
│ Tenant clicks       │
│ "Registrar Pago"    │
└──────────┬──────────┘
           │
      URL: report_payment/
           │
      ┌────┴────┐
      │          │
      ▼          ▼
  role='T'    role='O'
      │          │
      │          │
▼─────────────┐ ┌──────────────────────────┐
│ ReportPayment│ │ OwnerPaymentForm (NEW)  │
│ Form         │ │ - Rent selector         │
│ (existing)   │ │ - Invoice selector      │
│              │ │ - Balance display       │
│              │ │ - Send receipt option   │
└──────────────┘ └──────────────────────────┘
      │                    │
      ▼                    ▼
  Transaction         Payment + Transaction
  status='pending'    status='confirmed'
      │                    │
      ▼                    ▼
  Email to owner    Receipt to tenant
  (needs confirm)   (immediate)
```

---

## Data Flow: Invoice Updates

### Owner Payment Flow - Data Flow:

```
Owner submits form
       ↓
Payment.objects.create(
  invoice=selected_invoice,
  status='confirmed'
)
       ↓
Signal: @receiver(post_save, sender=Payment)
       ↓
Recalculate:
- invoice.paid_amount = sum(all confirmed payments)
- invoice.status = determine based on amount
       ↓
Invoice automatically updated:
  if paid_amount >= amount:
    status = 'paid' ✅
  elif paid_amount > 0:
    status = 'partial' ⚠️
  else:
    status = 'pending' ⏳
```

---

## Sample Scenarios

### Scenario 1: Owner Registers Full Payment

```
Invoice:
  - Amount: $1,000
  - Paid: $0
  - Balance: $1,000
  - Status: pending

Owner submits payment of $1,000

Result:
  - Payment created: $1,000 (confirmed)
  - Invoice.paid_amount: $1,000
  - Invoice.status: 'paid' ✅
  - Receipt sent to tenant
```

### Scenario 2: Owner Registers Partial Payment

```
Invoice:
  - Amount: $1,000
  - Paid: $0
  - Balance: $1,000
  - Status: pending

Owner submits payment of $500

Result:
  - Payment created: $500 (confirmed)
  - Invoice.paid_amount: $500
  - Invoice.status: 'partial' ⚠️
  - Remaining balance: $500
  - Receipt sent to tenant
```

### Scenario 3: Owner Registers Payment with Late Fee

```
Invoice:
  - Amount: $1,000
  - Paid: $0
  - Late Fee: $100
  - Balance: $1,100
  - Status: overdue_with_fee

Owner submits payment of $1,100

Result:
  - Payment created: $1,100 (confirmed)
  - Invoice.paid_amount: $1,100
  - Invoice.status: 'paid' ✅
  - Late fee covered
  - Receipt sent to tenant
```

---

## URL Routes

```
GET/POST /report_payment/
  ├─ If user.role == 'O': Show OwnerPaymentForm
  └─ If user.role == 'T': Show ReportPaymentForm

POST /api/unpaid-invoices/ (NEW)
  ├─ Request: rent_id
  ├─ Response: { invoices: [...] }
  └─ Used by AJAX in owner form
```

---

## Form Fields Summary

### OwnerPaymentForm (NEW):
```
- rent: ModelChoiceField (required)
  - Queryset: Rent.objects.filter(owner=user, is_active=True)
  
- invoice: ModelChoiceField (required)
  - Queryset: Invoice.objects.filter(status__in=['pending', 'partial', 'overdue', 'overdue_with_fee'])
  
- amount: DecimalField (required)
  - Validation: amount <= invoice.get_balance_owed()
  
- payment_date: DateField (required)
  
- payment_method: ChoiceField (required)
  - Choices: ('ach_yappy', 'cash', 'other')
  
- description: CharField (optional)
  
- send_receipt: BooleanField (default: True)
```

### ReportPaymentForm (EXISTING):
```
- transaction_date: DateField
- type: ChoiceField (forced to 'pago' for tenants)
- rent: ModelChoiceField
- tenant: ModelChoiceField (hidden, auto-set)
- property: ModelChoiceField
- amount: DecimalField
- description: CharField
- payment_method: ChoiceField
- confirmation_file: FileField
```

---

## Browser Experience

### Owner's View (After Clicking "Registrar Pago"):

```
┌─────────────────────────────────────────────────────┐
│ Registrar Pago Recibido                             │
│ Agregar un nuevo pago de tu inquilino               │
├─────────────────────────────────────────────────────┤
│                                                     │
│ Seleccionar Contrato de Alquiler:                  │
│ [Dropdown: Select a property...]                   │
│ ├─ Propiedad A (INV: $1000/mo)                     │
│ └─ Propiedad B (INV: $1500/mo)                     │
│                                                     │
│ Factura sin Pagar:                                 │
│ [Dropdown: Select an invoice...]  (disabled)       │
│ [shows only after rent selected]                   │
│                                                     │
│ ┌─────────────────────────────────┐                │
│ │ ℹ️  Saldo sin pagar: $1,000.00   │ (appears      │
│ │ Recargo por atraso: $50.00      │  when         │
│ └─────────────────────────────────┘ invoice       │
│                                     selected)     │
│                                                     │
│ Monto del Pago:                                     │
│ [$1,000.00]  (auto-filled, editable)              │
│                                                     │
│ Fecha del Pago:                                     │
│ [Date picker: 2024-03-04]                         │
│                                                     │
│ Método de Pago:                                     │
│ [Dropdown: ACH o Yappy / Efectivo / Otros]        │
│                                                     │
│ Notas/Descripción:                                 │
│ [Text area...]                                     │
│                                                     │
│ ☑ Enviar Recibo al Inquilino                      │
│ Se enviará un recibo en PDF al inquilino...       │
│                                                     │
│ [Registrar Pago Button]                           │
│                                                     │
│ [Volver al Panel Button]                          │
└─────────────────────────────────────────────────────┘
```

### Tenant's View (After Clicking "Registrar Pago"):

```
┌─────────────────────────────────────────────────────┐
│ Registrar Pago                                      │
│ Reportar un nuevo pago que realizaste               │
├─────────────────────────────────────────────────────┤
│                                                     │
│ Fecha de Transacción:                              │
│ [Date picker]                                      │
│                                                     │
│ Tipo:                                               │
│ [Pago] (disabled, fixed)                           │
│                                                     │
│ Contrato de Alquiler:                              │
│ [Dropdown: Select...]                              │
│                                                     │
│ Propiedad:                                          │
│ [Dropdown: Select...]                              │
│                                                     │
│ Monto:                                              │
│ [$]                                                 │
│                                                     │
│ Descripción:                                        │
│ [Text area]                                         │
│                                                     │
│ Método de Pago:                                     │
│ [Dropdown]                                          │
│                                                     │
│ Comprobante de Confirmación:                       │
│ [File upload]                                       │
│                                                     │
│ [Registrar Pago Button]                           │
│                                                     │
│ [Back to Dashboard Button]                         │
└─────────────────────────────────────────────────────┘
```

---

## Success Messages

### Owner Flow:
```
✅ "Pago registrado por $1,000.00. Recibo enviado al inquilino."
   OR
✅ "Pago registrado por $1,000.00."
```

### Tenant Flow:
```
✅ "Pago registrado. Esperando confirmación del propietario."
```

---

## Error Messages

### Owner Form:
```
❌ "El monto no puede ser mayor a lo adeudado ($1,000.00)"
❌ "No tienes acceso a esta factura."
❌ "Error al registrar el pago. Por favor intenta de nuevo."
```

### Tenant Form:
```
❌ "Error: No se pudo determinar el propietario de la propiedad."
```

---

## AJAX Response Example

```
POST /api/unpaid-invoices/
Data: { rent_id: 5 }

Response:
{
  "invoices": [
    {
      "id": 42,
      "invoice_number": "INV-5-202403-01",
      "due_date": "2024-03-05",
      "amount": "1000.00",
      "paid_amount": "0.00",
      "balance_owed": "1000.00",
      "late_fee_amount": "50.00",
      "status": "overdue_with_fee",
      "display": "INV-5-202403-01 - Vencimiento: 05/03/2024 - Saldo: $1050.00"
    },
    {
      "id": 41,
      "invoice_number": "INV-5-202402-01",
      "due_date": "2024-02-05",
      "amount": "1000.00",
      "paid_amount": "1000.00",
      "balance_owed": "0.00",
      "late_fee_amount": "0.00",
      "status": "paid",
      "display": "INV-5-202402-01 - Vencimiento: 05/02/2024 - Saldo: $0.00"
    }
  ]
}
```

---

## Implementation Complete ✅

The unified payment form is now ready:
- Single URL serves both flows
- Role-based form switching
- No user confusion
- Efficient for both owners and tenants
- Beautiful, responsive UI
- Full invoice tracking
