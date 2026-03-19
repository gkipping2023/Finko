from django.contrib import admin
from django.utils import timezone
from .models import User, Properties, Transaction, Rent, PromoCode, AuditLog, Feedback, Invoice, Payment, EmailSubscription

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


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ('subject', 'feedback_type', 'user', 'created_at', 'is_read', 'responded_at')
    list_filter = ('feedback_type', 'is_read', 'created_at')
    search_fields = ('subject', 'message', 'user__email', 'user__first_name', 'user__last_name')
    readonly_fields = ('user', 'created_at', 'responded_at')
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Información del Feedback', {
            'fields': ('user', 'feedback_type', 'subject', 'message', 'created_at')
        }),
        ('Estado y Respuesta', {
            'fields': ('is_read', 'response', 'responded_by', 'responded_at')
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if change and 'response' in form.changed_data and obj.response:
            obj.responded_by = request.user
            obj.responded_at = timezone.now()
        super().save_model(request, obj, form, change)


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'rent', 'invoice_date', 'due_date', 'amount', 'paid_amount', 'status')
    list_filter = ('status', 'invoice_date', 'due_date')
    search_fields = ('invoice_number', 'rent__rent_number')
    readonly_fields = ('invoice_number', 'created_at', 'updated_at')
    
    fieldsets = (
        ('Invoice Information', {
            'fields': ('invoice_number', 'rent', 'invoice_date', 'due_date')
        }),
        ('Payment Details', {
            'fields': ('amount', 'paid_amount', 'status')
        }),
        ('Late Fee', {
            'fields': ('late_fee_amount', 'late_fee_applied_date'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'invoice', 'amount', 'payment_date', 'payment_method', 'status')
    list_filter = ('status', 'payment_date', 'payment_method')
    search_fields = ('invoice__invoice_number', 'transaction__transaction_number')
    readonly_fields = ('created_at', 'transaction')
    
    fieldsets = (
        ('Payment Information', {
            'fields': ('invoice', 'amount', 'payment_date', 'payment_method')
        }),
        ('Status', {
            'fields': ('status', 'description')
        }),
        ('Audit', {
            'fields': ('created_at', 'transaction'),
            'classes': ('collapse',)
        }),
    )


@admin.register(EmailSubscription)
class EmailSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('email', 'is_active', 'created_at', 'updated_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('email',)
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Subscription Information', {
            'fields': ('email', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

