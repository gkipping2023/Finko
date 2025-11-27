from django.forms import ModelForm, ModelChoiceField
from .models import PLAN_CHOICES, User,Properties,Transaction, Rent, ID_Type, Sex, payment_method
from django.contrib.auth.forms import UserCreationForm
from django import forms
from django_countries.fields import CountryField
from .form_mixins import CustomizableFormMixin, BaseCustomModelForm, BaseCustomUserCreationForm
from datetime import timedelta

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
    dob = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    promo_code = forms.CharField(max_length=20, required=False)
    
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'id_type','role','personal_id', 'nac', 'dob', 'sex', 'promo_code']

    def __init__(self, *args, **kwargs):
        user = kwargs.get('instance', None)  # Get the user instance passed to the form
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'  # Add the form-control class to all fields

        # Disable the promo_code field if the user already has a promo code
        if user and user.promo_code:
            self.fields['promo_code'].widget = forms.HiddenInput()  # Hide the field


class AddPropertyForm(BaseCustomModelForm):
    class Meta:
        model = Properties
        fields = '__all__'
        exclude = ['maint_status','available','owner','size','bedrooms','bathrooms']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'  # Add the form-control class to all fields

    def save(self, commit=True, user=None):
        property_instance = super().save(commit=False)
        if user:  # Assign the current user as the owner
            property_instance.owner = user
        if commit:
            property_instance.save()
        return property_instance

# class NewRentForm(forms.ModelForm):
#     start_date = forms.DateField(widget=forms.DateInput(attrs={'type':'date','id':'id_start_date'}))
#     end_date = forms.DateField(widget=forms.DateInput(attrs={'type':'date','id':'id_end_date'}))
#     next_invoice_date = forms.DateField(widget=forms.DateInput(attrs={'type':'date','id':'id_next_invoice_date'}))
    
#     class Meta:
#         model = Rent
#         fields = '__all__'
#         exclude = ['property','tenant','owner','status','is_active']

#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         for field_name, field in self.fields.items():
#             field.widget.attrs['class'] = 'form-control'  # Add the form-control class to all fields

#     def clean(self):
#         cleaned_data = super().clean()
#         start_date = cleaned_data.get('start_date')
#         next_invoice_date = cleaned_data.get('next_invoice_date')

#         # If next_invoice_date is not provided, set it to 30 days from start_date
#         if start_date and not next_invoice_date:
#             cleaned_data['next_invoice_date'] = start_date + timedelta(days=30)

#         return cleaned_data

#     def save(self, commit=True, user=None):
#         property_instance = super().save(commit=False)
#         if user:  # Assign the current user as the owner
#             property_instance.owner = user
#         if commit:
#             property_instance.save()
#         return property_instance

class NewRentForm(BaseCustomModelForm):
    start_date = forms.DateField(widget=forms.DateInput(attrs={'type':'date', 'class':'form-control'}))
    end_date = forms.DateField(widget=forms.DateInput(attrs={'type':'date', 'class':'form-control'}))
    next_invoice_date = forms.DateField(widget=forms.DateInput(attrs={'type':'date', 'class':'form-control'}), required=False)

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
            'unregistered_tenant_name', 'unregistered_tenant_email', 'unregistered_tenant_phone',
            'unregistered_tenant_id_type', 'unregistered_tenant_personal_id',
            'unregistered_tenant_dob', 'unregistered_tenant_nac', 'unregistered_tenant_sex',
        ]
        exclude = ['property', 'owner', 'status', 'is_active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tenant'].required = False  # Make tenant optional for unregistered tenants
        for field_name, field in self.fields.items():
            if not hasattr(field.widget, 'input_type') or field.widget.input_type != 'hidden':
                field.widget.attrs['class'] = 'form-control'

    def clean(self):
        cleaned_data = super().clean()
        tenant = cleaned_data.get('tenant')
        name = cleaned_data.get('unregistered_tenant_name')
        email = cleaned_data.get('unregistered_tenant_email')

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

        # Set next_invoice_date if not provided
        start_date = cleaned_data.get('start_date')
        next_invoice_date = cleaned_data.get('next_invoice_date')
        if start_date and not next_invoice_date:
            cleaned_data['next_invoice_date'] = start_date + timedelta(days=365/12)

        return cleaned_data

    def save(self, commit=True, user=None, property_instance=None):
        rent = super().save(commit=False)
        if user:
            rent.owner = user
        if property_instance:
            rent.property = property_instance
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

class TransactionForm(BaseCustomModelForm):
    class Meta:
        model = Transaction
        fields = ['transaction_date','type','rent','tenant', 'property', 'amount', 'description', 'payment_method','confirmation_file']
        widgets = {
            'transaction_date': forms.DateTimeInput(attrs={'type': 'date', 'class': 'form-control'}),
            'type': forms.Select(attrs={'class': 'form-control'}),
            'rent': forms.Select(attrs={'class': 'form-control'}),
            'tenant': forms.Select(attrs={'class': 'form-control'}),
            'property': forms.Select(attrs={'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'payment_method': forms.Select(attrs={'class': 'form-control'}),
            'confirmation_file': forms.ClearableFileInput(attrs={'class': 'form-control-file'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)  # Get the current user from the view
        super().__init__(*args, **kwargs)
        if user:
            # Filter tenants associated with the current user
            self.fields['tenant'].queryset = User.objects.filter(role='T', tenant_rents__owner=user).distinct()

            # Filter properties owned by the current user
            self.fields['property'].queryset = Properties.objects.filter(owner=user)

            # Filter rents associated with the current user
            self.fields['rent'].queryset = Rent.objects.filter(owner=user,is_active=True)

class ReportPaymentForm(BaseCustomModelForm):
    # Add confirmation_file as a separate field that won't be saved to the model
    confirmation_file = forms.FileField(
        required=False, 
        widget=forms.ClearableFileInput(attrs={'class': 'form-control-file'})
    )
    
    class Meta:
        model = Transaction
        fields = ['transaction_date','type','rent','tenant', 'property', 'amount', 'description', 'payment_method','confirmation_file']
        widgets = {
            'transaction_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'type': forms.Select(attrs={'class': 'form-control'}),
            'rent': forms.Select(attrs={'class': 'form-control'}),
            'tenant': forms.HiddenInput(),  # Hide tenant field
            'property': forms.Select(attrs={'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'payment_method': forms.Select(attrs={'class': 'form-control'}),
            'confirmation_file': forms.ClearableFileInput(attrs={'class': 'form-control-file'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)  # Get the current user from the view
        super().__init__(*args, **kwargs)
        if user:
            self.fields['tenant'].queryset = User.objects.filter(id=user.id)
            self.fields['tenant'].initial = user.id
            rented_properties = Properties.objects.filter(rent__tenant=user).distinct()
            self.fields['property'].queryset = rented_properties
            self.fields['rent'].queryset = Rent.objects.filter(tenant=user, is_active=True)
            
            # For tenants, restrict transaction type to only "Pago"
            if user.role == 'T':  # Tenant role
                self.fields['type'].choices = [('pago', 'Pago')]
                self.fields['type'].initial = 'pago'
                self.fields['type'].widget.attrs['disabled'] = True
                self.fields['type'].widget.attrs['readonly'] = True
                self.fields['type'].required = False  # Make field not required for tenants
                # Store user role for clean method
                self._user_role = user.role
            else:
                self._user_role = user.role if user else None

    def clean(self):
        """Custom validation for the entire form"""
        cleaned_data = super().clean()
        
        # Handle type field for tenants
        if hasattr(self, '_user_role') and self._user_role == 'T':
            # For tenants, always set type to 'pago' regardless of what was submitted
            cleaned_data['type'] = 'pago'
        
        return cleaned_data

class PublicPaymentForm(forms.Form):
    """Form for public payment portal - no login required"""
    rent_number = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ej: RENT-1-5-0001'
        }),
        label='Número de Contrato'
    )
    tenant_email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'correo@ejemplo.com'
        }),
        label='Correo Electrónico'
    )
    transaction_date = forms.DateField(
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
        help_text='Sube una imagen o PDF del comprobante de pago'
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
        tenant_email = cleaned_data.get('tenant_email')
        
        if rent_number and tenant_email:
            try:
                rent = Rent.objects.get(rent_number=rent_number, is_active=True)
                # Verify email matches tenant or unregistered tenant email
                email_match = False
                if rent.tenant and rent.tenant.email == tenant_email:
                    email_match = True
                elif rent.unregistered_tenant_email == tenant_email:
                    email_match = True
                
                if not email_match:
                    raise forms.ValidationError(
                        'El correo electrónico no coincide con el inquilino de este contrato.'
                    )
            except Rent.DoesNotExist:
                pass  # Already handled in clean_rent_number
        
        return cleaned_data