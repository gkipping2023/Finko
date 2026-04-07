from django.views.decorators.http import require_POST
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
import re
import stripe
from datetime import date, datetime, timedelta
from django.utils.timezone import now
from calendar import monthrange
from django.urls import reverse
from django.conf import settings
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, get_backends
from django.contrib.auth.decorators import login_required
from .models import Properties, Transaction, Rent, User, PromoCode, Roles, Invoice, Payment
from .forms import AddPropertyForm, NewUserForm,NewTenantForm, NewRentForm, UpdateUserForm, TransactionForm, ReportPaymentForm, RenewLeaseForm, PublicPaymentForm
from django_countries.fields import Country  # Add this import if using django-countries
#from .filters import Reserves_DailyFilter, DogsFilter, Reserves_HotelFilter
from django.db import models  # Import models for aggregate functions
# from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from .filters import TransactionFilter
from weasyprint import HTML
from django.http import HttpResponse
from main.mailgun_utils import send_mailgun_simple
from .services import RentAccountStatus
import base64
from pathlib import Path



# Utility function to get logo for PDF (base64 embedded)
def get_logo_for_pdf(fallback_url=None):
    """
    Get Finko logo embedded as base64 for reliable PDF rendering.
    Falls back to external URL if local file is unavailable.
    
    Args:
        fallback_url: External URL to use if local file not found (optional)
    
    Returns:
        Data URI string for img src or empty string if not found
    """
    logo_path = settings.BASE_DIR / 'static' / 'assets' / 'img' / 'finko_logo.png'
    
    try:
        if logo_path.exists():
            with open(logo_path, 'rb') as f:
                b64 = base64.b64encode(f.read()).decode('utf-8')
                return f'data:image/png;base64,{b64}'
    except Exception as e:
        print(f"Error loading logo for PDF: {e}")
    
    # Return fallback external URL if provided
    return fallback_url or ''


#PDF Generation Function
def render_transaction_pdf(transaction):
    # Map transaction types to templates
    template_map = {
        'invoice': 'main/transaction_invoice.html',
        'receipt': 'main/transaction_receipt.html',
        'credit': 'main/transaction_credit.html',
        'debit': 'main/transaction_debit.html',
        'fee': 'main/transaction_fee.html',
        'pago': 'main/transaction_pago.html',
    }
    
    # Get template for this transaction type, fallback to receipt
    template_name = template_map.get(transaction.type, 'main/transaction_receipt.html')
    
    context = {
        'transaction': transaction,
        'logo_base64': get_logo_for_pdf()
    }
    html_string = render_to_string(template_name, context)
    html = HTML(string=html_string)
    pdf = html.write_pdf()
    return pdf

#Download Pdf Function
@login_required(login_url='log_in')
@xframe_options_sameorigin
def transaction_pdf(request, transaction_id):
    transaction = get_object_or_404(Transaction, id=transaction_id)
    pdf = render_transaction_pdf(transaction)
    response = HttpResponse(pdf, content_type='application/pdf')
    # If preview query param is provided, show inline in browser for previewing.
    preview = request.GET.get('preview')
    if preview in ['1', 'true', 'yes']:
      disposition = f'inline; filename="Transaccion_{transaction.transaction_number}.pdf"'
    else:
      disposition = f'attachment; filename="Transaccion_{transaction.transaction_number}.pdf"'
      response['Content-Disposition'] = disposition
    return response

# Contract PDF Generation Function
def render_contract_pdf(rent):
    """
    Generate a lease contract PDF for a specific rent.
    """
    from datetime import datetime
    from dateutil.relativedelta import relativedelta
    
    # Calculate contract duration in months
    duration_months = 0
    if rent.end_date and rent.start_date:
        delta = relativedelta(rent.end_date, rent.start_date)
        duration_months = delta.years * 12 + delta.months
    
    # Get contract date (use start_date or today)
    contract_date = rent.start_date if rent.start_date else datetime.now().date()
    
    # Convert amount to words (Spanish)
    def number_to_words_spanish(amount):
        """Simple number to words converter for amounts"""
        # This is a simplified version - you may want to use a library like num2words
        try:
            amount_str = f"{float(amount):.2f}"
            return f"{amount_str} BALBOAS"
        except:
            return f"{amount} BALBOAS"
    
    rent_amount_words = number_to_words_spanish(rent.rent_amount)
    
    # Get owner
    owner = rent.owner
    
    context = {
        'rent': rent,
        'owner': owner,
        'contract_day': contract_date.day,
        'contract_month': contract_date.strftime('%B'),
        'contract_year': contract_date.year,
        'duration_months': duration_months,
        'rent_amount_words': rent_amount_words,
        'generation_date': datetime.now(),
        'logo_base64': get_logo_for_pdf()
    }
    
    html_string = render_to_string('main/documents.html', context)
    html = HTML(string=html_string)
    pdf = html.write_pdf()
    return pdf

# Download Contract PDF Function
@login_required(login_url='log_in')
@xframe_options_sameorigin
def contract_pdf(request, rent_id):
    """
    View to download or preview the lease contract PDF.
    """
    rent = get_object_or_404(Rent, id=rent_id)
    
    # Check authorization - only owner or tenant can view
    if request.user.role == 'O' and rent.owner != request.user:
        messages.error(request, 'No tienes permiso para ver este contrato.')
        return redirect('properties')
    
    if request.user.role == 'T' and rent.tenant != request.user:
        messages.error(request, 'No tienes permiso para ver este contrato.')
        return redirect('tenant_portal')
    
    pdf = render_contract_pdf(rent)
    response = HttpResponse(pdf, content_type='application/pdf')
    
    # If preview query param is provided, show inline in browser
    preview = request.GET.get('preview')
    if preview in ['1', 'true', 'yes']:
        disposition = f'inline; filename="Contrato_{rent.rent_number}.pdf"'
    else:
        disposition = f'attachment; filename="Contrato_{rent.rent_number}.pdf"'
    
    response['Content-Disposition'] = disposition
    return response

# Modal role selection view
@login_required
@require_POST
def set_user_role(request):
  role = request.POST.get('role')
  if role in dict(Roles):
    user = request.user
    user.role = role
    user.save()
    messages.success(request, 'Tu rol ha sido actualizado.')
  else:
    messages.error(request, 'Selección de rol inválida.')
  return redirect(request.POST.get('next', 'dashboard'))

@login_required(login_url='log_in')
def rent_details(request, rent_id):
    """API endpoint to get rent details for auto-populating transaction form"""
    rent = get_object_or_404(Rent, id=rent_id, owner=request.user)
    
    # Handle both registered and unregistered tenants
    tenant_id = rent.tenant.id if rent.tenant else None
    tenant_display = None
    
    # If no registered tenant, use unregistered tenant info
    if not rent.tenant and rent.unregistered_tenant_name:
        tenant_display = rent.unregistered_tenant_name
        if rent.unregistered_tenant_email:
            tenant_display += f" ({rent.unregistered_tenant_email})"
    elif rent.tenant:
        tenant_display = f"{rent.tenant.first_name} {rent.tenant.last_name}"
    
    data = {
        'tenant_id': tenant_id,
        'property_id': rent.property.id,
        'property_display': rent.property.alias,
        'tenant_display': tenant_display,
        'is_unregistered': not bool(rent.tenant),
    }
    return JsonResponse(data)

@login_required(login_url='log_in')
def finish_rent(request, rent_id):
    rent = get_object_or_404(Rent, id=rent_id)
    if request.method == "POST":
        # Mark property as available
        rent.property.available = True
        rent.property.save()

        # Optionally, mark rent as inactive or set end_date
        rent.status = False
        rent.is_active = False
        rent.end_date = datetime.now().date()
        rent.save()

        # Send email to the tenant
        if rent.tenant:
            tenant_html = f"""
                <html>
                  <head>
                    <style>
                      body {{
                        font-family: 'Montserrat', Arial, sans-serif;
                        background: #f8f9fa;
                        color: #344767;
                        margin: 0;
                        padding: 0;
                      }}
                      .container {{
                        text-align: center;
                        max-width: 600px;
                        margin: 40px auto;
                        background: #fff;
                        border-radius: 12px;
                        box-shadow: 0 2px 8px rgba(44,62,80,0.08);
                        padding: 32px 24px;
                      }}
                      .footer {{
                        color: #8392ab;
                        font-size: 13px;
                        margin-top: 32px;
                        text-align: center;
                      }}
                    </style>
                  </head>
                  <body>
                    <div class="container">
                      <h2 style="color:#17c1e8;">¡Contrato Finalizado!</h2>
                      <p>Hola {rent.tenant.first_name},</p>
                      <p>Te informamos que tu contrato de alquiler para la propiedad <strong>{rent.property.alias}</strong> ha finalizado exitosamente.</p>
                      <p>Gracias por confiar en nosotros.</p>
                      <div class="footer">
                        Este es un mensaje automático de Finko - Property Management System.
                      </div>
                    </div>
                  </body>
                </html>
                """
            try:
                send_mailgun_simple(
                    subject="Finalización de Contrato de Alquiler",
                    html=tenant_html,
                    to_emails=rent.tenant.email,
                    from_email=settings.DEFAULT_FROM_EMAIL
                )
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Failed to send tenant email: {e}")

        # Send email to the owner
        if rent.owner:
            owner_html = f"""
                <html>
                  <head>
                    <style>
                      body {{
                        font-family: 'Montserrat', Arial, sans-serif;
                        background: #f8f9fa;
                        color: #344767;
                        margin: 0;
                        padding: 0;
                      }}
                      .container {{
                        text-align: center;
                        max-width: 600px;
                        margin: 40px auto;
                        background: #fff;
                        border-radius: 12px;
                        box-shadow: 0 2px 8px rgba(44,62,80,0.08);
                        padding: 32px 24px;
                      }}
                      .footer {{
                        color: #8392ab;
                        font-size: 13px;
                        margin-top: 32px;
                        text-align: center;
                      }}
                    </style>
                  </head>
                  <body>
                    <div class="container">
                      <h2 style="color:#17c1e8;">¡Contrato Finalizado!</h2>
                      <p>Hola {rent.owner.first_name},</p>
                      <p>Te informamos que el contrato de alquiler para la propiedad <strong>{rent.property.alias}</strong> ha finalizado exitosamente.</p>
                      <p>La propiedad ahora está disponible para nuevos alquileres.</p>
                      <div class="footer">
                        Este es un mensaje automático de Finko - Property Management System.
                      </div>
                    </div>
                  </body>
                </html>
                """
            try:
                send_mailgun_simple(
                    subject="Finalización de Contrato de Alquiler",
                    html=owner_html,
                    to_emails=rent.owner.email,
                    from_email=settings.DEFAULT_FROM_EMAIL
                )
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Failed to send owner email: {e}")

        # Success message
        messages.success(request, "El alquiler ha sido finalizado y la propiedad está disponible.")
        return redirect('properties')
    return redirect('properties')

def view_import(request):
    context= {

    }
    return render(request,'main/import.html',context)

def home(request):
    #Stripe Public Key for JS
    context= {'STRIPE_PUBLISHABLE_KEY': settings.STRIPE_PUBLISHABLE_KEY,

    }
    return render(request,'main/landing.html',context)

def features(request):
    return render(request, 'main/features.html')

def about(request):
    return render(request, 'main/about.html')

def contact(request):
    if request.method == 'POST':
        # Handle contact form submission
        name = request.POST.get('name')
        email = request.POST.get('email')
        phone = request.POST.get('phone', '')
        subject = request.POST.get('subject')
        message = request.POST.get('message')
        
        # Send email notification to all superusers
        superusers = User.objects.filter(is_superuser=True)
        superuser_emails = [user.email for user in superusers]
        
        if superuser_emails:
            email_subject = f"Nuevo mensaje de contacto: {subject}"
            email_body = f"""
        Nombre: {name}
        Email: {email}
        Teléfono: {phone}
        Asunto: {subject}
        
        Mensaje:
        {message}
        """
            
            try:
                send_mailgun_simple(
                    to_emails=superuser_emails,
                    subject=email_subject,
                    body=email_body,
                    from_email=settings.DEFAULT_FROM_EMAIL
                )
                messages.success(request, 'Tu mensaje ha sido enviado exitosamente. Te contactaremos pronto.')
            except Exception as e:
                messages.error(request, 'Hubo un error al enviar tu mensaje. Por favor intenta de nuevo.')
        else:
            messages.warning(request, 'No hay administradores disponibles en este momento.')
        
        return redirect('contact')
    
    return render(request, 'main/contact.html')

def log_in(request):
    page = 'login'
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        user = authenticate(request, password=password, email=email)
        if user is not None:
            login(request, user)
            return redirect('dashboard')
        else:
            messages.error(request, 'Usuario o Contraseña Inválidos')

    context = {'page' : page}
    return render(request,'main/log_in.html',context)

def logoutUser(request):
    logout(request)
    return redirect('home')

@login_required(login_url='log_in')
def update_property(request):
        property_id = request.GET.get('property_id')
        property_instance = None
        form = None

        if property_id:
            property_instance = get_object_or_404(Properties,id=property_id, owner=request.user)
            if request.method == "POST":
                form = AddPropertyForm(request.POST, instance=property_instance)
                if form.is_valid():
                    form.save(user=request.user)  # Pass the logged-in user to the form
                    return redirect('properties')
            else:
                form = AddPropertyForm(instance=property_instance)
        return render(request, 'main/update_property.html', {
            'form': form,
            'properties':Properties.objects.filter(owner=request.user),
            'selected_property':property_instance
            })

def register_user(request):
    new_user_form = NewUserForm()
    if request.method == 'POST':
        new_user_form = NewUserForm(request.POST)
        if new_user_form.is_valid():
            user = new_user_form.save(commit=False)
            user.last_name = user.last_name.capitalize()
            user.first_name = user.first_name.capitalize()
            user.full_name = f"{user.first_name} {user.last_name}".strip().title()
            user.save()

            # Link any existing rents with this user's email
            unlinked_rents = Rent.objects.filter(unregistered_tenant_email=user.email, tenant__isnull=True)
            for rent in unlinked_rents:
                rent.tenant = user
                rent.save()

            # Send welcome email via Mailgun
            subject = "¡Bienvenido a Finko - Property Management System!"
            body = f"""
            <html>
              <head>
                <style>
                  body {{
                    font-family: 'Montserrat', Arial, sans-serif;
                    background: #f8f9fa;
                    color: #344767;
                    margin: 0;
                    padding: 0;
                  }}
                  .container {{
                    text-align: center;
                    max-width: 600px;
                    margin: 40px auto;
                    background: #fff;
                    border-radius: 12px;
                    box-shadow: 0 2px 8px rgba(44,62,80,0.08);
                    padding: 32px 24px;
                  }}
                  .btn {{
                    display: inline-block;
                    background: #17c1e8;
                    color: #fff !important;
                    padding: 12px 28px;
                    border-radius: 6px;
                    text-decoration: none;
                    font-weight: 600;
                    margin-top: 16px;
                  }}
                  .footer {{
                    color: #8392ab;
                    font-size: 13px;
                    margin-top: 32px;
                    text-align: center;
                  }}
                </style>
              </head>
              <body>
                <div class="container">
                  <h2 style="color:#17c1e8;">¡Bienvenido a Finko!</h2>
                  <p>Hola {user.first_name},</p>
                  <p>Gracias por registrarte en <strong>Finko - Property Management System</strong>. Estamos emocionados de tenerte a bordo.</p>
                  <p>Con Finko, podrás gestionar tus propiedades, inquilinos y pagos de manera eficiente y profesional.</p>
                  <p>
                    <a href="{request.build_absolute_uri(reverse('dashboard'))}" class="btn">Ir al Panel de Control</a>
                  </p>
                  <p style="margin-top: 24px;">
                    <a href="{request.build_absolute_uri(reverse('user_profile'))}" class="btn" style="background:#344767;">Completa tu perfil</a>
                  </p>
                  <div class="footer">
                    Este es un mensaje automático de Finko - Property Management System.
                  </div>
                </div>
              </body>
            </html>
            """

            try:
                send_mailgun_simple(subject=subject, html=body, to_emails=user.email, from_email=settings.DEFAULT_FROM_EMAIL)
            except Exception as e:
                # Optional: log the error for debugging
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Failed to send welcome email to {user.email}: {e}")

            # Log the user in and redirect
            # Set the backend attribute on the user object for Django's login system
            user.backend = 'django.contrib.auth.backends.ModelBackend'
            login(request, user)
            return redirect('user_profile')
        else:
            print(new_user_form.errors)

    context = {'new_user_form': new_user_form}
    return render(request, 'main/register_user.html', context)


# def register_user(request):
#     new_user_form = NewUserForm()
#     if request.method == 'POST':
#         new_user_form = NewUserForm(request.POST)
#         if new_user_form.is_valid():
#             user = new_user_form.save(commit=False)
#             user.last_name = user.last_name.capitalize()
#             user.first_name = user.first_name.capitalize()
#             user.full_name = f"{user.first_name} {user.last_name}".strip().title()
#             user.save()
#             # Link any existing rents with this user's email
#             unlinked_rents = Rent.objects.filter(unregistered_tenant_email=user.email, tenant__isnull=True)
#             for rent in unlinked_rents:
#               rent.tenant = user
#               rent.save()
#             # Send welcome email
#             email = EmailMessage(
#                 subject="¡Bienvenido a Finko - Property Management System!",
#                 body=f"""
#                 <html>
#                   <head>
#                     <style>
#                       body {{
#                         font-family: 'Montserrat', Arial, sans-serif;
#                         background: #f8f9fa;
#                         color: #344767;
#                         margin: 0;
#                         padding: 0;
#                       }}
#                       .container {{
#                         text-align: center;
#                         max-width: 600px;
#                         margin: 40px auto;
#                         background: #fff;
#                         border-radius: 12px;
#                         box-shadow: 0 2px 8px rgba(44,62,80,0.08);
#                         padding: 32px 24px;
#                       }}
#                       .btn {{
#                         display: inline-block;
#                         background: #17c1e8;
#                         color: #fff !important;
#                         padding: 12px 28px;
#                         border-radius: 6px;
#                         text-decoration: none;
#                         font-weight: 600;
#                         margin-top: 16px;
#                       }}
#                       .footer {{
#                         color: #8392ab;
#                         font-size: 13px;
#                         margin-top: 32px;
#                         text-align: center;
#                       }}
#                     </style>
#                   </head>
#                   <body>
#                     <div class="container">
#                       <h2 style="color:#17c1e8;">¡Bienvenido a Finko!</h2>
#                       <p>Hola {user.first_name},</p>
#                       <p>Gracias por registrarte en <strong>Finko - Property Management System</strong>. Estamos emocionados de tenerte a bordo.</p>
#                       <p>Con Finko, podrás gestionar tus propiedades, inquilinos y pagos de manera eficiente y profesional.</p>
#                       <p>
#                         <a href="{request.build_absolute_uri(reverse('dashboard'))}" class="btn">Ir al Panel de Control</a>
#                       </p>
#                       <p style="margin-top: 24px;">
#                         <a href="{request.build_absolute_uri(reverse('user_profile'))}" class="btn" style="background:#344767;">Completa tu perfil</a>
#                       </p>
#                       <div class="footer">
#                         Este es un mensaje automático de Finko - Property Management System.
#                       </div>
#                     </div>
#                   </body>
#                 </html>
#                 """,
#                 from_email=settings.DEFAULT_FROM_EMAIL,
#                 to=[user.email],
#             )
#             email.content_subtype = "html"
#             email.send()

#             # Log the user in and redirect to the profile page
#             # Specify backend explicitly to avoid error with multiple authentication backends
#             from django.contrib.auth import get_backends
#             backend = get_backends()[0]  # Use the first backend (ModelBackend)
#             user.backend = backend.__module__ + '.' + backend.__class__.__name__
#             login(request, user, backend=user.backend)
#             return redirect('user_profile')
#         else:
#             print(new_user_form.errors)
#     context = {
#         'new_user_form': new_user_form,
#     }
#     return render(request, 'main/register_user.html', context)
# def register_user(request):
#     new_user_form = NewUserForm()
#     if request.method == 'POST':
#         new_user_form = NewUserForm(request.POST)
#         if new_user_form.is_valid():
#             user = new_user_form.save(commit=False)
#             user.last_name = user.last_name.capitalize()
#             user.first_name = user.first_name.capitalize()
#             user.full_name = f"{user.first_name} {user.last_name}".strip().title()
#             user.save()
#             login(request, user)
#             return redirect('user_profile')
#         else:
#             new_user_form = NewUserForm()
#             print(new_user_form.errors)
#     else:
#         print(request.method)
#     context= {
#         'new_user_form' : new_user_form,
#     }
#     return render(request,'main/register_user.html',context)

@login_required(login_url='log_in')
def user_profile(request):
    # Define a list of valid promo codes
    valid_promo_codes = ['ABC123', 'DISCOUNT50', 'WELCOME10']  # Add your valid promo codes here

    user = request.user
    form = UpdateUserForm(instance=user)

    if request.method == 'POST':
        form = UpdateUserForm(request.POST, instance=user)
        if form.is_valid():
            # Get the promo code entered by the user
            input_promo_code = form.cleaned_data.get('promo_code')

            # Validate the promo code
            if input_promo_code and input_promo_code not in valid_promo_codes:
                messages.error(request, 'Código Promocional Inválido')
                return render(request, 'main/user_profile.html', {'form': form})

            # Save the promo code and other fields
            user.promo_code = input_promo_code
            nac_code = form.cleaned_data.get('nac')
            if nac_code:
                user.nac = Country(nac_code)
            form.save()
            messages.success(request, 'Perfil Actualizado Exitosamente')
            return redirect('dashboard')
        else:
            messages.error(request, 'Error al actualizar, por favor verifica tu perfil')

    context = {
        'form': form
    }
    return render(request, 'main/user_profile.html', context)

# @login_required(login_url='log_in')
# def user_profile(request):
#     user = request.user
#     form = UpdateUserForm(instance=user)
#     if request.method == 'POST':
#         form = UpdateUserForm(request.POST,instance=user)
#         if form.is_valid():
#             nac_code = form.cleaned_data.get('nac')
#             if nac_code:
#                 user.nac = Country(nac_code)
#             form.save()
#             messages.success(request,'Profile Updated Successfully')
#             return redirect('dashboard')
#         else:
#             print(form.errors)
#             messages.error(request,'Error in update, Please verify your profile')
#     context= {
#         'form' : form
#     }
#     return render(request,'main/user_profile.html',context)

# @login_required(login_url='log_in')
# def new_rent(request):
#     property_id = request.GET.get('property_id')
#     personal_id = request.GET.get('personal_id')
#     tenant = None
#     property_instance = None
#     form = None

#     # Search for tenant by personal_id
#     if personal_id:
#         try:
#             tenant = User.objects.get(personal_id=personal_id, role='T')
#         except User.DoesNotExist:
#             tenant = None
#             print("Tenant not found")

#     # Fetch the selected property
#     if property_id:
#         property_instance = get_object_or_404(Properties, id=property_id, owner=request.user)
#         if request.method == "POST":
#             form = NewRentForm(request.POST)
#             if form.is_valid():
#                 # Save the rent details
#                 rent = form.save(commit=False)
#                 rent.property = property_instance
#                 rent.tenant = tenant
#                 rent.owner = request.user  # Set the owner as the logged-in user
#                 rent.save()

#                 # Update the property's availability
#                 property_instance.available = False
#                 property_instance.save()

#                 print("Rent created successfully!")
#                 return redirect('properties')
#             else:
#                 print(form.errors)
#                 #form = NewRentForm(request.POST)
#         else:
#             form = NewRentForm()#instance=property_instance

#     return render(request, 'main/new_rent.html', {
#         'form': form,
#         'properties': Properties.objects.filter(owner=request.user, available=True),
#         'selected_property': property_instance,
#         'personal_id': personal_id,
#         'tenant': tenant,
#     })

@login_required(login_url='log_in')
def new_rent(request):
    property_id = request.GET.get('property_id') or request.POST.get('property_id')
    personal_id = request.GET.get('personal_id') or request.POST.get('personal_id')
    tenant = None
    property_instance = None
    form = None

    # Search for tenant by personal_id (from GET or POST)
    if personal_id:
        try:
            tenant = User.objects.get(personal_id=personal_id, role='T')
        except User.DoesNotExist:
            tenant = None
            messages.warning(request, f"No se encontró ningún inquilino registrado con ID: {personal_id}")

    # Fetch the selected property
    if property_id:
        property_instance = get_object_or_404(Properties, id=property_id, owner=request.user)
        if request.method == "POST":
            # Create a mutable copy of POST data to inject tenant if found
            post_data = request.POST.copy()
            if tenant:
                post_data['tenant'] = tenant.id
            
            form = NewRentForm(post_data)
            
            if form.is_valid():
                # Save the rent details
                rent = form.save(commit=False)
                rent.property = property_instance
                rent.owner = request.user  # Set the owner as the logged-in user
                
                # Set tenant if found via search
                if tenant:
                    rent.tenant = tenant
                # If no tenant found, unregistered fields will be saved from form
                
                rent.save()
                # Update the property's availability
                property_instance.available = False
                property_instance.save()

                # Determine recipient for email notification
                if rent.tenant:
                    recipient_email = rent.tenant.email
                    recipient_name = rent.tenant.first_name
                elif rent.unregistered_tenant_email:
                    recipient_email = rent.unregistered_tenant_email
                    recipient_name = rent.unregistered_tenant_name
                else:
                    recipient_email = None
                    recipient_name = None

                # Send email notification
                if recipient_email:
                    registration_link = request.build_absolute_uri(reverse('register_user'))
                    tenant_html = f"""
                        <html>
                          <head>
                            <style>
                              body {{
                                font-family: 'Montserrat', Arial, sans-serif;
                                background: #f8f9fa;
                                color: #344767;
                                margin: 0;
                                padding: 0;
                              }}
                              .container {{
                                text-align: center;
                                max-width: 600px;
                                margin: 40px auto;
                                background: #fff;
                                border-radius: 12px;
                                box-shadow: 0 2px 8px rgba(44,62,80,0.08);
                                padding: 32px 24px;
                              }}
                              .btn {{
                                display: inline-block;
                                background: #17c1e8;
                                color: #fff !important;
                                padding: 12px 28px;
                                border-radius: 6px;
                                text-decoration: none;
                                font-weight: 600;
                                margin-top: 16px;
                              }}
                              .footer {{
                                color: #8392ab;
                                font-size: 13px;
                                margin-top: 32px;
                                text-align: center;
                              }}
                            </style>
                          </head>
                          <body>
                            <div class="container">
                              <h2 style="color:#17c1e8;">¡Nuevo Contrato de Alquiler!</h2>
                              <p>Hola {recipient_name},</p>
                              <p>Se ha creado un nuevo contrato de alquiler para la propiedad <strong>{rent.property.alias}</strong>.</p>
                              <p>Por favor, revisa los detalles del contrato en tu portal de inquilino.</p>
                              {f'<p><a href="{request.build_absolute_uri(reverse("tenant_portal"))}" class="btn">Ir al Portal de Inquilino</a></p>' if rent.tenant else ''}
                              <p style="margin-top: 24px;">
                                ¿Aún no tienes cuenta? <a href="{registration_link}" class="btn" style="background:#344767;">Regístrate aquí</a>
                              </p>
                              <div class="footer">
                                Este es un mensaje automático de Finko - Property Management System.
                              </div>
                            </div>
                          </body>
                        </html>
                        """
                    try:
                        send_mailgun_simple(
                            subject="Nuevo Contrato de Alquiler",
                            html=tenant_html,
                            to_emails=recipient_email,
                            from_email=settings.DEFAULT_FROM_EMAIL
                        )
                    except Exception as e:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.error(f"Failed to send tenant notification email: {e}")

                messages.success(request, "Contrato de alquiler creado exitosamente y se ha notificado al inquilino.")
                # Store rent ID in session to trigger contract PDF opening on next page
                request.session['new_rent_contract_id'] = rent.id
                return redirect('properties')
            else:
                print(form.errors)
                messages.error(request, "Por favor corrige los errores en el formulario.")
        else:
            # Pre-populate tenant if found via search
            initial_data = {}
            if tenant:
                initial_data['tenant'] = tenant.id
            form = NewRentForm(initial=initial_data)

    return render(request, 'main/new_rent.html', {
        'form': form,
        'properties': Properties.objects.filter(owner=request.user, available=True),
        'selected_property': property_instance,
        'personal_id': personal_id,
        'tenant': tenant,
    })

@login_required(login_url='log_in')
def renew_lease(request, lease_id):
    lease = get_object_or_404(Rent, id=lease_id, owner=request.user)
    if request.method == 'POST':
        form = RenewLeaseForm(request.POST, instance=lease)
        if form.is_valid():
            renewed_lease = form.save(commit=False)
            renewed_lease.is_active = True
            renewed_lease.status = True
            renewed_lease.save()
            messages.success(request, "Contrato renovado con términos actualizados!")
            return redirect('properties')
    else:
        form = RenewLeaseForm(instance=lease)
    return render(request, 'main/renew_lease.html', {'form': form, 'lease': lease})


@login_required(login_url='log_in')
def dashboard(request):
    user = request.user

    # Portfolio Overview
    total_properties = Properties.objects.filter(owner=user).count()
    rented_properties = Rent.objects.filter(owner=user, status=True).count()
    occupancy_rate = round((rented_properties / total_properties) * 100, 2) if total_properties > 0 else 0
    
    # Calculate collected_income & pending_income for CURRENT MONTH
    active_rents = Rent.objects.filter(owner=user, is_active=True)
    
    # Get current month date range
    today = datetime.now()
    month_start = today.replace(day=1)
    next_month = (month_start + timedelta(days=32)).replace(day=1)
    month_end = next_month - timedelta(days=1)
    
    collected_income = 0
    pending_income = 0
    total_outstanding_balance = 0
    
    for rent in active_rents:
        # Get invoices for current month
        current_month_invoices = rent.invoices.filter(
            invoice_date__gte=month_start,
            invoice_date__lte=month_end
        )
        
        if current_month_invoices.exists():
            # Calculate collected and pending for current month
            total_month_invoiced = current_month_invoices.aggregate(
                total=models.Sum('amount')
            )['total'] or 0
            total_month_paid = current_month_invoices.aggregate(
                total=models.Sum('paid_amount')
            )['total'] or 0
            
            collected_income += total_month_paid
            pending_income += (total_month_invoiced - total_month_paid)
        
        # Calculate outstanding balance using comprehensive status
        from .services import RentAccountStatus
        rent_status = RentAccountStatus(rent).get_status()
        total_outstanding_balance += rent_status['balance_owed']
    
    # Calculate expected monthly income (total rent amount for all active rents)
    expected_monthly_income = active_rents.aggregate(
        total=models.Sum('rent_amount')
    )['total'] or 0
    
    # Count active rents with end date in next 30 days
    upcoming_renewals = Rent.objects.filter(
        owner=user, 
        is_active=True,
        end_date__gte=datetime.now(), 
        end_date__lte=datetime.now() + timedelta(days=30)
    ).count()

    # Financial Snapshot - Calculate confirmed payments this month
    # Confirmed Invoice payments
    confirmed_invoice_payments = 0
    for rent in active_rents:
        current_month_invoices = rent.invoices.filter(
            invoice_date__gte=month_start,
            invoice_date__lte=month_end
        )
        confirmed_invoice_payments += current_month_invoices.aggregate(
            total=models.Sum('paid_amount')
        )['total'] or 0
    
    # Confirmed Transaction payments (receipt, credit, pago types)
    confirmed_transaction_payments = Transaction.objects.filter(
        owner=user,
        type__in=['receipt', 'credit', 'pago'],
        status='confirmed',
        transaction_date__gte=month_start,
        transaction_date__lte=month_end
    ).aggregate(total=models.Sum('amount'))['total'] or 0
    
    # Total collected and outstanding
    rent_collected = confirmed_invoice_payments + confirmed_transaction_payments
    rent_outstanding = expected_monthly_income - rent_collected
    
    # Recent confirmed payments
    recent_payments = Transaction.objects.filter(
        owner=user, 
        type__in=['receipt', 'credit', 'pago'],
        status='confirmed'
    ).order_by('-transaction_date')[:5]
    
    last_payment = Transaction.objects.filter(
        owner=user, 
        type__in=['receipt', 'credit', 'pago'],
        status='confirmed'
    ).order_by('-transaction_date').first()
    
    # Monthly expenses (this month only)
    expense_summary = Transaction.objects.filter(
        owner=user, 
        type='debit',
        transaction_date__gte=month_start,
        transaction_date__lte=month_end
    ).aggregate(total=models.Sum('amount'))['total'] or 0
    
    # Monthly net cash flow
    net_cash_flow = rent_collected - expense_summary

    # Alerts / Notifications
    # Count active rents with past due invoices
    from datetime import date
    overdue_rent_alerts = Rent.objects.filter(
        owner=user, 
        is_active=True,
        invoices__due_date__lt=date.today(),
        invoices__paid_amount__lt=models.F('invoices__amount')
    ).distinct().count()
    
    leases_expiring_soon = Rent.objects.filter(owner=user, end_date__gte=datetime.now(), end_date__lte=datetime.now() + timedelta(days=30)).count()
    pending_maintenance_requests = Properties.objects.filter(owner=user, maint_status='requested').count()

    # Add role-specific context to avoid extra queries in template
    context = {
      'last_payment': last_payment,
      'total_properties': total_properties,
      'occupancy_rate': occupancy_rate,
      'collected_income': collected_income,
      'pending_income': pending_income,
      'expected_monthly_income': expected_monthly_income,
      'upcoming_renewals': upcoming_renewals,
      'rent_collected': rent_collected,
      'rent_outstanding': rent_outstanding,
      'recent_payments': recent_payments,
      'expense_summary': expense_summary,
      'net_cash_flow': net_cash_flow,
      'overdue_rent_alerts': overdue_rent_alerts,
      'leases_expiring_soon': leases_expiring_soon,
      'pending_maintenance_requests': pending_maintenance_requests,
      'total_outstanding_balance': total_outstanding_balance,
    }

    # Tenant-specific context
    if user.role == 'T':
      tenant_rents = Rent.objects.filter(tenant=user, is_active=True)
      tenant_next_rent = tenant_rents.order_by('end_date').first() if tenant_rents.exists() else None
      # compute days past due if available
      if tenant_next_rent:
        try:
          tenant_next_rent.days_past_due = get_days_past_due(tenant_next_rent)
        except Exception:
          tenant_next_rent.days_past_due = 0
      tenant_total_paid = Transaction.objects.filter(tenant=user, type='receipt', status='confirmed').aggregate(total=models.Sum('amount'))['total'] or 0
      tenant_recent_payments = Transaction.objects.filter(tenant=user, type='receipt', status='confirmed').order_by('-transaction_date')[:5]

      context.update({
        'tenant_rents': tenant_rents,
        'tenant_next_rent': tenant_next_rent,
        'tenant_total_paid': tenant_total_paid,
        'tenant_recent_payments': tenant_recent_payments,
      })

    # Owner-specific context
    if user.role == 'O':
      owner_properties = Properties.objects.filter(owner=user)
      # annotate each property with last payment info to avoid template queries
      props_with_last = []
      for p in owner_properties:
        last_payment = Transaction.objects.filter(property=p, type='receipt', status='confirmed').order_by('-transaction_date').first()
        p.last_payment_amount = last_payment.amount if last_payment else None
        p.last_payment_date = last_payment.transaction_date if last_payment else None
        props_with_last.append(p)

      pending_confirmations = Transaction.objects.filter(owner=user, status='pending').count()
      context.update({
        'owner_properties': props_with_last,
        'pending_confirmations': pending_confirmations,
      })

    return render(request, 'main/dashboard.html', context)

from django.core.files.base import ContentFile

@login_required(login_url='log_in')
def payments(request):
  if request.method == 'POST':
    form = TransactionForm(request.POST, user=request.user)
    if form.is_valid():
      transaction = form.save(commit=False)
      transaction.owner = request.user  # Set the logged-in user as the owner
      transaction.save()
      pdf = render_transaction_pdf(transaction)
      messages.success(request, f"¡{transaction.get_type_display()} creado exitosamente!")
      return redirect('payments')
    else:
      messages.error(request, "Hubo un error al crear la transacción.")
  else:
    form = TransactionForm(user=request.user)

  transactions = Transaction.objects.filter(owner=request.user).order_by('-created_at')
  transaction_properties = Properties.objects.filter(owner=request.user).distinct()

  # Use django-filter for filtering
  transaction_filter = TransactionFilter(request.GET, queryset=transactions)
  # Limit tenant and property dropdowns to current user's data
  transaction_filter.form.fields['tenant'].queryset = User.objects.filter(
    tenant_transactions__owner=request.user, role='T'
  ).distinct()
  transaction_filter.form.fields['property'].queryset = transaction_properties

  context = {
    'transaction_properties': transaction_properties,
    'transactions': transaction_filter.qs,
    'form': form,
    'filter': transaction_filter,
  }
  return render(request, 'main/payments.html', context)

@login_required(login_url='log_in')
def add_transaction(request):
    if request.method == 'POST':
        form = TransactionForm(request.POST, user=request.user)
        if form.is_valid():
            # Check if this is a preview request
            if request.POST.get('action') == 'preview':
                # Create transaction object but don't save yet
                transaction = form.save(commit=False)
                transaction.owner = request.user
                
                # Auto-populate tenant and property from the selected rent
                if transaction.rent:
                    transaction.property = transaction.rent.property
                    transaction.tenant = transaction.rent.tenant  # Can be None for unregistered
                
                # Generate a temporary transaction number for preview
                context = {
                    'form': form,
                    'transaction': transaction,
                    'preview': True,
                    'form_data': request.POST.dict()
                }
                return render(request, 'main/add_transaction.html', context)
            else:
                # This is a confirmation from preview, save the transaction
                transaction = form.save(commit=False)
                transaction.owner = request.user  # Set the logged-in user as the owner
                transaction.status = 'confirmed'
                
                # Auto-populate tenant and property from the selected rent
                if transaction.rent:
                    transaction.property = transaction.rent.property
                    transaction.tenant = transaction.rent.tenant  # Can be None for unregistered
                
                transaction.save()
                messages.success(request, f"¡{transaction.get_type_display()} creado exitosamente!")
                return redirect('transaction_pdf', transaction_id=transaction.id)
        else:
            messages.error(request, "Hubo un error al crear la transacción.")
    else:
        form = TransactionForm(user=request.user)
    context = {
        'form': form,
        'preview': False,
    }
    return render(request, 'main/add_transaction.html', context)

@login_required(login_url='log_in')
def report_payments(request):
    """
    Unified payment registration view that handles both roles:
    - Tenant: Reports payment they made (pending confirmation by owner)
    - Owner: Registers payment received (immediately confirmed)
    """
    from .forms import OwnerPaymentForm
    
    if request.user.role == 'O':  # Owner
        # Owner payment registration flow
        if request.method == 'POST':
            form = OwnerPaymentForm(request.POST, user=request.user)
            if form.is_valid():
                try:
                    invoice = form.cleaned_data['invoice']
                    
                    # Validate owner has access to this invoice
                    if invoice.rent.owner != request.user:
                        messages.error(request, "No tienes acceso a esta factura.")
                        return render(request, 'main/report_payment.html', {'form': form, 'user_role': 'O'})
                    
                    # Create Payment record with confirmed status
                    payment = Payment.objects.create(
                        invoice=invoice,
                        amount=form.cleaned_data['amount'],
                        payment_date=form.cleaned_data['payment_date'],
                        payment_method=form.cleaned_data['payment_method'],
                        description=form.cleaned_data['description'],
                        status='confirmed'  # Auto-confirm since owner registered it
                    )
                    
                    # Signal handler will auto-update invoice
                    
                    # Create legacy Transaction record for audit trail
                    transaction = Transaction.objects.create(
                        owner=request.user,
                        tenant=invoice.rent.tenant,
                        property=invoice.rent.property,
                        rent=invoice.rent,
                        amount=form.cleaned_data['amount'],
                        transaction_date=form.cleaned_data['payment_date'],
                        payment_method=form.cleaned_data['payment_method'],
                        type='pago',
                        description=form.cleaned_data['description'],
                        status='confirmed',
                        is_legacy_only=True
                    )
                    
                    # Link payment to transaction for audit trail
                    payment.transaction = transaction
                    payment.save()
                    
                    # Send receipt if requested
                    if form.cleaned_data['send_receipt']:
                        send_receipt_to_tenant(transaction)
                        messages.success(
                            request, 
                            f"Pago registrado por ${form.cleaned_data['amount']:.2f}. "
                            "Recibo enviado al inquilino."
                        )
                    else:
                        messages.success(
                            request, 
                            f"Pago registrado por ${form.cleaned_data['amount']:.2f}."
                        )
                    
                    return redirect('properties')
                    
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Error registering owner payment: {e}")
                    messages.error(request, "Error al registrar el pago. Por favor intenta de nuevo.")
                    return render(request, 'main/report_payment.html', {'form': form, 'user_role': 'O'})
        
        else:
            form = OwnerPaymentForm(user=request.user)
        
        context = {'form': form, 'user_role': 'O'}
        return render(request, 'main/report_payment.html', context)
    
    else:  # Tenant
        # Tenant payment reporting flow (existing behavior)
        if request.method == 'POST':
            form = ReportPaymentForm(request.POST, request.FILES, user=request.user)
            if form.is_valid():
                # Get the uploaded file before saving the transaction
                confirmation_file = request.FILES.get('confirmation_file')
                
                transaction = form.save(commit=False)
                # Set the owner and tenant BEFORE calling save() to ensure proper transaction number generation
                transaction.owner = transaction.property.owner  # Set the owner as the property's owner
                transaction.tenant = request.user  # Set the tenant as the logged-in user
                transaction.status = 'pending'
                # Don't save the confirmation_file to the model
                transaction.confirmation_file = None
                
                # Ensure all required fields are set before saving
                if not transaction.owner:
                    messages.error(request, "Error: No se pudo determinar el propietario de la propiedad.")
                    return render(request, 'main/report_payment.html', {'form': form, 'user_role': 'T'})
                
                transaction.save()
                
                # Send email to owner
                owner_email = transaction.property.owner.email
                confirm_url = request.build_absolute_uri(
                    reverse('confirm_payment', args=[transaction.id])
                )
                # Example for report_payment (sending to owner)
                owner_html = f"""
                    <html>
                      <head>
                        <style>
                          body {{
                            font-family: 'Montserrat', Arial, sans-serif;
                            background: #f8f9fa;
                            color: #344767;
                            margin: 0;
                            padding: 0;
                          }}
                          .container {{
                            text-align: center;
                            max-width: 600px;
                            margin: 40px auto;
                            background: #fff;
                            border-radius: 12px;
                            box-shadow: 0 2px 8px rgba(44,62,80,0.08);
                            padding: 32px 24px;
                          }}
                          .btn {{
                            display: inline-block;
                            background: #17c1e8;
                            color: #fff !important;
                            padding: 12px 28px;
                            border-radius: 6px;
                            text-decoration: none;
                            font-weight: 600;
                            margin-top: 16px;
                          }}
                          .footer {{
                            color: #8392ab;
                            font-size: 13px;
                            margin-top: 32px;
                            text-align: center;
                          }}
                        </style>
                      </head>
                      <body>
                        <div class="container">
                          <h2 style="color:#17c1e8;">Nuevo pago registrado</h2>
                          <p>Se ha registrado un nuevo pago por parte de tu inquilino.</p>
                          <p style="color:#17c1e8;" class="fw-semibold">Una ves confirmes con tu banco, confirma el pago en el siguiente boton y se le enviara un recibo automaticamente a tu inquilino</p>
                          <p>
                            <a href="{confirm_url}" class="btn">Confirmar Pago</a>
                          </p>
                          <div class="footer">
                            Este es un mensaje automático de Finko - Property Management System.
                          </div>
                        </div>
                      </body>
                    </html>
                    """
                
                # Prepare attachments if confirmation file exists
                attachments = []
                if confirmation_file:
                    attachments.append((confirmation_file.name, confirmation_file.read()))
                
                try:
                    send_mailgun_simple(
                        subject="Nuevo pago pendiente de confirmación",
                        html=owner_html,
                        to_emails=owner_email,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        attachments=attachments if attachments else None
                    )
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Failed to send payment notification email: {e}")
                messages.success(request, "Pago registrado. Esperando confirmación del propietario.")
                return redirect('report_payment')
        else:
            form = ReportPaymentForm(user=request.user)
        
        transactions = Transaction.objects.filter(owner=request.user).order_by('-created_at')
        context = {'transactions': transactions, 'form': form, 'user_role': 'T'}
        return render(request, 'main/report_payment.html', context)


@login_required
@require_POST
def get_unpaid_invoices(request):
    """
    AJAX endpoint to fetch unpaid invoices for a selected rent.
    Returns JSON list of invoices with balance information.
    Only accessible to owners.
    """
    if request.user.role != 'O':
        return JsonResponse({'invoices': [], 'error': 'Unauthorized'}, status=403)
    
    rent_id = request.POST.get('rent_id')
    
    if not rent_id:
        return JsonResponse({'invoices': []})
    
    try:
        rent = Rent.objects.get(id=rent_id, owner=request.user)
        invoices = Invoice.objects.filter(
            rent=rent,
            status__in=['pending', 'partial', 'overdue', 'overdue_with_fee']
        ).order_by('-due_date')
        
        invoice_list = [
            {
                'id': inv.id,
                'invoice_number': inv.invoice_number,
                'due_date': inv.due_date.strftime('%Y-%m-%d'),
                'amount': str(inv.amount),
                'paid_amount': str(inv.paid_amount),
                'balance_owed': str(inv.get_balance_owed()),
                'late_fee_amount': str(inv.late_fee_amount or 0),
                'status': inv.status,
                'display': f"{inv.invoice_number} - Vencimiento: {inv.due_date.strftime('%d/%m/%Y')} - Saldo: ${inv.get_balance_owed():.2f}"
            }
            for inv in invoices
        ]
        
        return JsonResponse({'invoices': invoice_list})
    except Rent.DoesNotExist:
        return JsonResponse({'invoices': [], 'error': 'Rent not found'}, status=404)

@login_required(login_url='log_in')
def confirm_payment(request, transaction_id):
    transaction = get_object_or_404(Transaction, id=transaction_id)
    
    # Check if payment is already confirmed
    if transaction.confirmed_at is not None:
        if request.method == 'POST':
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': 'Este pago ya ha sido confirmado previamente.'})
            messages.warning(request, "Este pago ya ha sido confirmado previamente. No se puede confirmar nuevamente.")
            return render(request, 'main/confirm_payment.html', {'transaction': transaction, 'already_confirmed': True})
        else:
            # GET request - show template with confirmation info
            return render(request, 'main/confirm_payment.html', {'transaction': transaction, 'already_confirmed': True})
    
    # Handle rejection via query parameter
    action = request.GET.get('action') or request.POST.get('action')
    if action == 'reject':
        if request.method == 'POST':
            transaction.status = 'rejected'
            transaction.save()
            messages.success(request, "Pago rechazado.")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True})
            return redirect('properties')
        else:
            # Show confirmation dialog for rejection
            return render(request, 'main/confirm_payment.html', {'transaction': transaction, 'confirm_rejection': True})
    
    if request.method == 'POST':
        # Check if this is a resend request
        resend = request.POST.get('resend') or request.GET.get('resend')
        
        # If POST with JSON body (from AJAX), parse it
        if request.content_type == 'application/json':
            import json
            try:
                data = json.loads(request.body)
                resend = data.get('resend', False)
            except:
                pass
        
        if resend:
            # Just resend the email without changing status
            send_receipt_to_tenant(transaction)
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                # Return JSON for AJAX requests
                return JsonResponse({'success': True, 'message': 'Confirmación reenviada exitosamente'})
            messages.success(request, "Confirmación reenviada al inquilino.")
        else:
            # Confirm payment - set confirmed_at timestamp to prevent duplicate confirmations
            from django.utils import timezone
            transaction.status = 'confirmed'
            transaction.type = 'receipt'  # Change type to receipt when confirming
            transaction.is_legacy_only = True  # Mark as legacy
            transaction.confirmed_at = timezone.now()  # Record when confirmation happened
            transaction.save()
            
            # NEW: If linked to rent/invoice, create Payment and update Invoice
            if transaction.rent:
                try:
                    # Get most recent pending invoice for this rent
                    invoice = Invoice.objects.filter(
                        rent=transaction.rent,
                        status__in=['pending', 'partial', 'overdue', 'overdue_with_fee']
                    ).order_by('-due_date').first()
                    
                    if invoice:
                        # Create Payment record
                        payment = Payment.objects.create(
                            invoice=invoice,
                            amount=transaction.amount,
                            payment_date=transaction.transaction_date or date.today(),
                            payment_method=transaction.payment_method,
                            status='confirmed',
                            transaction=transaction,
                            description=transaction.description
                        )
                        
                        # payment.save() will auto-update invoice via signal
                        
                        # Update transaction reference
                        transaction.payment = payment
                        transaction.invoice = invoice
                        transaction.save()
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Failed to link payment to invoice: {e}")
            
            # Generate PDF and send to tenant
            send_receipt_to_tenant(transaction)
            messages.success(request, "Pago confirmado y recibo enviado al inquilino.")
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True})
        return redirect('dashboard')
    return render(request, 'main/confirm_payment.html', {'transaction': transaction})

from django.template.loader import render_to_string
from weasyprint import HTML

def send_receipt_to_tenant(transaction):
    # Skip email if tenant is not registered (non-registered user)
    if not transaction.tenant or not transaction.tenant.email:
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Skipping receipt email for transaction {transaction.id}: tenant is not registered or has no email")
        return
    
    context = {
        'transaction': transaction,
        'logo_base64': get_logo_for_pdf()
    }
    html_string = render_to_string('main/transaction_confirmation.html', context)
    pdf = HTML(string=html_string).write_pdf()
    tenant_email = transaction.tenant.email
    
    email_html = """
        <html>
          <head>
            <style>
              body {
                font-family: 'Montserrat', Arial, sans-serif;
                background: #f8f9fa;
                color: #344767;
                margin: 0;
                padding: 0;
              }
              .container {
                text-align: center;
                max-width: 600px;
                margin: 40px auto;
                background: #fff;
                border-radius: 12px;
                box-shadow: 0 2px 8px rgba(44,62,80,0.08);
                padding: 32px 24px;
              }
              .footer {
                color: #8392ab;
                font-size: 13px;
                margin-top: 32px;
                text-align: center;
              }
            </style>
          </head>
          <body>
            <div class="container">
              <h2 style="color:#17c1e8;">¡Pago confirmado!</h2>
              <p>Tu pago ha sido confirmado exitosamente. Adjuntamos tu recibo en PDF.</p>
              <div class="footer">
                Gracias por usar Finko - Property Management System.
              </div>
            </div>
          </body>
        </html>
        """
    
    attachments = [(f"recibo_{transaction.transaction_number}.pdf", pdf)]
    
    try:
        send_mailgun_simple(
            subject="Recibo de pago confirmado",
            html=email_html,
            to_emails=tenant_email,
            from_email=settings.DEFAULT_FROM_EMAIL,
            attachments=attachments
        )
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to send receipt email: {e}")

@login_required(login_url='log_in')
def expenses(request):
    context= {

    }
    return render(request,'main/expenses.html',context)

def pricing(request):
    context= {

    }
    return render(request,'main/pricing.html',context)

@login_required(login_url='log_in')
def properties(request):
    from main.models import Payment
    properties = Properties.objects.filter(owner=request.user)
    rents = []
    payments = []
    pending_payments = []
    pending_transactions = []
    
    if request.user.role == 'O':
      # If the user is an owner, filter rents by owner
      rents = Rent.objects.filter(owner=request.user,is_active=True)
      # Get last 10 invoices
      invoices_qs = Invoice.objects.filter(rent__owner=request.user).order_by('-due_date')
      payments = invoices_qs[:10]
      # Get pending payments from Payment model (awaiting confirmation)
      pending_payments = Payment.objects.filter(invoice__rent__owner=request.user, status='pending').order_by('-payment_date')
      # Get pending transactions (reported payments from public portal that need approval)
      pending_transactions = Transaction.objects.filter(owner=request.user, type='pago', status='pending').order_by('-created_at')
    elif request.user.role == 'T':
      # If the user is a tenant, filter rents by tenant
      rents = Rent.objects.filter(tenant=request.user, is_active=True)
      # Get confirmed payments (last 10)
      payments_qs = Payment.objects.filter(invoice__rent__tenant=request.user, status='confirmed').order_by('-payment_date')
      payments = payments_qs[:10]
      # Tenants don't have pending approvals
      pending_payments = Payment.objects.none()
      pending_transactions = Transaction.objects.none()

    for rent in rents:
        last_payment = Transaction.objects.filter(rent=rent, type='receipt',status='confirmed').order_by('-created_at').first()
        rent.last_payment_date = last_payment.created_at if last_payment else None
        rent.last_payment_amount = last_payment.amount if last_payment else None
        
        # NEW: Use comprehensive status
        rent_status = get_rent_status(rent)
        rent.days_past_due = rent_status['days_past_due']
        rent.status_display = rent_status['status']
        rent.balance_owed = rent_status['balance_owed']

    # Check for newly created rent contract to auto-open
    new_rent_contract_id = request.session.pop('new_rent_contract_id', None)

    context = {
      'rents': rents,
      'properties':properties,
      'payments':payments,
      'pending_payments': pending_payments,
      'pending_transactions': pending_transactions,
      'new_rent_contract_id': new_rent_contract_id,
    }
    return render(request,'main/properties.html',context)

@login_required(login_url='log_in')
def properties_form(request):
    add_property_form = AddPropertyForm()
    if request.method == 'POST':
        add_property_form = AddPropertyForm(request.POST)
        if add_property_form.is_valid():
            add_property_form.save(user=request.user)  # Pass the logged-in user to the form
            return redirect('properties')
        else:
            print(add_property_form.errors)
            add_property_form = AddPropertyForm()
    context= {
        'error_list': add_property_form.errors,
        'add_property_form':add_property_form,
    }
    return render(request,'main/properties_form.html',context)

def register_tenant(request):
    new_tenant_form = NewTenantForm()
    if request.method == 'POST':
        new_tenant_form = NewTenantForm(request.POST)
        if new_tenant_form.is_valid():
            form = new_tenant_form.save(commit=False)
            form.role = 'T'  # Set the role to 'T' for Inquilino
            form.last_name = form.last_name.capitalize()
            form.first_name = form.first_name.capitalize()
            form.full_name = f"{new_tenant_form.cleaned_data['first_name']} {new_tenant_form.cleaned_data['last_name']}".strip().title()
            form.save()
            return redirect('tenants')
        else:
            print(new_tenant_form.errors)
            new_tenant_form = NewTenantForm()
    context= {
        'new_tenant_form' : new_tenant_form,
    }
    return render(request,'main/register_tenant.html',context)

@login_required(login_url='log_in')
def tenants(request):
    tenants = User.objects.filter(role='T')
    context= {
        'tenants':tenants,
    }
    return render(request,'main/tenants.html',context)

from datetime import date

def get_rent_status(rent):
    """NEW: Replace get_days_past_due with comprehensive status"""
    status_service = RentAccountStatus(rent)
    return status_service.get_status()


def get_days_past_due(rent):
    """LEGACY: Kept for backward compatibility, now uses new system"""
    status = get_rent_status(rent)
    return status['days_past_due']


@login_required(login_url='log_in')
def maintenance(request):
    context= {

    }
    return render(request,'main/maintenance.html',context)

@login_required(login_url='log_in')
def documents(request):
    context= {

    }
    return render(request,'main/documents.html',context)

@login_required(login_url='log_in')
def reports(request):
    context= {

    }
    return render(request,'main/reports.html',context)


@login_required(login_url='log_in')
@xframe_options_sameorigin
def generate_documents(request):
  """Generate letters, reports, and payment history PDFs for users.

  - GET without action: show UI to choose generation options (owners only)
  - Tenants without action are redirected to statement form
  - GET?action=payment_history: returns a PDF with the user's confirmed receipts
  - GET?action=letter or POST?action=letter: show form / generate letter PDF
  - GET?action=statement: statement/account statement generation (all users)
  """
  action = request.GET.get('action')

  # Redirect tenants to statement form if no action specified
  if not action and request.user.role == 'T':
    return redirect(f"{reverse('generate_documents')}?action=statement")

  if action == 'payment_history':
    # Filters: start/end date and properties
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    prop_ids = request.GET.getlist('properties')

    qs = Transaction.objects.filter(type='receipt', status='confirmed')
    if request.user.role == 'O':
      qs = qs.filter(owner=request.user)
    else:
      qs = qs.filter(tenant=request.user)

    if start_date:
      try:
        sd = datetime.strptime(start_date, '%Y-%m-%d').date()
        qs = qs.filter(transaction_date__gte=sd)
      except Exception:
        sd = None
    else:
      sd = None

    if end_date:
      try:
        ed = datetime.strptime(end_date, '%Y-%m-%d').date()
        qs = qs.filter(transaction_date__lte=ed)
      except Exception:
        ed = None
    else:
      ed = None

    if prop_ids:
      try:
        ids = [int(x) for x in prop_ids]
        qs = qs.filter(property__id__in=ids)
      except Exception:
        pass

    transactions = qs.order_by('-transaction_date')

    html_string = render_to_string('main/payment_history_pdf.html', {
      'transactions': transactions,
      'user': request.user,
      'now': date.today(),
      'start_date': sd,
      'end_date': ed,
    })
    pdf = HTML(string=html_string).write_pdf()
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="payment_history_{request.user.id}.pdf"'
    return response

  if action == 'income_letter':
    # Get available years for dropdown
    if request.user.role == 'O':
      transactions = Transaction.objects.filter(owner=request.user, type='receipt', status='confirmed')
    else:
      transactions = Transaction.objects.filter(tenant=request.user, type='receipt', status='confirmed')
    
    available_years = sorted(set(
      t.transaction_date.year for t in transactions 
      if t.transaction_date
    ), reverse=True)
    
    # If no transactions, add current year
    if not available_years:
      available_years = [date.today().year]
    
    # Handle both GET with preview param and POST for generation
    if request.method == 'POST' or request.GET.get('recipient'):
      recipient = request.POST.get('recipient') or request.GET.get('recipient', '')
      year = request.POST.get('year') or request.GET.get('year', str(date.today().year))
      
      try:
        year = int(year)
      except (ValueError, TypeError):
        year = date.today().year
      
      # Fetch all confirmed receipts for the selected year
      if request.user.role == 'O':
        qs = Transaction.objects.filter(
          owner=request.user,
          type='receipt',
          status='confirmed',
          transaction_date__year=year
        )
      else:
        qs = Transaction.objects.filter(
          tenant=request.user,
          type='receipt',
          status='confirmed',
          transaction_date__year=year
        )
      
      # Group income by property
      property_income_dict = {}
      for transaction in qs:
        if transaction.property:
          prop_name = transaction.property.alias or f"Propiedad {transaction.property.id}"
          if prop_name not in property_income_dict:
            property_income_dict[prop_name] = 0
          property_income_dict[prop_name] += float(transaction.amount)
      
      # Convert to list of dicts, sorted by property name
      property_incomes = [
        {'property_name': prop_name, 'total': amount}
        for prop_name, amount in sorted(property_income_dict.items())
      ]
      
      total_income = sum(t.amount for t in qs)
      
      # Format date
      from datetime import datetime as dt
      today = date.today()
      months_es = {
        1: 'enero', 2: 'febrero', 3: 'marzo', 4: 'abril',
        5: 'mayo', 6: 'junio', 7: 'julio', 8: 'agosto',
        9: 'septiembre', 10: 'octubre', 11: 'noviembre', 12: 'diciembre'
      }
      date_formatted = f"{today.day} de {months_es[today.month]} de {today.year}"
      
      # Get user location (using nationality or default)
      #location = request.user.nac.name if request.user.nac else "Panama"
      location = 'Panama'  # Default to Panama for simplicity
      
      html_string = render_to_string('main/income_letter_pdf.html', {
        'recipient': recipient,
        'year': year,
        'user': request.user,
        'date_formatted': date_formatted,
        'location': location,
        'property_incomes': property_incomes,
        'total_income': total_income,
      })
      pdf = HTML(string=html_string).write_pdf()
      response = HttpResponse(pdf, content_type='application/pdf')
      
      # Check if preview mode
      preview = request.GET.get('preview')
      if preview in ['1', 'true', 'yes']:
        response['Content-Disposition'] = 'inline; filename="carta_ingresos_preview.pdf"'
      else:
        response['Content-Disposition'] = f'attachment; filename="carta_ingresos_{year}_{request.user.id}.pdf"'
      return response
    else:
      return render(request, 'main/income_letter_form.html', {
        'available_years': available_years
      })

  if action == 'statement':
    # Statement/Account statement generation by month
    month_str = request.GET.get('month')  # Format: YYYY-MM
    property_id = request.GET.get('property')
    preview = request.GET.get('preview')
    
    # Determine the month range
    property_obj = None
    start_date = None
    end_date = None
    transactions = []
    
    if month_str:
      try:
        # Parse month string (YYYY-MM format)
        month_parts = month_str.split('-')
        year = int(month_parts[0])
        month = int(month_parts[1])
        
        # Get first and last day of the month
        from calendar import monthrange
        last_day = monthrange(year, month)[1]
        start_date = date(year, month, 1)
        end_date = date(year, month, last_day)
      except (ValueError, IndexError):
        start_date = None
        end_date = None
    
    if start_date and end_date:
      qs = Transaction.objects.filter(
        type='receipt', 
        status='confirmed',
        transaction_date__gte=start_date,
        transaction_date__lte=end_date
      )
      
      if request.user.role == 'O':
        qs = qs.filter(owner=request.user)
        # If property is specified, filter by it
        if property_id:
          try:
            prop_id = int(property_id)
            qs = qs.filter(property__id=prop_id)
            property_obj = Properties.objects.get(id=prop_id, owner=request.user)
          except (ValueError, Properties.DoesNotExist):
            pass
      else:
        qs = qs.filter(tenant=request.user)
      
      transactions = qs.order_by('property__alias', '-transaction_date')
    
    # Calculate total amount
    total_amount = sum(t.amount for t in transactions)
    
    months_es = {
      1: 'enero', 2: 'febrero', 3: 'marzo', 4: 'abril',
      5: 'mayo', 6: 'junio', 7: 'julio', 8: 'agosto',
      9: 'septiembre', 10: 'octubre', 11: 'noviembre', 12: 'diciembre'
    }
    
    # Format month display
    month_display = ''
    if start_date:
      month_display = f"{months_es[start_date.month]} de {start_date.year}"
    
    # If request method is POST or if we need to generate PDF
    if request.method == 'POST' or preview:
      html_string = render_to_string('main/statement_pdf.html', {
        'transactions': transactions,
        'user': request.user,
        'property': property_obj,
        'month_display': month_display,
        'total_amount': total_amount,
        'now': date.today(),
        'start_date': start_date,
        'end_date': end_date,
      })
      pdf = HTML(string=html_string).write_pdf()
      response = HttpResponse(pdf, content_type='application/pdf')
      
      # Check if preview mode
      if preview in ['1', 'true', 'yes']:
        response['Content-Disposition'] = 'inline; filename="estado_cuenta_preview.pdf"'
      else:
        if property_obj:
          response['Content-Disposition'] = f'attachment; filename="estado_cuenta_{month_str}_{property_obj.id}_{request.user.id}.pdf"'
        else:
          response['Content-Disposition'] = f'attachment; filename="estado_cuenta_{month_str}_{request.user.id}.pdf"'
      return response
    else:
      # Show form
      if request.user.role == 'O':
        props = Properties.objects.filter(owner=request.user)
      else:
        props = Properties.objects.filter(rent__tenant=request.user).distinct()
      
      # Set default month to current month
      today = date.today()
      current_month = f"{today.year}-{today.month:02d}"
      
      return render(request, 'main/statement_form.html', {
        'properties': props,
        'is_owner': request.user.role == 'O',
        'current_month': current_month,
      })

  # Default: render the generation UI (pass available properties)
  if request.user.role == 'O':
    props = Properties.objects.filter(owner=request.user)
  else:
    # For tenants, show properties they rent
    props = Properties.objects.filter(rent__tenant=request.user).distinct()

  # If preview requested via action=preview
  if action == 'preview':
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    prop_ids = request.GET.getlist('properties')

    qs = Transaction.objects.filter(type='receipt', status='confirmed')
    if request.user.role == 'O':
      qs = qs.filter(owner=request.user)
    else:
      qs = qs.filter(tenant=request.user)

    sd = None
    ed = None
    if start_date:
      try:
        sd = datetime.strptime(start_date, '%Y-%m-%d').date()
        qs = qs.filter(transaction_date__gte=sd)
      except Exception:
        sd = None
    if end_date:
      try:
        ed = datetime.strptime(end_date, '%Y-%m-%d').date()
        qs = qs.filter(transaction_date__lte=ed)
      except Exception:
        ed = None

    if prop_ids:
      try:
        ids = [int(x) for x in prop_ids]
        qs = qs.filter(property__id__in=ids)
      except Exception:
        pass

    transactions = qs.order_by('-transaction_date')
    total = transactions.aggregate(total=models.Sum('amount'))['total'] or 0

    selected_props = Properties.objects.filter(id__in=[int(x) for x in prop_ids]) if prop_ids else None

    return render(request, 'main/payment_summary_preview.html', {
      'transactions': transactions,
      'total': total,
      'start_date': sd,
      'end_date': ed,
      'properties': props,
      'selected_props': selected_props,
      'prop_ids': prop_ids,
    })

  return render(request, 'main/generate_documents.html', {'properties': props})

@login_required(login_url='log_in')
def tenant_portal(request):

    context= {

    }
    return render(request,'main/tenant_portal_home.html',context)


stripe.api_key = settings.STRIPE_SECRET_KEY

@login_required
def create_subscription_checkout_session(request):
    YOUR_DOMAIN = "http://127.0.0.1:8000"
    price_id = "price_1S75xUKCiMsrxq5Opjnf7yCM"  # Replace with your actual Stripe Price ID

    # Create Stripe customer if not exists
    user = request.user
    if not user.stripe_customer_id:
        customer = stripe.Customer.create(email=user.email)
        user.stripe_customer_id = customer.id
        user.save()
    else:
        customer = stripe.Customer.retrieve(user.stripe_customer_id)

    checkout_session = stripe.checkout.Session.create(
        customer=customer.id,
        payment_method_types=['card'],
        line_items=[{
            'price': price_id,
            'quantity': 1,
        }],
        mode='subscription',
        success_url=YOUR_DOMAIN + '/subscription/success/',
        cancel_url=YOUR_DOMAIN + '/subscription/cancel/',
    )
    return JsonResponse({'id': checkout_session.id})

@login_required(login_url='log_in')
def preview_transaction_confirmation(request):
    # Create a dummy transaction object for testing
    dummy_transaction = {
        'transaction_number': 'TXN12345',
        'created_at': datetime.now(),
        'get_type_display': 'Payment',
        'amount': 1500.00,
        'tenant': {
            'full_name': 'John Doe',
            'email': 'johndoe@example.com',
        },
        'property': {
            'alias': 'Luxury Apartment',
            'location': '123 Main St, Springfield',
        },
        'description': 'Monthly Rent Payment',
        'get_payment_method_display': 'Bank Transfer',
        'owner': {
            'full_name': 'Jane Smith',
            'email': 'janesmith@example.com',
        },
    }

    # Render the template with the dummy data
    return render(request, 'main/transaction_confirmation.html', {'transaction': dummy_transaction, 'logo_base64': get_logo_for_pdf()})

def public_payment_portal(request):
    """Public payment portal - no login required"""
    if request.method == 'POST':
        form = PublicPaymentForm(request.POST, request.FILES)
        if form.is_valid():
            # Get form data
            rent_number = form.cleaned_data['rent_number']
            tenant_email = form.cleaned_data['tenant_email']
            transaction_date = form.cleaned_data['transaction_date']
            amount = form.cleaned_data['amount']
            payment_method = form.cleaned_data['payment_method']
            description = form.cleaned_data.get('description', '')
            confirmation_file = request.FILES.get('confirmation_file')
            
            try:
                # Get the rent
                rent = Rent.objects.get(rent_number=rent_number, is_active=True)
                
                # Create transaction
                transaction = Transaction(
                    type='pago',
                    owner=rent.owner,
                    tenant=rent.tenant,
                    property=rent.property,
                    rent=rent,
                    amount=amount,
                    description=description or f'Pago reportado vía portal público - Contrato {rent_number}',
                    payment_method=payment_method,
                    transaction_date=transaction_date,
                    status='pending',
                    confirmation_file=None  # Don't save file to model
                )
                transaction.save()
                
                # Send notification email to owner
                owner_email = rent.owner.email
                confirm_url = request.build_absolute_uri(
                    reverse('confirm_payment', args=[transaction.id])
                )
                
                owner_html = f"""
                    <html>
                      <head>
                        <style>
                          body {{
                            font-family: 'Montserrat', Arial, sans-serif;
                            background: #f8f9fa;
                            color: #344767;
                            margin: 0;
                            padding: 0;
                          }}
                          .container {{
                            max-width: 600px;
                            margin: 40px auto;
                            background: #fff;
                            border-radius: 12px;
                            box-shadow: 0 2px 8px rgba(44,62,80,0.08);
                            padding: 32px 24px;
                          }}
                          .header {{
                            text-align: center;
                            color: #17c1e8;
                            margin-bottom: 24px;
                          }}
                          .info-box {{
                            background: #f8f9fa;
                            border-left: 4px solid #17c1e8;
                            padding: 16px;
                            margin: 16px 0;
                          }}
                          .btn {{
                            display: inline-block;
                            background: #17c1e8;
                            color: #fff !important;
                            padding: 12px 28px;
                            border-radius: 6px;
                            text-decoration: none;
                            font-weight: 600;
                            margin-top: 16px;
                          }}
                          .footer {{
                            color: #8392ab;
                            font-size: 13px;
                            margin-top: 32px;
                            text-align: center;
                          }}
                        </style>
                      </head>
                      <body>
                        <div class="container">
                          <h2 class="header">Nuevo Pago Reportado - Portal Público</h2>
                          <p>Hola {rent.owner.first_name},</p>
                          <p>Se ha reportado un nuevo pago a través del portal público para el contrato <strong>{rent_number}</strong>.</p>
                          
                          <div class="info-box">
                            <strong>Detalles del Pago:</strong><br>
                            <strong>Propiedad:</strong> {rent.property.alias}<br>
                            <strong>Inquilino:</strong> {rent.tenant.full_name if rent.tenant else rent.unregistered_tenant_name}<br>
                            <strong>Monto:</strong> ${amount}<br>
                            <strong>Fecha:</strong> {transaction_date}<br>
                            <strong>Método:</strong> {transaction.get_payment_method_display()}<br>
                            <strong>Número de Transacción:</strong> {transaction.transaction_number}
                          </div>
                          
                          <p>Por favor revisa y confirma este pago en tu panel de control.</p>
                          <p style="text-align: center;">
                            <a href="{confirm_url}" class="btn">Confirmar Pago</a>
                          </p>
                          
                          <div class="footer">
                            Este es un mensaje automático de Finko - Property Management System.
                          </div>
                        </div>
                      </body>
                    </html>
                    """
                
                # Prepare email attachments
                attachments = []
                if confirmation_file:
                    attachments.append((
                        confirmation_file.name,
                        confirmation_file.read()
                    ))
                
                try:
                    send_mailgun_simple(
                        subject=f"Nuevo Pago Reportado - Contrato {rent_number}",
                        html=owner_html,
                        to_emails=owner_email,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        attachments=attachments if attachments else None
                    )
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Failed to send owner notification email: {e}")
                
                # Send confirmation to tenant
                tenant_html = f"""
                    <html>
                      <head>
                        <style>
                          body {{
                            font-family: 'Montserrat', Arial, sans-serif;
                            background: #f8f9fa;
                            color: #344767;
                            margin: 0;
                            padding: 0;
                          }}
                          .container {{
                            max-width: 600px;
                            margin: 40px auto;
                            background: #fff;
                            border-radius: 12px;
                            box-shadow: 0 2px 8px rgba(44,62,80,0.08);
                            padding: 32px 24px;
                          }}
                          .success-icon {{
                            text-align: center;
                            font-size: 48px;
                            color: #82d616;
                            margin-bottom: 16px;
                          }}
                          .info-box {{
                            background: #f8f9fa;
                            border-left: 4px solid #82d616;
                            padding: 16px;
                            margin: 16px 0;
                          }}
                          .footer {{
                            color: #8392ab;
                            font-size: 13px;
                            margin-top: 32px;
                            text-align: center;
                          }}
                        </style>
                      </head>
                      <body>
                        <div class="container">
                          <div class="success-icon">✓</div>
                          <h2 style="color:#82d616; text-align:center;">¡Pago Reportado Exitosamente!</h2>
                          <p>Tu pago ha sido reportado correctamente y está pendiente de confirmación por el propietario.</p>
                          
                          <div class="info-box">
                            <strong>Resumen del Pago:</strong><br>
                            <strong>Contrato:</strong> {rent_number}<br>
                            <strong>Propiedad:</strong> {rent.property.alias}<br>
                            <strong>Monto:</strong> ${amount}<br>
                            <strong>Fecha:</strong> {transaction_date}<br>
                            <strong>Número de Transacción:</strong> {transaction.transaction_number}
                          </div>
                          
                          <p>Recibirás una notificación cuando el propietario confirme el pago.</p>
                          
                          <div class="footer">
                            Este es un mensaje automático de Finko - Property Management System.<br>
                            Para consultas, contacta a tu propietario.
                          </div>
                        </div>
                      </body>
                    </html>
                    """
                
                try:
                    send_mailgun_simple(
                        subject="Confirmación de Reporte de Pago",
                        html=tenant_html,
                        to_emails=tenant_email,
                        from_email=settings.DEFAULT_FROM_EMAIL
                    )
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Failed to send tenant confirmation email: {e}")
                
                # Send confirmation to actual tenant (if different from reporter email)
                actual_tenant_email = rent.tenant.email if rent.tenant else rent.unregistered_tenant_email
                if actual_tenant_email and actual_tenant_email != tenant_email:
                    actual_tenant_html = f"""
                    <html>
                      <head>
                        <style>
                          body {{
                            font-family: 'Montserrat', Arial, sans-serif;
                            background: #f8f9fa;
                            color: #344767;
                            margin: 0;
                            padding: 0;
                          }}
                          .container {{
                            max-width: 600px;
                            margin: 40px auto;
                            background: #fff;
                            border-radius: 12px;
                            box-shadow: 0 2px 8px rgba(44,62,80,0.08);
                            padding: 32px 24px;
                          }}
                          .success-icon {{
                            text-align: center;
                            font-size: 48px;
                            color: #82d616;
                            margin-bottom: 16px;
                          }}
                          .info-box {{
                            background: #f8f9fa;
                            border-left: 4px solid #82d616;
                            padding: 16px;
                            margin: 16px 0;
                          }}
                          .footer {{
                            color: #8392ab;
                            font-size: 13px;
                            margin-top: 32px;
                            text-align: center;
                          }}
                        </style>
                      </head>
                      <body>
                        <div class="container">
                          <div class="success-icon">✓</div>
                          <h2 style="color:#82d616; text-align:center;">¡Pago Reportado Exitosamente!</h2>
                          <p>Tu pago ha sido reportado correctamente y está pendiente de confirmación por el propietario.</p>
                          
                          <div class="info-box">
                            <strong>Resumen del Pago:</strong><br>
                            <strong>Contrato:</strong> {rent_number}<br>
                            <strong>Propiedad:</strong> {rent.property.alias}<br>
                            <strong>Monto:</strong> ${amount}<br>
                            <strong>Fecha:</strong> {transaction_date}<br>
                            <strong>Número de Transacción:</strong> {transaction.transaction_number}
                          </div>
                          
                          <p>Recibirás una notificación cuando el propietario confirme el pago.</p>
                          
                          <div class="footer">
                            Este es un mensaje automático de Finko - Property Management System.<br>
                            Para consultas, contacta a tu propietario.
                          </div>
                        </div>
                      </body>
                    </html>
                    """
                    try:
                        send_mailgun_simple(
                            subject="Confirmación de Reporte de Pago",
                            html=actual_tenant_html,
                            to_emails=actual_tenant_email,
                            from_email=settings.DEFAULT_FROM_EMAIL
                        )
                    except Exception as e:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.error(f"Failed to send actual tenant confirmation email: {e}")
                
                messages.success(request, 
                    f'¡Pago reportado exitosamente! Número de transacción: {transaction.transaction_number}. '
                    'Recibirás una confirmación por correo electrónico.')
                return redirect('public_payment_success')
                
            except Rent.DoesNotExist:
                messages.error(request, 'No se pudo procesar el pago. Verifica el número de contrato.')
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error processing public payment: {e}")
                messages.error(request, 'Ocurrió un error al procesar el pago. Por favor intenta de nuevo.')
        else:
            messages.error(request, 'Por favor corrige los errores en el formulario.')
    else:
        form = PublicPaymentForm()
    
    return render(request, 'main/public_payment_portal.html', {'form': form})

def public_payment_success(request):
    """Success page after payment submission"""
    return render(request, 'main/public_payment_success.html')


# ============================================
# DATA PROTECTION VIEWS (LEY 81 COMPLIANCE)
# ============================================

def privacy_policy(request):
    """Display privacy policy page (Ley 81 compliant)"""
    from django.utils import timezone
    return render(request, 'main/privacy_policy.html', {
        'current_date': timezone.now().strftime('%d de %B de %Y')
    })

def terms_of_service(request):
    """Display terms of service page"""
    from django.utils import timezone
    return render(request, 'main/terms_of_service.html', {
        'current_date': timezone.now().strftime('%d de %B de %Y')
    })

@login_required(login_url='log_in')
def my_data(request):
    """Allow users to view all their personal data (Right to Access - Ley 81)"""
    from .models import AuditLog
    
    user = request.user
    
    # Log this access
    AuditLog.objects.create(
        user=user,
        action='view',
        model_name='User',
        object_id=user.id,
        ip_address=request.META.get('REMOTE_ADDR'),
        details='User accessed their personal data'
    )
    
    # Gather all user data
    user_data = {
        'personal_info': {
            'Nombre': user.first_name,
            'Apellido': user.last_name,
            'Email': user.email,
            'Teléfono': user.phone,
            'Identificación': user.personal_id if hasattr(user, 'personal_id') else 'N/A',
            'Rol': user.get_role_display() if user.role else 'N/A',
        },
        'account_info': {
            'Fecha de registro': user.date_joined.strftime('%d/%m/%Y %H:%M') if user.date_joined else 'N/A',
            'Última actualización': user.last_privacy_update.strftime('%d/%m/%Y %H:%M') if user.last_privacy_update else 'N/A',
            'Plan': user.get_plan_display() if hasattr(user, 'plan') else 'N/A',
        },
        'consents': {
            'Política de Privacidad': f"Aceptada el {user.privacy_policy_accepted_date.strftime('%d/%m/%Y %H:%M')}" if user.privacy_policy_accepted and user.privacy_policy_accepted_date else "No aceptada",
            'Términos y Condiciones': f"Aceptados el {user.terms_accepted_date.strftime('%d/%m/%Y %H:%M')}" if user.terms_accepted and user.terms_accepted_date else "No aceptados",
            'Marketing': "Sí" if user.marketing_consent else "No",
        }
    }
    
    # Add role-specific data
    if user.role == 'O':  # Owner
        user_data['properties'] = Properties.objects.filter(owner=user)
        user_data['rents'] = Rent.objects.filter(owner=user)
        user_data['transactions'] = Transaction.objects.filter(owner=user).order_by('-created_at')[:20]  # Last 20
    elif user.role == 'T':  # Tenant
        user_data['rents'] = Rent.objects.filter(tenant=user)
        user_data['transactions'] = Transaction.objects.filter(tenant=user).order_by('-created_at')[:20]  # Last 20
    
    return render(request, 'main/my_data.html', {'user_data': user_data})


@login_required(login_url='log_in')
def export_my_data(request):
    """Export user data in JSON format (Right to Data Portability - Ley 81)"""
    import json
    from django.http import HttpResponse
    from .models import AuditLog
    
    user = request.user
    
    # Log this export
    AuditLog.objects.create(
        user=user,
        action='export',
        model_name='User',
        object_id=user.id,
        ip_address=request.META.get('REMOTE_ADDR'),
        details='User exported their personal data'
    )
    
    # Compile all user data
    data = {
        'personal_info': {
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email,
            'phone': user.phone,
            'personal_id': user.personal_id if hasattr(user, 'personal_id') else None,
            'role': user.get_role_display() if user.role else None,
            'plan': user.get_plan_display() if hasattr(user, 'plan') else None,
        },
        'account_created': str(user.date_joined) if user.date_joined else None,
        'consents': {
            'privacy_policy': user.privacy_policy_accepted,
            'privacy_policy_date': str(user.privacy_policy_accepted_date) if user.privacy_policy_accepted_date else None,
            'terms_accepted': user.terms_accepted,
            'terms_date': str(user.terms_accepted_date) if user.terms_accepted_date else None,
            'marketing': user.marketing_consent,
        }
    }
    
    # Add role-specific data
    if user.role == 'O':
        data['properties'] = list(Properties.objects.filter(owner=user).values())
        data['rents'] = list(Rent.objects.filter(owner=user).values())
        data['transactions'] = list(Transaction.objects.filter(owner=user).values())
    elif user.role == 'T':
        data['rents'] = list(Rent.objects.filter(tenant=user).values())
        data['payments'] = list(Transaction.objects.filter(tenant=user).values())
    
    # Create JSON response
    response = HttpResponse(
        json.dumps(data, indent=2, default=str),
        content_type='application/json'
    )
    response['Content-Disposition'] = f'attachment; filename="my_data_{user.email}.json"'
    
    return response


@login_required(login_url='log_in')
def delete_my_account(request):
    """Request account deletion (Right to Erasure - Ley 81)"""
    from .models import AuditLog
    
    if request.method == 'POST':
        user = request.user
        
        # Mark for deletion
        from django.utils import timezone
        user.data_deletion_requested = True
        user.data_deletion_request_date = timezone.now()
        user.save()
        
        # Log this request
        AuditLog.objects.create(
            user=user,
            action='delete_request',
            model_name='User',
            object_id=user.id,
            ip_address=request.META.get('REMOTE_ADDR'),
            details='User requested account deletion'
        )
        
        # Send notification to admin
        try:
            send_mailgun_simple(
                subject=f"Solicitud de eliminación de cuenta - {user.email}",
                text=f"El usuario {user.email} ({user.full_name}) ha solicitado la eliminación de su cuenta el {timezone.now().strftime('%d/%m/%Y %H:%M')}.\n\nProcesar conforme a la Ley 81 de Protección de Datos de Panamá.",
                to_emails=settings.ADMINS[0][1] if settings.ADMINS else 'admin@finkoapp.com',
                from_email=settings.DEFAULT_FROM_EMAIL
            )
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to send deletion request notification: {e}")
        
        messages.success(request, 
            "Su solicitud de eliminación de cuenta ha sido registrada. "
            "Procesaremos su solicitud dentro de 30 días hábiles según lo establecido por la Ley 81 de Protección de Datos de Panamá.")
        
        return redirect('home')
    
    return render(request, 'main/delete_account.html')


@login_required(login_url='log_in')
def feedback_form(request):
    """Display feedback form for authenticated users"""
    from .forms import FeedbackForm
    
    if request.method == 'POST':
        form = FeedbackForm(request.POST)
        if form.is_valid():
            feedback = form.save(commit=False)
            feedback.user = request.user
            feedback.save()
            
            # Send email to superusers
            send_feedback_to_superusers(feedback)
            
            messages.success(request, "¡Gracias por tu feedback! Lo hemos recibido y pronto nos comunicaremos contigo si es necesario.")
            return redirect('feedback_success')
    else:
        form = FeedbackForm()
    
    return render(request, 'main/feedback_form.html', {'form': form})


def feedback_success(request):
    """Success page after feedback submission"""
    return render(request, 'main/feedback_success.html')


def send_feedback_to_superusers(feedback):
    """Send feedback notification to all superusers"""
    from django.contrib.auth import get_user_model
    from .mailgun_utils import send_mailgun_simple
    
    User = get_user_model()
    superusers = User.objects.filter(is_superuser=True)
    
    if not superusers.exists():
        return
    
    superuser_emails = [user.email for user in superusers]
    
    feedback_type_display = feedback.get_feedback_type_display()
    
    email_html = f"""
        <html>
          <head>
            <style>
              body {{
                font-family: 'Montserrat', Arial, sans-serif;
                background: #f8f9fa;
                color: #344767;
                margin: 0;
                padding: 0;
              }}
              .container {{
                max-width: 600px;
                margin: 40px auto;
                background: #fff;
                border-radius: 12px;
                box-shadow: 0 2px 8px rgba(44,62,80,0.08);
                padding: 32px 24px;
              }}
              .header {{
                border-bottom: 3px solid #17c1e8;
                padding-bottom: 16px;
                margin-bottom: 24px;
              }}
              .header h2 {{
                color: #17c1e8;
                margin: 0;
              }}
              .feedback-type {{
                display: inline-block;
                background: #e3f2fd;
                color: #1976d2;
                padding: 4px 12px;
                border-radius: 20px;
                font-size: 12px;
                font-weight: bold;
                margin-bottom: 16px;
              }}
              .user-info {{
                background: #f5f5f5;
                padding: 12px 16px;
                border-radius: 8px;
                margin-bottom: 16px;
              }}
              .user-info p {{
                margin: 4px 0;
                font-size: 14px;
              }}
              .message-body {{
                background: #f9f9f9;
                border-left: 4px solid #17c1e8;
                padding: 16px;
                margin: 16px 0;
                border-radius: 4px;
              }}
              .footer {{
                color: #8392ab;
                font-size: 13px;
                margin-top: 24px;
                text-align: center;
                border-top: 1px solid #e0e0e0;
                padding-top: 16px;
              }}
            </style>
          </head>
          <body>
            <div class="container">
              <div class="header">
                <h2>Nuevo Feedback Recibido</h2>
              </div>
              <div class="feedback-type">{feedback_type_display}</div>
              
              <div class="user-info">
                <p><strong>De:</strong> {feedback.user.first_name} {feedback.user.last_name}</p>
                <p><strong>Email:</strong> {feedback.user.email}</p>
                <p><strong>Fecha:</strong> {feedback.created_at.strftime('%d/%m/%Y %H:%M')}</p>
                <p><strong>Asunto:</strong> {feedback.subject}</p>
              </div>
              
              <div class="message-body">
                <strong>Mensaje:</strong>
                <p>{feedback.message.replace(chr(10), '<br>')}</p>
              </div>
              
              <div class="footer">
                Accede al panel de administración para ver todos los feedbacks y responder si es necesario.
              </div>
            </div>
          </body>
        </html>
        """
    
    try:
        send_mailgun_simple(
            subject=f"[Feedback] {feedback_type_display} - {feedback.subject}",
            html=email_html,
            to_emails=superuser_emails,
            from_email=settings.DEFAULT_FROM_EMAIL
        )
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to send feedback email to superusers: {e}")
