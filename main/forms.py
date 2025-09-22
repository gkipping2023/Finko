from django.forms import ModelForm, ModelChoiceField
from .models import PLAN_CHOICES, User,Properties,Transaction, Rent, ID_Type, Sex
from django.contrib.auth.forms import UserCreationForm
from django import forms
from django_countries.fields import CountryField
#from crispy_forms.helper import FormHelper
from datetime import timedelta

class NewUserForm(UserCreationForm):
    first_name = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First Name'}))
    last_name = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last Name'}))
    phone = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control','type':'number', 'placeholder': 'Telefono'}))
    password1 = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password'}))
    password2 = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password Confirmation'}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'form-control','placeholder': 'E-mail'}))
    role = forms.ChoiceField(choices=[('T', 'Inquilino'), ('P', 'Propietario')], widget=forms.Select(attrs={'class': 'form-control', 'placeholder': 'Eres Inquilino o Propietario?'}))
    #role = forms.ChoiceField(widget=forms.Select(attrs={'class': 'form-control'}))
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].label = 'Password'
        self.fields['password2'].label = 'Password Confirmation'
        self.fields['first_name'].label = 'First Name'
        self.fields['last_name'].label = 'Last Name'
        self.fields['phone'].label = 'Telefono'
        self.fields['email'].label = 'E-mail'
        self.fields['role'].label = 'Eres Inquilino o Propietario?'

        self.fields['password1'].help_text = None
        self.fields['password2'].help_text = None


    class Meta:
        model = User
        fields = ['first_name','last_name','phone','email','role']
        widgets = {
            'role': forms.Select(attrs={'class': 'form-control'}),
        }

class UpdateUserForm(ModelForm):
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


class AddPropertyForm(ModelForm):
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

class NewRentForm(forms.ModelForm):
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

        # Require either a registered tenant or unregistered tenant info (name and email)
        if not tenant and not (name and email):
            raise forms.ValidationError("Please select a registered tenant or enter name and email for an unregistered tenant.")

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

class RenewLeaseForm(forms.ModelForm):
    start_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}))
    end_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}))
    rent_amount = forms.DecimalField(widget=forms.NumberInput(attrs={'class': 'form-control'}))

    class Meta:
        model = Rent
        fields = ['start_date', 'end_date', 'rent_amount']
        # Add other fields if you want them editable

class NewTenantForm(forms.ModelForm):
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

class TransactionForm(forms.ModelForm):
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

class ReportPaymentForm(forms.ModelForm):
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
            self.fields['rent'].queryset = Rent.objects.filter(tenant=user)