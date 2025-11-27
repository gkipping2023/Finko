from django.contrib import admin
from .models import User, Properties, Transaction, Rent, PromoCode, AuditLog

# Register your models here.

@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    list_display = ('code', 'discount_percent', 'active', 'expires_at')

@admin.register(Properties)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ('alias', 'location', 'monthly_pmt', 'available')

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('email', 'full_name', 'role', 'phone', 'privacy_policy_accepted', 'terms_accepted')
    list_filter = ('role', 'privacy_policy_accepted', 'terms_accepted', 'data_deletion_requested')
    search_fields = ('email', 'full_name', 'phone')
    readonly_fields = ('privacy_policy_accepted_date', 'terms_accepted_date', 'last_privacy_update', 'data_deletion_request_date')
    
    fieldsets = (
        ('Información Personal', {
            'fields': ('email', 'first_name', 'last_name', 'full_name', 'phone', 'personal_id', 'role')
        }),
        ('Consentimientos (Ley 81)', {
            'fields': ('privacy_policy_accepted', 'privacy_policy_accepted_date', 
                      'terms_accepted', 'terms_accepted_date',
                      'marketing_consent', 'data_retention_consent')
        }),
        ('Solicitudes de Eliminación', {
            'fields': ('data_deletion_requested', 'data_deletion_request_date'),
            'classes': ('collapse',)
        }),
    )

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('type', 'owner', 'amount', 'created_at','status')
    list_filter = ('type', 'owner')
    search_fields = ('owner__email', 'type')

@admin.register(Rent)
class RentAdmin(admin.ModelAdmin):
    list_display = ('property', 'owner', 'tenant', 'start_date', 'end_date', 'rent_amount', 'status','is_active')
    list_filter = ('status', 'owner', 'tenant')
    search_fields = ('property__alias', 'owner__email', 'tenant__email')

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'user', 'action', 'model_name', 'ip_address')
    list_filter = ('action', 'model_name', 'timestamp')
    search_fields = ('user__email', 'details', 'ip_address')
    readonly_fields = ('timestamp', 'user', 'action', 'model_name', 'object_id', 'ip_address', 'details')
    date_hierarchy = 'timestamp'
    
    def has_add_permission(self, request):
        return False  # Audit logs should not be manually added
    
    def has_change_permission(self, request, obj=None):
        return False  # Audit logs should not be modified


    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "owner":
            kwargs["queryset"] = User.objects.filter(role='O')  # Only Propietarios
        elif db_field.name == "tenant":
            kwargs["queryset"] = User.objects.filter(role='T')  # Only Inquilinos
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

