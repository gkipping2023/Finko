# Payment Form Enhancement: Owner Payment Registration with Invoice Selection

## Current State Analysis

### Existing Flow
1. **Current Form** (`ReportPaymentForm`): Uses Transaction model, requires selecting rent/property/tenant
2. **Current View** (`report_payments`): Creates a pending transaction, sends email to owner to confirm
3. **Confirmation** (`confirm_payment`): Owner confirms, transaction marked as confirmed, receipt sent to tenant

### Issues with Current Approach for Owner Payments
1. **Form Complexity**: Form shows Transaction fields (rent, property, tenant, type) which are tenant-centric
2. **Status Manual**: When owner registers payment directly, it still requires confirmation step
3. **No Invoice Selection**: Owners cannot select which invoice(s) to apply payment to
4. **No Automatic Receipt**: Receipt sending is only in confirm_payment, not on initial submission

---

## Recommended Solution

### 1. Create a New Form: `OwnerPaymentForm`

**Purpose**: Dedicated form for owners to register payments they've received

**Key Features**:
- **Rent Selector**: Dropdown of owner's active rents
- **Unpaid Invoices Dropdown**: Dynamically filtered based on selected rent
- **Display Unpaid Balance**: Show total unpaid amount including late fees
- **Payment Details**: Amount, date, method, description
- **Receipt Email Toggle**: Checkbox to send receipt immediately

**Form Definition**:
```python
class OwnerPaymentForm(forms.Form):
    """
    Form for owners to register payments they've received.
    Creates Payment records with 'confirmed' status immediately.
    """
    rent = forms.ModelChoiceField(
        queryset=Rent.objects.none(),
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'id_rent'}),
        label='Seleccionar Contrato de Alquiler',
        required=True
    )
    
    invoice = forms.ModelChoiceField(
        queryset=Invoice.objects.none(),
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'id_invoice'}),
        label='Factura sin Pagar',
        required=True,
        help_text='Solo se muestran facturas pendientes, parcialmente pagadas o vencidas'
    )
    
    amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        label='Monto del Pago',
        required=True
    )
    
    payment_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label='Fecha del Pago',
        required=True
    )
    
    payment_method = forms.ChoiceField(
        choices=payment_method,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Método de Pago',
        required=True
    )
    
    description = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        label='Notas/Descripción',
        required=False
    )
    
    send_receipt = forms.BooleanField(
        required=False,
        initial=True,
        label='Enviar Recibo al Inquilino',
        help_text='Se enviará un recibo en PDF al inquilino automáticamente',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if user and user.role == 'O':  # Owner
            # Load owner's active rents
            self.fields['rent'].queryset = Rent.objects.filter(
                owner=user,
                is_active=True
            ).select_related('property', 'tenant')
            
            # Load unpaid invoices (will be filtered via AJAX in template)
            self.fields['invoice'].queryset = Invoice.objects.filter(
                status__in=['pending', 'partial', 'overdue', 'overdue_with_fee']
            ).select_related('rent').order_by('-due_date')
    
    def clean(self):
        cleaned_data = super().clean()
        invoice = cleaned_data.get('invoice')
        amount = cleaned_data.get('amount')
        
        if invoice and amount:
            # Validate amount doesn't exceed balance owed
            balance_owed = invoice.get_balance_owed()
            if amount > balance_owed:
                self.add_error('amount', f'El monto no puede ser mayor a lo adeudado (${balance_owed:.2f})')
        
        return cleaned_data
```

### 2. Create New View: `owner_register_payment`

**Purpose**: Dedicated view for owners to register and confirm payments immediately

**Key Features**:
- Validate owner has access to the rent/invoice
- Create Payment record with 'confirmed' status immediately
- Optionally send receipt to tenant
- Return to properties page with success message

**View Implementation**:
```python
@login_required(login_url='log_in')
def owner_register_payment(request):
    """
    Allows property owners to register payments they've received.
    Creates Payment records with 'confirmed' status immediately.
    Optionally sends receipt to tenant.
    """
    
    # Ensure user is owner
    if request.user.role != 'O':
        messages.error(request, "Solo propietarios pueden registrar pagos.")
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = OwnerPaymentForm(request.POST, user=request.user)
        if form.is_valid():
            try:
                invoice = form.cleaned_data['invoice']
                
                # Validate owner has access to this invoice
                if invoice.rent.owner != request.user:
                    messages.error(request, "No tienes acceso a esta factura.")
                    return render(request, 'main/owner_payment.html', {'form': form})
                
                # Create Payment record with confirmed status
                payment = Payment.objects.create(
                    invoice=invoice,
                    amount=form.cleaned_data['amount'],
                    payment_date=form.cleaned_data['payment_date'],
                    payment_method=form.cleaned_data['payment_method'],
                    description=form.cleaned_data['description'],
                    status='confirmed'  # Auto-confirm since owner registered it
                )
                
                # Signal handler will auto-update invoice
                
                # Create legacy Transaction record for audit trail
                transaction = Transaction.objects.create(
                    owner=request.user,
                    tenant=invoice.rent.tenant,
                    property=invoice.rent.property,
                    rent=invoice.rent,
                    amount=form.cleaned_data['amount'],
                    transaction_date=form.cleaned_data['payment_date'],
                    payment_method=form.cleaned_data['payment_method'],
                    type='pago',
                    description=form.cleaned_data['description'],
                    status='confirmed',
                    is_legacy_only=True
                )
                
                # Link payment to transaction for audit trail
                payment.transaction = transaction
                payment.save()
                
                # Send receipt if requested
                if form.cleaned_data['send_receipt']:
                    send_receipt_to_tenant(transaction)
                    messages.success(
                        request, 
                        f"Pago registrado por ${form.cleaned_data['amount']:.2f}. "
                        "Recibo enviado al inquilino."
                    )
                else:
                    messages.success(
                        request, 
                        f"Pago registrado por ${form.cleaned_data['amount']:.2f}."
                    )
                
                return redirect('properties')
                
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error registering owner payment: {e}")
                messages.error(request, "Error al registrar el pago. Por favor intenta de nuevo.")
                return render(request, 'main/owner_payment.html', {'form': form})
    
    else:
        form = OwnerPaymentForm(user=request.user)
    
    return render(request, 'main/owner_payment.html', {'form': form})


@login_required
@require_POST
def get_unpaid_invoices(request):
    """
    AJAX endpoint to fetch unpaid invoices for a selected rent.
    Returns JSON list of invoices with balance information.
    """
    rent_id = request.POST.get('rent_id')
    
    if not rent_id:
        return JsonResponse({'invoices': []})
    
    try:
        rent = Rent.objects.get(id=rent_id, owner=request.user)
        invoices = Invoice.objects.filter(
            rent=rent,
            status__in=['pending', 'partial', 'overdue', 'overdue_with_fee']
        ).order_by('-due_date')
        
        invoice_list = [
            {
                'id': inv.id,
                'invoice_number': inv.invoice_number,
                'due_date': inv.due_date.strftime('%Y-%m-%d'),
                'amount': str(inv.amount),
                'paid_amount': str(inv.paid_amount),
                'balance_owed': str(inv.get_balance_owed()),
                'late_fee_amount': str(inv.late_fee_amount or 0),
                'status': inv.status,
                'display': f"{inv.invoice_number} - Due: {inv.due_date} - Balance: ${inv.get_balance_owed():.2f}"
            }
            for inv in invoices
        ]
        
        return JsonResponse({'invoices': invoice_list})
    except Rent.DoesNotExist:
        return JsonResponse({'invoices': [], 'error': 'Rent not found'}, status=404)
```

### 3. Create New Template: `owner_payment.html`

**Features**:
- Display current unpaid balance
- AJAX dropdown filtering
- Clear form layout
- Submit button with receipt option

**Template Structure**:
```html
{% extends "index.html" %}
{% block content %}
<div class="container-fluid py-4">
  <div class="row justify-content-center">
    <div class="col-lg-8 col-md-10 col-12">
      <div class="card shadow border-0 mb-4">
        <div class="card-header bg-gradient-primary pb-3 border-radius-lg">
          <h4 class="text-white mb-0">Registrar Pago Recibido</h4>
          <p class="text-white-50 mb-0">Agregar un nuevo pago de tu inquilino</p>
        </div>
        <div class="card-body">
          <form method="post" id="owner-payment-form" autocomplete="off">
            {% csrf_token %}
            
            <!-- Rent Selection -->
            <div class="mb-3">
              <label class="form-label font-weight-bold text-dark">
                {{ form.rent.label }}
              </label>
              {{ form.rent }}
              {% for error in form.rent.errors %}
                <div class="text-danger small">{{ error }}</div>
              {% endfor %}
            </div>
            
            <!-- Invoice Balance Display -->
            <div class="mb-3" id="invoice-balance-display" style="display: none;">
              <div class="alert alert-info" role="alert">
                <strong>Saldo sin pagar: </strong>
                <span id="balance-amount">$0.00</span>
                <br>
                <small id="late-fee-display"></small>
              </div>
            </div>
            
            <!-- Invoice Selection -->
            <div class="mb-3">
              <label class="form-label font-weight-bold text-dark">
                {{ form.invoice.label }}
              </label>
              {{ form.invoice }}
              <small class="form-text text-muted">{{ form.invoice.help_text }}</small>
              {% for error in form.invoice.errors %}
                <div class="text-danger small">{{ error }}</div>
              {% endfor %}
            </div>
            
            <!-- Amount -->
            <div class="mb-3">
              <label class="form-label font-weight-bold text-dark">
                {{ form.amount.label }}
              </label>
              {{ form.amount }}
              {% for error in form.amount.errors %}
                <div class="text-danger small">{{ error }}</div>
              {% endfor %}
            </div>
            
            <!-- Payment Date -->
            <div class="mb-3">
              <label class="form-label font-weight-bold text-dark">
                {{ form.payment_date.label }}
              </label>
              {{ form.payment_date }}
              {% for error in form.payment_date.errors %}
                <div class="text-danger small">{{ error }}</div>
              {% endfor %}
            </div>
            
            <!-- Payment Method -->
            <div class="mb-3">
              <label class="form-label font-weight-bold text-dark">
                {{ form.payment_method.label }}
              </label>
              {{ form.payment_method }}
              {% for error in form.payment_method.errors %}
                <div class="text-danger small">{{ error }}</div>
              {% endfor %}
            </div>
            
            <!-- Description -->
            <div class="mb-3">
              <label class="form-label font-weight-bold text-dark">
                {{ form.description.label }}
              </label>
              {{ form.description }}
              {% for error in form.description.errors %}
                <div class="text-danger small">{{ error }}</div>
              {% endfor %}
            </div>
            
            <!-- Send Receipt Checkbox -->
            <div class="mb-3">
              <div class="form-check">
                {{ form.send_receipt }}
                <label class="form-check-label" for="{{ form.send_receipt.id_for_label }}">
                  {{ form.send_receipt.label }}
                </label>
              </div>
              <small class="form-text text-muted d-block mt-2">
                {{ form.send_receipt.help_text }}
              </small>
            </div>
            
            <!-- Submit Button -->
            <div class="text-center">
              <button type="submit" class="btn btn-primary bg-gradient w-50 mt-3">
                Registrar Pago
              </button>
            </div>
          </form>
          
          <div class="text-center mt-3">
            <a href="{% url 'properties' %}" class="btn btn-secondary">Volver al Panel</a>
          </div>
        </div>
      </div>
    </div>
  </div>
</div>

<script>
document.addEventListener('DOMContentLoaded', function() {
  const rentSelect = document.getElementById('id_rent');
  const invoiceSelect = document.getElementById('id_invoice');
  const balanceDisplay = document.getElementById('invoice-balance-display');
  const balanceAmount = document.getElementById('balance-amount');
  const lateFeeDisplay = document.getElementById('late-fee-display');
  const amountInput = document.getElementById('id_amount');
  
  // Fetch invoices when rent changes
  rentSelect.addEventListener('change', function() {
    const rentId = this.value;
    
    if (!rentId) {
      invoiceSelect.innerHTML = '<option value="">-- Seleccionar Factura --</option>';
      balanceDisplay.style.display = 'none';
      return;
    }
    
    // AJAX request to get unpaid invoices
    fetch('{% url "get_unpaid_invoices" %}', {
      method: 'POST',
      headers: {
        'X-CSRFToken': '{{ csrf_token }}',
        'Content-Type': 'application/x-www-form-urlencoded'
      },
      body: 'rent_id=' + rentId
    })
    .then(response => response.json())
    .then(data => {
      invoiceSelect.innerHTML = '<option value="">-- Seleccionar Factura --</option>';
      
      if (data.invoices && data.invoices.length > 0) {
        data.invoices.forEach(invoice => {
          const option = document.createElement('option');
          option.value = invoice.id;
          option.textContent = invoice.display;
          option.dataset.balanceOwed = invoice.balance_owed;
          option.dataset.lateFee = invoice.late_fee_amount;
          invoiceSelect.appendChild(option);
        });
      } else {
        const option = document.createElement('option');
        option.textContent = 'No hay facturas sin pagar';
        option.disabled = true;
        invoiceSelect.appendChild(option);
      }
    });
  });
  
  // Update balance display when invoice changes
  invoiceSelect.addEventListener('change', function() {
    const selectedOption = this.options[this.selectedIndex];
    
    if (this.value) {
      const balanceOwed = parseFloat(selectedOption.dataset.balanceOwed);
      const lateFee = parseFloat(selectedOption.dataset.lateFee);
      
      balanceAmount.textContent = '$' + balanceOwed.toFixed(2);
      
      if (lateFee > 0) {
        lateFeeDisplay.innerHTML = `<strong>Recargo por atraso:</strong> $${lateFee.toFixed(2)}`;
      } else {
        lateFeeDisplay.innerHTML = '';
      }
      
      balanceDisplay.style.display = 'block';
      amountInput.max = balanceOwed;
      amountInput.value = balanceOwed.toFixed(2);
    } else {
      balanceDisplay.style.display = 'none';
      amountInput.value = '';
    }
  });
});
</script>
{% endblock %}
```

### 4. Add URL Route

```python
# In urls.py
path('owner/payment/register/', views.owner_register_payment, name='owner_register_payment'),
path('api/unpaid-invoices/', views.get_unpaid_invoices, name='get_unpaid_invoices'),
```

### 5. Update Navigation Link

```html
<!-- In properties.html or navbar -->
<a class="btn btn-primary btn-sm mb-0 me-3" href="{% url 'owner_register_payment' %}">
  Registrar Pago Recibido
</a>
```

---

## Key Benefits

✅ **Simplified for Owners**: Dedicated form showing only relevant invoices
✅ **Immediate Confirmation**: Payments confirmed automatically (no extra step)
✅ **Invoice-Level Tracking**: Select specific invoices to pay
✅ **One-Click Receipt**: Send receipt immediately on submission
✅ **Balance Visibility**: Shows unpaid balance and late fees
✅ **Backward Compatible**: Existing flow for tenants unchanged
✅ **Audit Trail**: Legacy Transaction created for historical records

---

## Implementation Steps

1. Add `OwnerPaymentForm` to [forms.py](forms.py)
2. Add views `owner_register_payment` and `get_unpaid_invoices` to [views.py](views.py)
3. Create [main/templates/main/owner_payment.html](main/templates/main/owner_payment.html)
4. Add URL routes to [urls.py](urls.py)
5. Add navigation link in properties template
6. Test with sample rent/invoice/payment flow

---

## Testing Checklist

- [ ] Owner can see only their active rents in dropdown
- [ ] Invoice dropdown filters based on selected rent
- [ ] Balance display updates when invoice changes
- [ ] Amount field auto-populates with balance owed
- [ ] Amount validation prevents overpayment
- [ ] Payment created with 'confirmed' status immediately
- [ ] Invoice status updates automatically via signal
- [ ] Receipt sent to tenant when checkbox enabled
- [ ] Tenant receives PDF receipt with correct amount
- [ ] Legacy Transaction created for audit trail
