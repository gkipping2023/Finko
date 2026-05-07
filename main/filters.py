import django_filters
from django_filters import FilterSet, ChoiceFilter, ModelChoiceFilter, DateFromToRangeFilter
from django import forms
from .models import Invoice, Payment, Credit, Debit, Rent, User
from .models import INVOICE_STATUS_CHOICES, PAYMENT_STATUS_CHOICES, payment_method


class DateRangeWidget(forms.MultiWidget):
    """Custom widget for date range with HTML5 date inputs."""
    def __init__(self, attrs=None):
        widgets = (
            forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control',
                'placeholder': 'Fecha inicio'
            }),
            forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control',
                'placeholder': 'Fecha fin'
            }),
        )
        super().__init__(widgets, attrs)

    def decompress(self, value):
        if value:
            return value.split(',')
        return [None, None]


class InvoiceFilter(FilterSet):
    status = ChoiceFilter(choices=INVOICE_STATUS_CHOICES, empty_label="Todos los estados")
    rent = ModelChoiceFilter(queryset=Rent.objects.none(), label="Contrato")
    invoice_date = DateFromToRangeFilter(label="Rango de fechas", widget=DateRangeWidget())

    class Meta:
        model = Invoice
        fields = ['status', 'rent', 'invoice_date']

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user is not None:
            self.filters['rent'].queryset = Rent.objects.filter(owner=user, is_active=True)


class PaymentFilter(FilterSet):
    rent = ModelChoiceFilter(queryset=Rent.objects.none(), label="Contrato")
    status = ChoiceFilter(choices=PAYMENT_STATUS_CHOICES, empty_label="Todos los estados")
    payment_method = ChoiceFilter(choices=payment_method, empty_label="Todos los métodos")
    payment_date = DateFromToRangeFilter(label="Rango de fechas", widget=DateRangeWidget())

    class Meta:
        model = Payment
        fields = ['rent', 'status', 'payment_method', 'payment_date']

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user is not None:
            self.filters['rent'].queryset = Rent.objects.filter(owner=user)


class DebitFilter(FilterSet):
    rent = ModelChoiceFilter(queryset=Rent.objects.none(), label="Contrato")
    debit_date = DateFromToRangeFilter(label="Rango de fechas", widget=DateRangeWidget())

    class Meta:
        model = Debit
        fields = ['rent', 'debit_date']

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user is not None:
            self.filters['rent'].queryset = Rent.objects.filter(owner=user)


class CreditFilter(FilterSet):
    rent = ModelChoiceFilter(queryset=Rent.objects.none(), label="Contrato")
    credit_date = DateFromToRangeFilter(label="Rango de fechas", widget=DateRangeWidget())

    class Meta:
        model = Credit
        fields = ['rent', 'credit_date']

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user is not None:
            self.filters['rent'].queryset = Rent.objects.filter(owner=user)


class AllTransactionsFilter(FilterSet):
    """Filter for unified transactions view combining invoices, credits, and debits."""
    rent = ModelChoiceFilter(queryset=Rent.objects.none(), label="Contrato")
    transaction_type = ChoiceFilter(
        choices=[('all', 'Todos'), ('invoice', 'Facturas'), ('credit', 'Créditos'), ('debit', 'Cargos')],
        method='filter_transaction_type',
        initial='all',
        label="Tipo de Transacción"
    )
    invoice_date = DateFromToRangeFilter(label="Rango de fechas", widget=DateRangeWidget())

    class Meta:
        model = Invoice
        fields = ['invoice_date']

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        self.user = user
        super().__init__(*args, **kwargs)
        if user is not None:
            self.filters['rent'].queryset = Rent.objects.filter(owner=user, is_active=True)

    def filter_transaction_type(self, queryset, name, value):
        # This filter is handled in the view; placeholder here
        return queryset
