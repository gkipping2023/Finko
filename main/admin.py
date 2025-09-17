from django.contrib import admin
from .models import User, Properties, Transaction, Rent, PromoCode

# Register your models here.

@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    list_display = ('code', 'discount_percent', 'active', 'expires_at')

@admin.register(Properties)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ('alias', 'location', 'monthly_pmt', 'available')

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('email', 'full_name', 'role', 'phone')
    list_filter = ('role',)
    search_fields = ('email', 'full_name', 'phone')

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('type', 'owner', 'amount', 'created_at','status')
    list_filter = ('type', 'owner')
    search_fields = ('owner__email', 'type')

@admin.register(Rent)
class RentAdmin(admin.ModelAdmin):
    list_display = ('property', 'owner', 'tenant', 'start_date', 'end_date', 'rent_amount', 'status')
    list_filter = ('status', 'owner', 'tenant')
    search_fields = ('property__alias', 'owner__email', 'tenant__email')

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "owner":
            kwargs["queryset"] = User.objects.filter(role='O')  # Only Propietarios
        elif db_field.name == "tenant":
            kwargs["queryset"] = User.objects.filter(role='T')  # Only Inquilinos
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

