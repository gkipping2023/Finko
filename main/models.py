from django.db import models
from django.contrib.auth.models import AbstractUser
from django_countries.fields import CountryField
from django_countries import countries
from django.db.models import Max
from datetime import datetime

# Create your models lists here.

TRANSACTION_TYPES = (
        ('invoice', 'Invoice'),
        ('receipt', 'Receipt'),
        ('credit', 'Credit'),
        ('debit', 'Debit'),
        ('fee', 'Fee'),
        ('pago', 'Pago'),
    )

ID_Type = (
    ('cedula','Cedula'),
    ('pasaporte','Pasaporte')
)

PLAN_CHOICES = (
    ('free', 'Free/Basic'),
    ('standard', 'Standard'),
    ('enterprise', 'Enterprise'),
)

payment_method = (
    ('ach_yappy','ACH O Yappy'),
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

Status = (
    ('available','Disponible'),
    ('no_available','No Disponible')
)

Due_Status = (
    ('good','Al Dia'),
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
    unregistered_tenant_name = models.CharField(max_length=250, blank=True, null=True)
    unregistered_tenant_email = models.EmailField(max_length=250, blank=True, null=True)
    unregistered_tenant_phone = models.CharField(max_length=25, blank=True, null=True)
    unregistered_tenant_id_type =models.CharField(choices=ID_Type,max_length=100,null=True, blank=True)
    unregistered_tenant_personal_id = models.CharField(max_length=250, blank=True, null=True)
    unregistered_tenant_dob = models.DateField(blank=True, null=True)
    unregistered_tenant_nac = CountryField(blank=True, null=True)
    unregistered_tenant_sex = models.CharField(choices=Sex,max_length=100,null=True, blank=True)

    def __str__(self):
        return f"{self.tenant} - {self.property}"


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
            # Get the last sequence number for this owner and type
            last_number = Transaction.objects.filter(owner=self.owner, type=self.type).aggregate(
                Max('sequence_number')
            )['sequence_number__max'] or 0 # Default to 0 if no transactions exist
            self.sequence_number = last_number + 1 # Increment the sequence number

            # Build the transaction number
            padded_seq = str(self.sequence_number).zfill(4)
            self.transaction_number = f"{self.type.upper()}-{self.owner.id}-{padded_seq}"

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.transaction_number} - {self.amount} ({self.created_at.strftime('%Y-%m-%d')})"

