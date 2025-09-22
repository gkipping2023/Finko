from django.urls import path, include
from django.contrib.auth import views as auth_views
from . import views
from django.views.generic import TemplateView

urlpatterns = [
    path('',views.home,name='home'),
    path('api/rent-details/<int:rent_id>/', views.rent_details, name='rent_details'),
    path('import',views.view_import,name='import'),
    path('dashboard',views.dashboard,name='dashboard'),
    path('documents',views.documents,name='documents'),
    path('expenses',views.expenses,name='expenses'),
    path('log_in',views.log_in,name='log_in'),
    path('logout', views.logoutUser, name='logout'),
    path('maintenance',views.maintenance,name='maintenance'),
    path('payments',views.payments,name='payments'),
    path('properties',views.properties,name='properties'),
    path('properties_form',views.properties_form,name='properties_form'),
    path('register_user',views.register_user,name='register_user'),
    path('reports',views.reports,name='reports'),
    path('tenants',views.tenants,name='tenants'),
    path('tenant_portal',views.tenant_portal,name='tenant_portal'),
    path('register_tenant',views.register_tenant,name='register_tenant'),
    path('new_rent',views.new_rent,name='new_rent'),
    path('update_property',views.update_property,name='update_property'),
    path('user_profile',views.user_profile,name='user_profile'),
    path('transaction/<int:transaction_id>/pdf/', views.transaction_pdf, name='transaction_pdf'),
    path('add_transaction',views.add_transaction,name='add_transaction'),
    path('pricing',views.pricing,name='pricing'),
    path('rent/<int:rent_id>/finish/', views.finish_rent, name='finish_rent'),
    path('confirm-payment/<int:transaction_id>/', views.confirm_payment, name='confirm_payment'),
    path('report_payment',views.report_payments,name='report_payment'),
    path('preview-transaction-confirmation/', views.preview_transaction_confirmation, name='preview_transaction_confirmation'),
    path('account/', include('allauth.urls')),  # Add allauth URLs
    path('lease/<int:lease_id>/renew/', views.renew_lease, name='renew_lease'),
    path('set_user_role/', views.set_user_role, name='set_user_role'),

    


    
    path('reset_password/', auth_views.PasswordResetView.as_view(template_name='main/password_reset_view.html'),name='reset_password'),
    path('reset_password_sent/', auth_views.PasswordResetDoneView.as_view(template_name='main/password_reset_sent.html'),name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='main/password_confirm_view.html'),name='password_reset_confirm'),
    path('reset_password_complete/', auth_views.PasswordResetCompleteView.as_view(template_name='main/password_reset_complete.html'),name='password_reset_complete'),
    
    # Stripe payment integration
    path('create-subscription-checkout-session/', views.create_subscription_checkout_session, name='create_subscription_checkout_session'),
    path('subscription/success/', TemplateView.as_view(template_name="main/subscription_success.html"), name='subscription_success'),
    path('subscription/cancel/', TemplateView.as_view(template_name="main/subscription_cancel.html"), name='subscription_cancel'),
]

