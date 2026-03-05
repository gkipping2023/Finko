# Payment Registration Implementation Guide

## Overview

Successfully implemented **Option A: Unified Payment Form** with role-based logic that uses the same `report_payment.html` template to handle both payment registration flows:

1. **Tenant Flow**: Reports payment they made → Owner confirms → Receipt sent
2. **Owner Flow**: Registers payment received → Immediately confirmed → Receipt sent

---

## Implementation Summary

### 1. New Form: `OwnerPaymentForm` (forms.py)

**Location**: [main/forms.py](main/forms.py#L357)

**Purpose**: Dedicated form for owners registering payments they've received

**Key Features**:
- **Rent Dropdown**: Filter to owner's active rents
- **Invoice Dropdown**: Shows unpaid invoices from selected rent
- **Amount Field**: Auto-populates with balance owed, validates no overpayment
- **Payment Details**: Date, method, description
- **Send Receipt Checkbox**: Option to send PDF receipt to tenant immediately

**Fields**:
```python
- rent: Rent selector (owner's active rents only)
- invoice: Invoice selector (unpaid invoices only)
- amount: Decimal field with validation
- payment_date: Date field (default today)
- payment_method: Choice field (ACH/Yappy, Cash, Other)
- description: Optional text area
- send_receipt: Boolean checkbox (default True)
```

**Validation**:
- Amount cannot exceed invoice balance owed
- Only unpaid/partial/overdue invoices shown

---

### 2. Updated View: `report_payments` (views.py)

**Location**: [main/views.py](main/views.py#L1027)

**Purpose**: Unified endpoint that handles both tenant and owner payment registration

**Flow**:

#### When Owner (role='O') logs in:
1. Displays `OwnerPaymentForm`
2. Owner selects Rent → Form loads unpaid invoices via AJAX
3. Owner selects Invoice → Form displays balance owed and late fees
4. Owner enters payment details and submits
5. **Immediately creates**:
   - `Payment` record with status='confirmed'
   - Legacy `Transaction` record (for audit trail)
6. **Optionally sends** PDF receipt to tenant
7. Redirects to properties page with success message

#### When Tenant (role='T') logs in:
1. Displays `ReportPaymentForm` (existing behavior)
2. Tenant reports payment they made
3. Creates `Transaction` with status='pending'
4. Sends confirmation email to owner
5. Owner must manually confirm payment via `confirm_payment` view
6. Redirects to report_payment page

---

### 3. New AJAX Endpoint: `get_unpaid_invoices` (views.py)

**Location**: [main/views.py](main/views.py#L1119)

**Purpose**: Provides dynamic invoice list for owner payment form

**Request**:
```
POST /api/unpaid-invoices/
Body: rent_id=<rent_id>
```

**Response**:
```json
{
  "invoices": [
    {
      "id": 1,
      "invoice_number": "INV-1-202403-01",
      "due_date": "2024-03-05",
      "amount": "1000.00",
      "paid_amount": "500.00",
      "balance_owed": "500.00",
      "late_fee_amount": "50.00",
      "status": "partial",
      "display": "INV-1-202403-01 - Vencimiento: 05/03/2024 - Saldo: $500.00"
    }
  ]
}
```

**Security**:
- Only accessible to logged-in users
- Validates owner has access to the rent
- Returns 403 if not an owner

---

### 4. Updated Template: `report_payment.html`

**Location**: [main/templates/main/report_payment.html](main/templates/main/report_payment.html)

**Features**:
- Conditional form rendering based on `user_role` context variable
- Owner form with AJAX invoice filtering
- Tenant form with existing fields (rent, property, amount, file upload, etc.)
- Inline JavaScript for invoice dropdown population
- Real-time balance display with late fee information

**Owner Form Layout**:
```
1. Rent Selection Dropdown
2. Invoice Balance Alert (shows unpaid amount + late fees)
3. Invoice Selection Dropdown
4. Payment Amount (auto-filled with balance owed)
5. Payment Date
6. Payment Method
7. Description
8. Send Receipt Checkbox
9. Submit Button
```

**Tenant Form Layout** (unchanged):
```
1. Transaction Date
2. Type (hidden, fixed to 'pago')
3. Rent Selection
4. Property Selection
5. Amount
6. Description
7. Payment Method
8. File Upload
9. Submit Button
```

---

### 5. URL Routes (urls.py)

**Location**: [main/urls.py](main/urls.py#L40)

**New Routes**:
```python
path('api/unpaid-invoices/', views.get_unpaid_invoices, name='get_unpaid_invoices'),
```

**Existing Routes** (unchanged):
```python
path('report_payment', views.report_payments, name='report_payment'),  # Used by both flows
```

---

## How It Works: Step-by-Step

### For Owners:

1. **Click "Registrar Pago"** in properties dashboard
2. **Select Rent** from dropdown
3. **AJAX request** fetches unpaid invoices for selected rent
4. **Select Invoice** from dropdown
5. **View Balance Owed** including late fees
6. **Enter Amount** (auto-filled, can be edited)
7. **Enter Payment Date**
8. **Select Payment Method**
9. **Optional: Add Description**
10. **Optional: Enable "Send Receipt"** (checked by default)
11. **Submit Form**
12. **Payment Created** with status='confirmed' (no extra step!)
13. **Receipt Sent** to tenant (if enabled)
14. **Success Message** and redirect to properties

### For Tenants:

1. **Click "Registrar Pago"** (same link, but shows tenant form)
2. **Select Rent** from their rented properties
3. **Select Property**
4. **Enter Amount**
5. **Add Description** (optional)
6. **Select Payment Method**
7. **Optional: Upload Confirmation** (bank statement, receipt, etc.)
8. **Submit Form**
9. **Payment Status**: pending
10. **Email Sent** to owner with confirmation link
11. **Owner Reviews** and clicks confirm/reject
12. **Upon Confirmation**: Receipt sent to tenant

---

## Database/Model Integration

### Payment Model Usage:
- ✅ Creates `Payment` record immediately with `status='confirmed'`
- ✅ Linked to specific `Invoice` (not rent-wide)
- ✅ Linked to legacy `Transaction` for audit trail
- ✅ Signal handler auto-updates `Invoice` status

### Transaction Model (Legacy):
- ✅ Still created for backward compatibility
- ✅ Marked with `is_legacy_only=True`
- ✅ Used by email/receipt functions

### Invoice Model:
- ✅ Auto-updated via signal when Payment confirmed
- ✅ `paid_amount` recalculated from all confirmed payments
- ✅ `status` updated based on payment coverage
- ✅ `late_fee_amount` displayed to owner

---

## Key Differences from Previous Implementation

| Aspect | Old | New |
|--------|-----|-----|
| **Owner Payment Flow** | N/A | Dedicated form with invoice selection |
| **Payment Confirmation** | Owner manual | Automatic ('confirmed' on creation) |
| **Invoice Selection** | Not available | Invoice dropdown with balance display |
| **Receipt Sending** | On confirm_payment | Immediate or optional |
| **Form Complexity** | Single form (tenant-centric) | Role-specific forms in one template |
| **Status Tracking** | Invoice-level | Both Invoice and Payment models |

---

## Context Variables Passed to Template

```python
{
    'form': <OwnerPaymentForm or ReportPaymentForm>,
    'user_role': 'O' or 'T',
    'transactions': Transaction.objects.filter(owner=request.user)  # For tenant display
}
```

---

## Error Handling

### Owner Form Validation:
- ✅ Amount > balance_owed: Form error
- ✅ Unauthorized invoice access: Error message, form redisplayed
- ✅ AJAX request fails: Console error, user-friendly message
- ✅ Invoice/rent not found: 404 response

### Tenant Form Validation:
- ✅ Same as existing implementation
- ✅ Missing owner: Error message
- ✅ Transaction save failure: Error handling with logging

---

## JavaScript Functionality

**Owner Form Script**:
```javascript
- Event listener on rent dropdown
- Fetch AJAX endpoint on rent change
- Populate invoice dropdown dynamically
- Update balance display on invoice change
- Auto-fill amount field
- Show/hide late fee information
```

**Error Handling**:
```javascript
- Catch network errors
- Log to console
- Show user-friendly error message
```

---

## Testing Checklist

### Owner Flow:
- [ ] Owner sees OwnerPaymentForm (not ReportPaymentForm)
- [ ] Rent dropdown loads owner's active rents
- [ ] Selecting rent triggers AJAX fetch
- [ ] Invoice dropdown populates with unpaid invoices
- [ ] Balance display shows correct amount + late fees
- [ ] Amount field auto-fills with balance
- [ ] Amount validation prevents overpayment
- [ ] Form submission creates Payment with 'confirmed' status
- [ ] Legacy Transaction created for audit trail
- [ ] Invoice status updates automatically (via signal)
- [ ] Receipt sent to tenant when checkbox enabled
- [ ] Success message displayed
- [ ] Redirect to properties page

### Tenant Flow:
- [ ] Tenant sees ReportPaymentForm (not OwnerPaymentForm)
- [ ] Rent dropdown loads tenant's rented properties
- [ ] Property dropdown populated correctly
- [ ] Form submission creates Transaction with 'pending' status
- [ ] Email sent to owner with confirmation link
- [ ] Owner can confirm/reject payment
- [ ] Receipt sent upon confirmation

### Integration:
- [ ] Both flows use same URL (report_payment)
- [ ] No errors in Django logs
- [ ] CSRF token working for AJAX request
- [ ] Mobile responsive design
- [ ] Spanish labels and messages displayed correctly

---

## Files Modified

1. **[main/forms.py](main/forms.py)**
   - Added imports: `Invoice, Payment, Decimal`
   - Added `OwnerPaymentForm` class

2. **[main/views.py](main/views.py)**
   - Updated `report_payments()` view with role-based logic
   - Added `get_unpaid_invoices()` AJAX endpoint

3. **[main/urls.py](main/urls.py)**
   - Added URL route for `get_unpaid_invoices`

4. **[main/templates/main/report_payment.html](main/templates/main/report_payment.html)**
   - Complete redesign with role-conditional rendering
   - Added JavaScript for invoice filtering and balance display

---

## Navigation

The existing "Registrar Pago" button in [main/templates/main/properties.html](main/templates/main/properties.html#L251) already points to the correct URL:
```html
<a href="{% url 'report_payment' %}">Registrar Pago</a>
```

This URL now intelligently shows:
- **For Owners**: New invoice-based payment form with immediate confirmation
- **For Tenants**: Traditional payment reporting form requiring owner confirmation

---

## Benefits of This Implementation

✅ **Single Integration Point**: One URL handles both flows  
✅ **Role-Based UX**: Each user sees only relevant form  
✅ **Simplified for Owners**: No confirmation step needed  
✅ **Invoice-Level Control**: Owners select specific invoices to pay  
✅ **Immediate Confirmation**: Payments confirmed on creation  
✅ **Optional Receipt**: Owners can choose to send receipt immediately  
✅ **Backward Compatible**: Tenant flow unchanged  
✅ **Audit Trail**: Legacy transactions preserved  
✅ **Real-Time Balance**: Shows unpaid amount including late fees  
✅ **AJAX Filtering**: Dynamic invoice selection without page reload  

---

## Future Enhancements

- [ ] Bulk payment registration (multiple invoices)
- [ ] Payment templates for recurring payments
- [ ] Payment history per invoice
- [ ] Email receipt with payment details
- [ ] SMS notification to tenant
- [ ] Payment partial allocation logic
- [ ] Late fee appeal workflow

---

## Support Notes

**Issue**: Invoice dropdown empty after selecting rent  
**Solution**: Check Celery task `generate_invoices` has run, verify rent has unpaid invoices

**Issue**: Receipt not sent to tenant  
**Solution**: Verify `send_receipt` checkbox enabled, check Mailgun configuration

**Issue**: AJAX request fails  
**Solution**: Check browser console, verify CSRF token, check Django logs
