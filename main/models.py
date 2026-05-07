from django.db import models
from django.contrib.auth.models import AbstractUser
from django_countries.fields import CountryField
from django_countries import countries
from django.db.models import Max
from datetime import datetime
from decimal import Decimal
import uuid

# Create your models lists here.

ID_Type = (
    ('cedula','Cédula'),
    ('pasaporte','Pasaporte')
)

PLAN_CHOICES = (
    ('free', 'Gratis/Básico'),
    ('standard', 'Estándar'),
    ('enterprise', 'Empresarial'),
)

payment_method = (
    ('ach_yappy','ACH o Yappy'),
    ('cash','Efectivo'),
    ('other','Otros')
)

Sex = (
    ('M','Hombre'),
    ('F','Mujer'),
    ('O','Otro')
)

Roles = (
    ('O','Propietario'),
    ('T','Inquilino')
)

Category = (
    ('apartment','Apartamento'),
    ('house','Casa'),
    ('loft','Loft'),
    ('comercial','Local'),
    ('other','Otros')
)

Duration_of_Lease = (
    ('3','3 meses'),
    ('6','6 meses'),
    ('12','12 meses'),
    ('18','18 meses'),
    ('24','24 meses')
)

LATE_FEE_CHOICES = (
    ('none', 'Ninguno'),
    ('10_percent', '10%'),
    ('20_percent', '20%'),
    ('fixed_amount', 'Cantidad Fija'),
)

INVOICE_STATUS_CHOICES = (
    ('pending', 'Pendiente'),
    ('partial', 'Parcialmente Pagado'),
    ('paid', 'Pagado'),
    ('overdue', 'Vencido'),
    ('overdue_with_fee', 'Vencido con Recargo'),
)

PAYMENT_STATUS_CHOICES = (
    ('pending', 'Pendiente'),
    ('confirmed', 'Confirmado'),
    ('rejected', 'Rechazado'),
)

Status = (
    ('available','Disponible'),
    ('no_available','No Disponible')
)

Due_Status = (
    ('good','Al Día'),
    ('late','Atrasado'),
    ('partial','Parcial')
)

maint_status = (
    ('cleared','Ninguno'),
    ('requested','Solicitado'),
    ('asignado','Asignado'),
    ('in_progress','En Progreso'),
    ('finished', 'Terminado')
)

#<<<--- Models --->>>>

# class Tenant(models.Model):
#     first_name = models.CharField(max_length=250)
#     last_name = models.CharField(max_length=250)
#     full_name = models.CharField(max_length=250,blank=True,null=False)
#     phone = models.CharField(blank=False,max_length=25,default='9999-9999')
#     email = models.EmailField(unique=True,max_length=250)
#     personal_id = models.CharField(unique=True,max_length=250)
#     id_type = models.CharField(choices=ID_Type,max_length=100)
#     nac = CountryField()
#     dob = models.DateField(default='1900-01-01')
#     sex = models.CharField(choices=Sex,max_length=100)
    

#     # Convert country code to full country name before saving.
#     def save(self, *args, **kwargs):
#         if self.nac:  # Ensure country is selected
#             self.nac = dict(countries).get(self.nac.code, self.nac)  
#         super().save(*args, **kwargs)
    
#     def __str__(self):
#         return str(self.full_name)

class PromoCode(models.Model):
    code = models.CharField(max_length=50, unique=True)
    discount_percent = models.PositiveIntegerField(default=0)
    active = models.BooleanField(default=True)
    expires_at = models.DateField(null=True, blank=True)

    def __str__(self):
        return self.code

class User(AbstractUser):
    first_name = models.CharField(max_length=250)
    last_name = models.CharField(max_length=250)
    full_name = models.CharField(max_length=250)
    phone = models.CharField(blank=False,max_length=25,default='9999-9999')
    email = models.EmailField(unique=True,max_length=250,blank=False)
    personal_id = models.CharField(max_length=250)
    id_type = models.CharField(choices=ID_Type,max_length=100)
    nac = CountryField()
    dob = models.DateField(default='1900-01-01')
    sex = models.CharField(choices=Sex,max_length=100)
    role = models.CharField(choices=Roles,max_length=100,default='T')
    plan = models.CharField(choices=PLAN_CHOICES, max_length=20, default='free')
    promo_code = models.CharField(max_length=20, blank=True, null=True)
    username = models.CharField(unique=False,max_length=250)
    #stripe
    stripe_customer_id = models.CharField(max_length=255, blank=True, null=True)
    stripe_subscription_id = models.CharField(max_length=255, blank=True, null=True)
    plan = models.CharField(choices=PLAN_CHOICES, max_length=20, default='free')
    
    # Data Protection Fields (Ley 81 Compliance)
    privacy_policy_accepted = models.BooleanField(default=False, verbose_name="Política de Privacidad Aceptada")
    privacy_policy_accepted_date = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de Aceptación de Privacidad")
    terms_accepted = models.BooleanField(default=False, verbose_name="Términos y Condiciones Aceptados")
    terms_accepted_date = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de Aceptación de Términos")
    marketing_consent = models.BooleanField(default=False, verbose_name="Consentimiento de Marketing")
    data_retention_consent = models.BooleanField(default=True, verbose_name="Consentimiento de Retención de Datos")
    last_privacy_update = models.DateTimeField(auto_now=True, verbose_name="Última Actualización de Privacidad")
    data_deletion_requested = models.BooleanField(default=False, verbose_name="Eliminación de Datos Solicitada")
    data_deletion_request_date = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de Solicitud de Eliminación")
    role_confirmed = models.BooleanField(default=False, verbose_name="Rol Confirmado")

    # Convert country code to full country name before saving.
    def save(self, *args, **kwargs):
        # if self.nac:  # Ensure country is selected
        #     self.nac = dict(countries).get(self.nac.code, self.nac)  
        super().save(*args, **kwargs)
    
    def __str__(self):
        return str(self.full_name)
    
    
    USERNAME_FIELD = 'email'
    EMAIL_FIELD = 'email'
    REQUIRED_FIELDS = ['username']
    
    def __str__(self):
        return self.full_name
    
class Properties(models.Model):
    owner = models.ForeignKey(User,on_delete=models.CASCADE,max_length=20,null=True)
    alias = models.CharField(max_length=100)
    location = models.CharField(max_length=100)
    category = models.CharField(choices=Category,max_length=100)
    size = models.DecimalField(decimal_places=2,max_digits=10, null=True, blank=True)
    bedrooms = models.IntegerField(null=True, blank=True)
    bathrooms = models.IntegerField(null=True, blank=True)
    description = models.TextField(max_length=250)
    monthly_pmt = models.DecimalField(decimal_places=2,max_digits=10,null=True, blank=True,default=0.00) #Pago mensual BANCO
    maint_fee = models.DecimalField(decimal_places=2,max_digits=10,null=True, blank=True,default=0.00) #Cuota de mantenimiento
    # photo = models.ImageField()
    maint_status = models.CharField(choices=maint_status,max_length=100,default='cleared')
    available = models.BooleanField(default=True)

    def __str__(self):
        return self.alias
    
class Rent(models.Model):
    owner = models.ForeignKey(User,on_delete=models.CASCADE,max_length=20,null=True,limit_choices_to={'role': 'O'},related_name='owner_rents')
    tenant = models.ForeignKey(User, on_delete=models.CASCADE,max_length=20,null=True,limit_choices_to={'role': 'T'},related_name='tenant_rents')
    property = models.ForeignKey(Properties, on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    rent_amount = models.DecimalField(max_digits=10, decimal_places=2)
    rent_due_date = models.IntegerField(choices=[(i, str(i)) for i in range(1, 32)],default=1)  # Date when the rent is due
    next_invoice_date = models.DateField(null=True, blank=True)
    status = models.BooleanField(default=True) #MOROSIDAD cambiaremos a dias de morosidad.
    is_active = models.BooleanField(default=True) #Activo o inactivo
    rent_number = models.CharField(max_length=100, unique=True, editable=False, null=True, blank=True)  # Unique rent identifier
    rent_sequence_number = models.PositiveIntegerField(editable=False, null=True, blank=True)
    unregistered_tenant_name = models.CharField(max_length=250, blank=True, null=True)
    unregistered_tenant_email = models.EmailField(max_length=250, blank=True, null=True)
    unregistered_tenant_phone = models.CharField(max_length=25, blank=True, null=True)
    unregistered_tenant_id_type =models.CharField(choices=ID_Type,max_length=100,null=True, blank=True)
    unregistered_tenant_personal_id = models.CharField(max_length=250, blank=True, null=True)
    unregistered_tenant_dob = models.DateField(blank=True, null=True)
    unregistered_tenant_nac = CountryField(blank=True, null=True)
    unregistered_tenant_sex = models.CharField(choices=Sex,max_length=100,null=True, blank=True)
    late_fee_type = models.CharField(choices=LATE_FEE_CHOICES, max_length=20, default='none')
    late_fee_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    late_fee_grace_days = models.IntegerField(
        default=5,
        help_text="Number of days past due before late fee is applied (default: 5)"
    )

    def get_late_fee(self):
        """
        Calculate the late fee based on the late_fee_type and rent_amount.
        Returns the calculated or fixed late fee amount.
        """
        from decimal import Decimal
        
        if self.late_fee_type == 'none':
            return Decimal('0.00')
        elif self.late_fee_type == '10_percent':
            return self.rent_amount * Decimal('0.10')
        elif self.late_fee_type == '20_percent':
            return self.rent_amount * Decimal('0.20')
        elif self.late_fee_type == 'fixed_amount':
            return self.late_fee_amount or Decimal('0.00')
        return Decimal('0.00')

    def save(self, *args, **kwargs):
        if not self.pk and not self.rent_number:
            # Generate rent number for new rents
            from django.db import transaction
            with transaction.atomic():
                # Get last sequence number for this owner and property
                last_number = Rent.objects.filter(
                    owner=self.owner,
                    property=self.property
                ).aggregate(Max('rent_sequence_number'))['rent_sequence_number__max'] or 0
                self.rent_sequence_number = last_number + 1
                
                # Format: RENT-OWNER_ID-PROPERTY_ID-SEQUENCE
                padded_seq = str(self.rent_sequence_number).zfill(4)
                property_id = self.property.id if self.property else 0
                base_rent_number = f"RENT-{self.owner.id}-{property_id}-{padded_seq}"
                
                # Check for duplicates
                counter = 0
                self.rent_number = base_rent_number
                while Rent.objects.filter(rent_number=self.rent_number).exists():
                    counter += 1
                    self.rent_number = f"{base_rent_number}-{counter}"
        
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.rent_number} - {self.tenant or self.unregistered_tenant_name} - {self.property}"


class AuditLog(models.Model):
    """Track data access for Ley 81 compliance"""
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=100)  # 'view', 'edit', 'delete', 'export', 'login'
    model_name = models.CharField(max_length=50)
    object_id = models.IntegerField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    details = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['action', 'timestamp']),
        ]
    
    def __str__(self):
        return f"{self.user} - {self.action} - {self.timestamp}"


class Feedback(models.Model):
    """User feedback, comments, issues, and suggestions"""
    FEEDBACK_TYPES = (
        ('comment', 'Comentario'),
        ('feedback', 'Feedback'),
        ('issue', 'Reportar un problema'),
        ('suggestion', 'Sugerencia'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    feedback_type = models.CharField(max_length=20, choices=FEEDBACK_TYPES)
    subject = models.CharField(max_length=200)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    response = models.TextField(blank=True, null=True)
    responded_at = models.DateTimeField(blank=True, null=True)
    responded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='feedback_responses')
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.get_feedback_type_display()} - {self.subject} ({self.user.email})"


class Invoice(models.Model):
    """
    Represents a single monthly rent invoice.
    Each Rent generates one Invoice per month.
    Tracks payment status, late fees, and payment history at the invoice level.
    """
    rent = models.ForeignKey(
        Rent, 
        on_delete=models.CASCADE, 
        related_name='invoices'
    )
    
    # Invoice identification
    invoice_number = models.CharField(
        max_length=100, 
        unique=True, 
        editable=False,
        help_text="Auto-generated unique invoice identifier"
    )
    
    # Dates
    invoice_date = models.DateField(
        help_text="Date when invoice was created"
    )
    due_date = models.DateField(
        help_text="Date when payment is due"
    )
    
    # Amount tracking
    amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        help_text="Original rent amount for this invoice"
    )
    paid_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        default=0,
        help_text="Total amount paid against this invoice"
    )
    
    # Late fee tracking
    late_fee_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        default=0,
        null=True,
        blank=True,
        help_text="Late fee amount (if applicable)"
    )
    late_fee_applied_date = models.DateField(
        null=True, 
        blank=True,
        help_text="Date when late fee was applied"
    )
    
    # Status
    status = models.CharField(
        max_length=20, 
        choices=INVOICE_STATUS_CHOICES,
        default='pending'
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Public portal token (for tenant-facing payment link)
    payment_token = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True
    )
    
    class Meta:
        ordering = ['-due_date']
        indexes = [
            models.Index(fields=['rent', 'due_date']),
            models.Index(fields=['status']),
            models.Index(fields=['invoice_date']),
        ]
    
    def __str__(self):
        return f"{self.invoice_number} - {self.rent.property.alias} - ${self.amount}"
    
    def get_balance_owed(self):
        """Calculate total amount still owed (including late fee)"""
        total_owed = (self.amount - self.paid_amount) + (self.late_fee_amount or Decimal('0.00'))
        return max(total_owed, Decimal('0.00'))
    
    def get_days_overdue(self):
        """Calculate days past due date"""
        from datetime import date
        today = date.today()
        if today > self.due_date:
            return (today - self.due_date).days
        return 0
    
    def is_past_due(self):
        """Check if invoice is past due"""
        from datetime import date
        return date.today() > self.due_date
    
    def mark_paid(self):
        """Mark invoice as fully paid"""
        self.paid_amount = self.amount
        self.status = 'paid'
        self.save()
    
    def save(self, *args, **kwargs):
        """Generate invoice_number on creation"""
        if not self.pk and not self.invoice_number:
            from django.db import transaction
            from django.db.models import Max
            
            with transaction.atomic():
                # Format: INV-RENT_ID-YYYYMM-SEQUENCE
                sequence = Invoice.objects.filter(
                    rent=self.rent,
                    invoice_date=self.invoice_date
                ).count() + 1
                
                rent_id = self.rent.id
                date_str = self.invoice_date.strftime('%Y%m')
                padded_seq = str(sequence).zfill(2)
                
                self.invoice_number = f"INV-{rent_id}-{date_str}-{padded_seq}"
                
                # Check for duplicates
                counter = 0
                base = self.invoice_number
                while Invoice.objects.filter(invoice_number=self.invoice_number).exists():
                    counter += 1
                    self.invoice_number = f"{base}-{counter}"
        
        super().save(*args, **kwargs)


class Payment(models.Model):
    """
    Represents a single payment applied to an invoice.
    Links payments to specific invoices for accurate tracking.
    """
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name='payments'
    )

    # Payment identification
    payment_number = models.CharField(
        max_length=100,
        unique=True,
        editable=False,
        help_text="Auto-generated unique payment identifier"
    )

    # Payment details
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Amount paid"
    )

    # Dates
    payment_date = models.DateField(
        help_text="Date when payment was made"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    # Confirmation
    confirmed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when owner confirmed the payment"
    )

    # Payment method
    payment_method = models.CharField(
        max_length=100,
        choices=payment_method,
        help_text="How the payment was made"
    )

    # Status
    status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default='pending'
    )

    # Confirmation file (tenant upload)
    confirmation_file = models.FileField(
        upload_to='payment_confirmations/',
        null=True,
        blank=True
    )

    # Metadata
    description = models.TextField(
        max_length=250,
        blank=True,
        null=True
    )

    class Meta:
        ordering = ['-payment_date']
        indexes = [
            models.Index(fields=['invoice', 'payment_date']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.payment_number} - ${self.amount} ({self.payment_date})"

    def save(self, *args, **kwargs):
        if not self.pk and not self.payment_number:
            from django.db import transaction as db_transaction
            with db_transaction.atomic():
                last_number = Payment.objects.filter(
                    invoice__rent=self.invoice.rent
                ).aggregate(
                    Max('id')
                )['id__max'] or 0
                seq = last_number + 1
                rent_id = self.invoice.rent.id
                padded_seq = str(seq).zfill(4)
                base = f"PAY-{rent_id}-{padded_seq}"
                self.payment_number = base
                counter = 0
                while Payment.objects.filter(payment_number=self.payment_number).exists():
                    counter += 1
                    self.payment_number = f"{base}-{counter}"
        super().save(*args, **kwargs)


class Credit(models.Model):
    """
    A manual credit applied to a rent account.
    Subtracts from the tenant's balance (e.g. discount, overpayment refund).
    """
    rent = models.ForeignKey(
        Rent,
        on_delete=models.CASCADE,
        related_name='credits'
    )
    credit_number = models.CharField(
        max_length=100,
        unique=True,
        editable=False
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    credit_date = models.DateField()
    description = models.TextField(max_length=250)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='issued_credits'
    )

    class Meta:
        ordering = ['-credit_date']

    def __str__(self):
        return f"{self.credit_number} - ${self.amount} ({self.credit_date})"

    def save(self, *args, **kwargs):
        if not self.pk and not self.credit_number:
            from django.db import transaction as db_transaction
            with db_transaction.atomic():
                last = Credit.objects.filter(rent=self.rent).aggregate(Max('id'))['id__max'] or 0
                seq = last + 1
                base = f"CRED-{self.rent.id}-{str(seq).zfill(4)}"
                self.credit_number = base
                counter = 0
                while Credit.objects.filter(credit_number=self.credit_number).exists():
                    counter += 1
                    self.credit_number = f"{base}-{counter}"
        super().save(*args, **kwargs)


class Debit(models.Model):
    """
    A manual debit applied to a rent account.
    Adds to the tenant's balance (e.g. damage repair, extra charge).
    """
    rent = models.ForeignKey(
        Rent,
        on_delete=models.CASCADE,
        related_name='debits'
    )
    debit_number = models.CharField(
        max_length=100,
        unique=True,
        editable=False
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    debit_date = models.DateField()
    description = models.TextField(max_length=250)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='issued_debits'
    )

    class Meta:
        ordering = ['-debit_date']

    def __str__(self):
        return f"{self.debit_number} - ${self.amount} ({self.debit_date})"

    def save(self, *args, **kwargs):
        if not self.pk and not self.debit_number:
            from django.db import transaction as db_transaction
            with db_transaction.atomic():
                last = Debit.objects.filter(rent=self.rent).aggregate(Max('id'))['id__max'] or 0
                seq = last + 1
                base = f"DEB-{self.rent.id}-{str(seq).zfill(4)}"
                self.debit_number = base
                counter = 0
                while Debit.objects.filter(debit_number=self.debit_number).exists():
                    counter += 1
                    self.debit_number = f"{base}-{counter}"
        super().save(*args, **kwargs)

