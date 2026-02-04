from django.db import models
from django.contrib.auth.models import AbstractUser
from django_countries.fields import CountryField
from django_countries import countries
from django.db.models import Max
from datetime import datetime

# Create your models lists here.

TRANSACTION_TYPES = (
        ('invoice', 'Factura'),
        ('receipt', 'Recibo'),
        ('credit', 'Credito'),
        ('debit', 'Debito'),
        ('fee', 'Recargo'),
        ('pago', 'Pago'),
    )

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
    rent_due_date = models.IntegerField(choices=[(i, str(i)) for i in range(1, 32)],default=5)  # Date when the rent is due
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


class Transaction(models.Model):

    confirmation_file = models.FileField(upload_to='payment_confirmations/', null=True, blank=True)
    status = models.CharField(max_length=20, choices=[('pending', 'Pendiente'), ('confirmed', 'Confirmado'), ('rejected', 'Rechazado')], default='pending')
    type = models.CharField(choices=TRANSACTION_TYPES, max_length=50)
    owner = models.ForeignKey(User, on_delete=models.CASCADE,limit_choices_to={'role': 'O'},related_name='owner_transactions')  # The user who owns the transaction
    tenant = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True,limit_choices_to={'role': 'T'},related_name='tenant_transactions')  # Optional tenant
    property = models.ForeignKey(Properties, on_delete=models.CASCADE, null=True, blank=True)  # Optional property
    rent = models.ForeignKey(Rent, on_delete=models.CASCADE, null=True, blank=True)  # Optional rent
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(max_length=250, blank=True, null=True)
    payment_method = models.CharField(choices=payment_method, max_length=100)
    due_date = models.DateField(null=True, blank=True)
    is_paid = models.BooleanField(default=False)
    sequence_number = models.PositiveIntegerField(editable=False)
    transaction_number = models.CharField(max_length=100, unique=True, editable=False)
    transaction_date = models.DateField(null=True, blank=False)  # Date when the transaction was created
    created_at = models.DateTimeField(null=True, blank=False, default=datetime.now)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.pk:
            # Only generate sequence number for new transactions
            # Use a more robust approach to prevent duplicate transaction numbers
            import uuid
            from django.db import transaction
            
            with transaction.atomic():
                # Get the last sequence number for this owner, type, and property
                last_number = Transaction.objects.filter(
                    owner=self.owner, 
                    type=self.type, 
                    property=self.property
                ).aggregate(
                    Max('sequence_number')
                )['sequence_number__max'] or 0 # Default to 0 if no transactions exist
                self.sequence_number = last_number + 1 # Increment the sequence number

                # Build the transaction number with property_id included
                padded_seq = str(self.sequence_number).zfill(4)
                property_id = self.property.id if self.property else 0
                base_transaction_number = f"{self.type.upper()}-{self.owner.id}-{property_id}-{padded_seq}"
                
                # Check if this transaction number already exists
                counter = 0
                self.transaction_number = base_transaction_number
                while Transaction.objects.filter(transaction_number=self.transaction_number).exists():
                    counter += 1
                    self.transaction_number = f"{base_transaction_number}-{counter}"

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.transaction_number} - {self.amount} ({self.created_at.strftime('%Y-%m-%d')})"


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
