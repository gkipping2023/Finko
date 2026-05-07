from django.urls import path, include
from django.contrib.auth import views as auth_views
from . import views,admin_views
from django.views.generic import TemplateView

urlpatterns = [
    path('',views.home,name='home'),
    
    # New landing pages
    path('features/', views.features, name='features'),
    path('about/', views.about, name='about'),
    path('contact/', views.contact, name='contact'),
    
    path('api/rent-details/<int:rent_id>/', views.rent_details, name='rent_details'),
    path('import',views.view_import,name='import'),
    path('dashboard',views.dashboard,name='dashboard'),
    path('documents',views.documents,name='documents'),
    path('adjustments',views.adjustments,name='adjustments'),
    path('all-transactions', views.all_transactions, name='all_transactions'),
    path('payments', views.payments, name='payments'),
    path('resend-document/<str:doc_type>/<int:doc_id>/', views.resend_document, name='resend_document'),
    path('log_in',views.log_in,name='log_in'),
    path('logout', views.logoutUser, name='logout'),
    path('maintenance',views.maintenance,name='maintenance'),
    path('invoices',views.invoices,name='invoices'),
    path('properties',views.properties,name='properties'),
    path('properties_form',views.properties_form,name='properties_form'),
    path('register_user',views.register_user,name='register_user'),
    path('reports',views.reports,name='reports'),
    path('generate-documents/', views.generate_documents, name='generate_documents'),
    path('tenants',views.tenants,name='tenants'),
    path('tenant_portal',views.tenant_portal,name='tenant_portal'),
    path('register_tenant',views.register_tenant,name='register_tenant'),
    path('new_rent',views.new_rent,name='new_rent'),
    path('update_property',views.update_property,name='update_property'),
    path('user_profile',views.user_profile,name='user_profile'),
    path('payment/<int:payment_id>/pdf/', views.payment_pdf, name='payment_pdf'),
    path('invoice/<int:invoice_id>/pdf/', views.invoice_pdf, name='invoice_pdf'),
    path('credit/<int:credit_id>/pdf/', views.credit_pdf, name='credit_pdf'),
    path('debit/<int:debit_id>/pdf/', views.debit_pdf, name='debit_pdf'),
    path('contract/<int:rent_id>/pdf/', views.contract_pdf, name='contract_pdf'),
    path('pricing',views.pricing,name='pricing'),
    path('rent/<int:rent_id>/finish/', views.finish_rent, name='finish_rent'),
    path('payment/<int:payment_id>/confirm/', views.confirm_payment, name='confirm_payment'),
    path('report_payment',views.report_payment,name='report_payment'),
    path('api/unpaid-invoices/', views.get_unpaid_invoices, name='get_unpaid_invoices'),
    path('account/', include('allauth.urls')),  # Add allauth URLs
    path('lease/<int:lease_id>/renew/', views.renew_lease, name='renew_lease'),
    path('set_user_role/', views.set_user_role, name='set_user_role'),
    path('admin/form-labels/', admin_views.form_labels_admin, name='form_labels_admin'),
    path('admin/forms/<str:form_name>/data/', admin_views.get_form_data, name='get_form_data'),
    path('admin/form-labels/export/', admin_views.export_form_labels, name='export_form_labels'),
    
    # Public payment portal (no login required)
    path('pay/', views.public_payment_portal, name='public_payment_portal'),
    path('pay/success/', views.public_payment_success, name='public_payment_success'),
    
    # Data Protection & Privacy (Ley 81 Compliance)
    path('privacy/', views.privacy_policy, name='privacy_policy'),
    path('terms/', views.terms_of_service, name='terms_of_service'),
    path('my-data/', views.my_data, name='my_data'),
    path('export-my-data/', views.export_my_data, name='export_my_data'),
    path('delete-account/', views.delete_my_account, name='delete_account'),
    
    # Feedback & Support
    path('feedback/', views.feedback_form, name='feedback_form'),
    path('feedback/success/', views.feedback_success, name='feedback_success'),


    
    path('reset_password/', auth_views.PasswordResetView.as_view(template_name='main/password_reset_view.html'),name='reset_password'),
    path('reset_password_sent/', auth_views.PasswordResetDoneView.as_view(template_name='main/password_reset_sent.html'),name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='main/password_confirm_view.html'),name='password_reset_confirm'),
    path('reset_password_complete/', auth_views.PasswordResetCompleteView.as_view(template_name='main/password_reset_complete.html'),name='password_reset_complete'),
    
    # Stripe payment integration
    path('create-subscription-checkout-session/', views.create_subscription_checkout_session, name='create_subscription_checkout_session'),
    path('subscription/success/', TemplateView.as_view(template_name="main/subscription_success.html"), name='subscription_success'),
    path('subscription/cancel/', TemplateView.as_view(template_name="main/subscription_cancel.html"), name='subscription_cancel'),
]

