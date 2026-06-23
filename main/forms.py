from django.forms import ModelForm, ModelChoiceField
from .models import PLAN_CHOICES, User, Properties, Rent, ID_Type, Sex, payment_method, Feedback, LATE_FEE_CHOICES, Invoice, Payment, Credit, Debit
from django.contrib.auth.forms import UserCreationForm
from django import forms
from django_countries.fields import CountryField
from .form_mixins import CustomizableFormMixin, BaseCustomModelForm, BaseCustomUserCreationForm
from datetime import timedelta
from decimal import Decimal

class NewUserForm(CustomizableFormMixin, UserCreationForm):
    first_name = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control'}))
    phone = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control','type':'number'}))
    password1 = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    password2 = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'form-control'}))
    role = forms.ChoiceField(choices=[('T', 'Inquilino'), ('O', 'Propietario')], widget=forms.Select(attrs={'class': 'form-control'}))
    
    # Data Protection Consent Fields (Ley 81)
    privacy_policy_accepted = forms.BooleanField(
        required=True,
        label='He leído y acepto la Política de Privacidad',
        error_messages={'required': 'Debe aceptar la Política de Privacidad para continuar'},
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    terms_accepted = forms.BooleanField(
        required=True,
        label='He leído y acepto los Términos y Condiciones',
        error_messages={'required': 'Debe aceptar los Términos y Condiciones para continuar'},
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    marketing_consent = forms.BooleanField(
        required=False,
        label='Acepto recibir comunicaciones de marketing por correo electrónico',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Remove default help texts
        self.fields['password1'].help_text = None
        self.fields['password2'].help_text = None

    class Meta:
        model = User
        fields = ['first_name','last_name','phone','email','role','privacy_policy_accepted','terms_accepted','marketing_consent']
        widgets = {
            'role': forms.Select(attrs={'class': 'form-control'}),
        }
    
    def save(self, commit=True):
        user = super().save(commit=False)
        
        # Record consent timestamps
        from django.utils import timezone
        if self.cleaned_data['privacy_policy_accepted']:
            user.privacy_policy_accepted_date = timezone.now()
        if self.cleaned_data['terms_accepted']:
            user.terms_accepted_date = timezone.now()
        
        if commit:
            user.save()
        return user


class UpdateUserForm(BaseCustomModelForm):
    dob = forms.DateField(widget=forms.DateInput(attrs={'type': 'date', 'class':'form-control'}))
    promo_code = forms.CharField(max_length=20, required=False)
    
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'id_type','role','personal_id', 'nac', 'dob', 'sex', 'promo_code']

    def __init__(self, *args, **kwargs):
        user = kwargs.get('instance', None)  # Get the user instance passed to the form
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'  # Add the form-control class to all fields

        # Hide the role field - users shouldn't change their role after sign up
        self.fields['role'].widget = forms.HiddenInput()
        self.fields['role'].required = False  # Make it not required since it's hidden

        # Disable the promo_code field if the user already has a promo code
        if user and user.promo_code:
            self.fields['promo_code'].widget = forms.HiddenInput()  # Hide the field


class NotificationPreferencesForm(BaseCustomModelForm):
    """Form for managing user email notification preferences"""
    
    class Meta:
        model = User
        fields = [
            'notify_invoice_generated',
            'notify_invoice_summary',
            'notify_late_fee_applied',
            'notify_payment_confirmed',
            'notify_payment_received',
            'notify_lease_renewal',
            'notify_maintenance',
            'notify_property_alerts',
        ]
        widgets = {
            'notify_invoice_generated': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notify_invoice_summary': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notify_late_fee_applied': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notify_payment_confirmed': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notify_payment_received': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notify_lease_renewal': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notify_maintenance': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notify_property_alerts': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add help text for each field
        self.fields['notify_invoice_generated'].label = 'Notificaciones de Facturas'
        self.fields['notify_invoice_generated'].help_text = 'Recibe notificaciones cuando se generen nuevas facturas de renta'
        
        self.fields['notify_invoice_summary'].label = 'Resumen de Facturas'
        self.fields['notify_invoice_summary'].help_text = 'Recibe un resumen diario de facturas generadas'
        
        self.fields['notify_late_fee_applied'].label = 'Alertas de Recargos'
        self.fields['notify_late_fee_applied'].help_text = 'Recibe alertas cuando se apliquen recargos por mora'
        
        self.fields['notify_payment_confirmed'].label = 'Confirmación de Pagos'
        self.fields['notify_payment_confirmed'].help_text = 'Recibe confirmación cuando se registren pagos'
        
        self.fields['notify_payment_received'].label = 'Pagos Recibidos'
        self.fields['notify_payment_received'].help_text = 'Recibe notificación cuando se reciban pagos de inquilinos'
        
        self.fields['notify_lease_renewal'].label = 'Renovación de Contrato'
        self.fields['notify_lease_renewal'].help_text = 'Recibe recordatorios de renovación de contratos'
        
        self.fields['notify_maintenance'].label = 'Alertas de Mantenimiento'
        self.fields['notify_maintenance'].help_text = 'Recibe notificaciones de solicitudes de mantenimiento'
        
        self.fields['notify_property_alerts'].label = 'Alertas de Propiedad'
        self.fields['notify_property_alerts'].help_text = 'Recibe alertas generales sobre las propiedades'


class AddPropertyForm(BaseCustomModelForm):
    class Meta:
        model = Properties
        fields = '__all__'
        exclude = ['maint_status','available','owner','size','bedrooms','bathrooms']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make monthly_pmt and maint_fee explicitly optional
        if 'monthly_pmt' in self.fields:
            self.fields['monthly_pmt'].required = False
        if 'maint_fee' in self.fields:
            self.fields['maint_fee'].required = False
        
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'  # Add the form-control class to all fields

    def save(self, commit=True, user=None):
        property_instance = super().save(commit=False)
        if user:  # Assign the current user as the owner
            property_instance.owner = user
        if commit:
            property_instance.save()
        return property_instance


class NewRentForm(BaseCustomModelForm):
    start_date = forms.DateField(widget=forms.DateInput(attrs={'type':'date', 'class':'form-control','id': 'id_start_date'}))
    end_date = forms.DateField(widget=forms.DateInput(attrs={'type':'date', 'class':'form-control','id': 'id_end_date'}))
    next_invoice_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        required=False,
        help_text='Fecha en que se generará la primera factura. El vencimiento será 30 días después. Las siguientes facturas se generarán automáticamente cada 30 días.'
    )
    late_fee_type = forms.ChoiceField(
        choices=LATE_FEE_CHOICES,
        widget=forms.HiddenInput(),
        initial='none',
        label='Formato de Recargo por Mora'
    )
    late_fee_amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ingresa la cantidad fija'}),
        label='Cantidad Fija de Recargo por Mora'
    )
    late_fee_grace_days = forms.IntegerField(
        initial=5,
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '5', 'min': '0', 'max': '30'}),
        label='Días de Gracia (antes del recargo)',
        help_text='Días después del vencimiento antes de aplicar recargo'
    )

    # Unregistered tenant fields
    unregistered_tenant_name = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    unregistered_tenant_email = forms.EmailField(required=False, widget=forms.EmailInput(attrs={'class': 'form-control'}))
    unregistered_tenant_phone = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    unregistered_tenant_id_type = forms.ChoiceField(choices=ID_Type, required=False, widget=forms.Select(attrs={'class': 'form-control'}))
    unregistered_tenant_personal_id = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    unregistered_tenant_dob = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}))
    unregistered_tenant_nac = CountryField(blank=True).formfield(required=False, widget=forms.Select(attrs={'class': 'form-control'}))
    unregistered_tenant_sex = forms.ChoiceField(choices=Sex, required=False, widget=forms.Select(attrs={'class': 'form-control'}))

    class Meta:
        model = Rent
        fields = [
            'tenant',  # Registered tenant (optional)
            'start_date', 'end_date', 'rent_amount', 'rent_due_date', 'next_invoice_date',
            'late_fee_type', 'late_fee_amount', 'late_fee_grace_days',
            'unregistered_tenant_name', 'unregistered_tenant_email', 'unregistered_tenant_phone',
            'unregistered_tenant_id_type', 'unregistered_tenant_personal_id',
            'unregistered_tenant_dob', 'unregistered_tenant_nac', 'unregistered_tenant_sex',
        ]
        exclude = ['property', 'owner', 'status', 'is_active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tenant'].required = False  # Make tenant optional for unregistered tenants
        self.fields['late_fee_amount'].required = False  # Not required for percentage-based fees
        for field_name, field in self.fields.items():
            if field_name not in ['late_fee_type', 'late_fee_amount']:  # Don't apply form-control to radio buttons or hidden fields
                if not hasattr(field.widget, 'input_type') or field.widget.input_type != 'hidden':
                    if not isinstance(field.widget, forms.RadioSelect):
                        field.widget.attrs['class'] = 'form-control'

    def clean(self):
        cleaned_data = super().clean()
        tenant = cleaned_data.get('tenant')
        name = cleaned_data.get('unregistered_tenant_name')
        email = cleaned_data.get('unregistered_tenant_email')
        late_fee_type = cleaned_data.get('late_fee_type')
        late_fee_amount = cleaned_data.get('late_fee_amount')
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')

        # Check if EITHER registered tenant OR both unregistered fields are provided
        has_registered_tenant = tenant is not None
        has_unregistered_tenant = name and email

        if not has_registered_tenant and not has_unregistered_tenant:
            raise forms.ValidationError(
                "Por favor selecciona un inquilino registrado o ingresa el nombre y correo de un inquilino no registrado."
            )

        # If both are provided, show error
        if has_unregistered_tenant and has_registered_tenant:
            raise forms.ValidationError(
                "Por favor selecciona solo una opción: inquilino registrado O inquilino no registrado."
            )

        # Validate late_fee_amount is provided when fixed_amount is selected
        if late_fee_type == 'fixed_amount' and not late_fee_amount:
            raise forms.ValidationError(
                "Por favor ingresa una cantidad fija para la tarifa de mora."
            )

        # Validate next_invoice_date is not before start_date
        next_invoice_date = cleaned_data.get('next_invoice_date')
        if next_invoice_date and start_date and next_invoice_date < start_date:
            self.add_error(
                'next_invoice_date',
                "La fecha de primera factura no puede ser anterior a la fecha de inicio del contrato."
            )

        return cleaned_data

    def save(self, commit=True, user=None, property_instance=None):
        rent = super().save(commit=False)
        if user:
            rent.owner = user
        if property_instance:
            rent.property = property_instance
        
        # Default next_invoice_date to start_date if not explicitly provided
        if not self.cleaned_data.get('next_invoice_date'):
            rent.next_invoice_date = self.cleaned_data.get('start_date')
        
        if commit:
            rent.save()
        return rent

class RenewLeaseForm(BaseCustomModelForm):
    start_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}))
    end_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}))
    rent_amount = forms.DecimalField(widget=forms.NumberInput(attrs={'class': 'form-control'}))

    class Meta:
        model = Rent
        fields = ['start_date', 'end_date', 'rent_amount']

class NewTenantForm(BaseCustomModelForm):
    dob = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    phone = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control', 'type': 'number'}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'form-control'}))
    role = forms.ChoiceField(
        choices=[('T', 'Inquilino')],  # Only allow the role "Inquilino" for this form
        widget=forms.Select(attrs={'class': 'form-control'}),
        initial='T'
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'phone', 'email', 'personal_id', 'id_type', 'nac', 'dob', 'sex', 'role']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'personal_id': forms.TextInput(attrs={'class': 'form-control'}),
            'id_type': forms.Select(attrs={'class': 'form-control'}),
            'nac': forms.Select(attrs={'class': 'form-control'}),
            'dob': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'sex': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['role'].disabled = True  # Disable the role field to ensure it is always "Inquilino"

class OwnerPaymentForm(forms.Form):
    """
    Form for owners to register payments they've received.
    Creates Payment records with 'confirmed' status immediately.
    """
    rent = forms.ModelChoiceField(
        queryset=Rent.objects.none(),
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'id_owner_rent'}),
        label='Seleccionar Contrato de Alquiler',
        required=True
    )
    
    invoice = forms.ModelChoiceField(
        queryset=Invoice.objects.none(),
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'id_owner_invoice'}),
        label='Factura sin Pagar',
        required=True,
        help_text='Solo se muestran facturas pendientes, parcialmente pagadas o vencidas'
    )
    
    amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'id': 'id_owner_amount'}),
        label='Monto del Pago',
        required=True
    )
    
    payment_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control', 'id': 'id_owner_payment_date'}),
        label='Fecha del Pago',
        required=True
    )
    
    payment_method = forms.ChoiceField(
        choices=payment_method,
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'id_owner_payment_method'}),
        label='Método de Pago',
        required=True
    )
    
    description = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'id': 'id_owner_description'}),
        label='Notas/Descripción',
        required=False
    )
    
    send_receipt = forms.BooleanField(
        required=False,
        initial=True,
        label='Enviar Recibo al Inquilino',
        help_text='Se enviará un recibo en PDF al inquilino automáticamente',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'id_owner_send_receipt'})
    )
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if user and user.role == 'O':  # Owner
            # Load owner's active rents
            self.fields['rent'].queryset = Rent.objects.filter(
                owner=user,
                is_active=True
            ).select_related('property', 'tenant').order_by('-start_date')
            
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


class PublicPaymentForm(forms.Form):
    """Form for public payment portal - no login required"""
    rent_number = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ej: REF-1-1-0001'
        }),
        label='Número de Contrato'
    )
    tenant_email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'correo@ejemplo.com'
        }),
        label='Correo Electrónico para la Confirmación',
        help_text='El correo donde se enviará la confirmación del pago reportado.'
    )
    payment_date = forms.DateField(
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        }),
        label='Fecha del Pago'
    )
    amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '0.00',
            'step': '0.01'
        }),
        label='Monto Pagado'
    )
    payment_method = forms.ChoiceField(
        choices=payment_method,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Método de Pago'
    )
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Descripción del pago (opcional)'
        }),
        label='Descripción'
    )
    confirmation_file = forms.FileField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*,.pdf'
        }),
        label='Comprobante de Pago',
        help_text='Sube una imagen o PDF del comprobante de pago (opcional)'
    )

    def clean_rent_number(self):
        rent_number = self.cleaned_data.get('rent_number')
        try:
            rent = Rent.objects.get(rent_number=rent_number, is_active=True)
            return rent_number
        except Rent.DoesNotExist:
            raise forms.ValidationError('Número de contrato no válido o inactivo.')
    
    def clean(self):
        cleaned_data = super().clean()
        rent_number = cleaned_data.get('rent_number')
        
        if rent_number:
            try:
                rent = Rent.objects.get(rent_number=rent_number, is_active=True)
                # Just verify rent exists and is active - email can be any valid address
            except Rent.DoesNotExist:
                pass  # Already handled in clean_rent_number
        
        return cleaned_data


class FeedbackForm(forms.ModelForm):
    """Form for users to submit feedback, comments, issues, and suggestions"""
    feedback_type = forms.ChoiceField(
        choices=Feedback.FEEDBACK_TYPES,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        label='Tipo de mensaje'
    )
    subject = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Asunto del mensaje'
        }),
        label='Asunto'
    )
    message = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 6,
            'placeholder': 'Describe tu comentario, problema, feedback o sugerencia...'
        }),
        label='Mensaje'
    )
    
    class Meta:
        model = Feedback
        fields = ['feedback_type', 'subject', 'message']


class TenantPaymentForm(forms.Form):
    """Form for tenants to report payments they've made (pending confirmation)."""
    rent = forms.ModelChoiceField(
        queryset=Rent.objects.none(),
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'id_tenant_rent'}),
        label='Contrato de Alquiler',
        required=True
    )
    invoice = forms.ModelChoiceField(
        queryset=Invoice.objects.none(),
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'id_tenant_invoice'}),
        label='Factura',
        required=True
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
        label='Notas',
        required=False
    )
    confirmation_file = forms.FileField(
        required=False,
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*,.pdf'}),
        label='Comprobante de Pago'
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            active_rents = Rent.objects.filter(tenant=user, is_active=True).select_related('property')
            self.fields['rent'].queryset = active_rents
            self.fields['invoice'].queryset = Invoice.objects.filter(
                rent__tenant=user,
                status__in=['pending', 'partial', 'overdue', 'overdue_with_fee']
            ).order_by('-due_date')


class CreditForm(forms.Form):
    """Form for owners to apply a credit to a rent account."""
    rent = forms.ModelChoiceField(
        queryset=Rent.objects.none(),
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Contrato de Alquiler',
        required=True
    )
    amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        label='Monto del Crédito',
        required=True
    )
    credit_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label='Fecha del Crédito',
        required=True
    )
    description = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        label='Descripción',
        required=True
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['rent'].queryset = Rent.objects.filter(owner=user, is_active=True).select_related('property', 'tenant')


class DebitForm(forms.Form):
    """Form for owners to apply a debit (charge) to a rent account."""
    rent = forms.ModelChoiceField(
        queryset=Rent.objects.none(),
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Contrato de Alquiler',
        required=True
    )
    amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        label='Monto del Cargo',
        required=True
    )
    debit_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label='Fecha del Cargo',
        required=True
    )
    description = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        label='Descripción',
        required=True
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['rent'].queryset = Rent.objects.filter(owner=user, is_active=True).select_related('property', 'tenant')

