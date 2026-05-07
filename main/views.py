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
from .models import Properties, Rent, User, PromoCode, Roles, Invoice, Payment, Credit, Debit
from .forms import AddPropertyForm, NewUserForm, NewTenantForm, NewRentForm, UpdateUserForm, RenewLeaseForm, PublicPaymentForm, OwnerPaymentForm, TenantPaymentForm, CreditForm, DebitForm
from django_countries.fields import Country  # Add this import if using django-countries
from django.db import models  # Import models for aggregate functions
from django.template.loader import render_to_string
from .filters import InvoiceFilter, PaymentFilter, CreditFilter, DebitFilter
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
def render_payment_pdf(payment):
    context = {
        'payment': payment,
        'logo_base64': get_logo_for_pdf()
    }
    html_string = render_to_string('main/payment_receipt.html', context)
    return HTML(string=html_string).write_pdf()


@login_required(login_url='log_in')
@xframe_options_sameorigin
def payment_pdf(request, payment_id):
    payment = get_object_or_404(Payment, id=payment_id)
    # Security: only allow owner or the tenant of the invoice's rent
    rent = payment.invoice.rent
    if request.user != rent.owner and request.user != rent.tenant:
        messages.error(request, "No tienes acceso a este documento.")
        return redirect('dashboard')
    pdf = render_payment_pdf(payment)
    response = HttpResponse(pdf, content_type='application/pdf')
    preview = request.GET.get('preview')
    disposition = f'inline; filename="Pago_{payment.payment_number}.pdf"' if preview in ['1', 'true', 'yes'] else f'attachment; filename="Pago_{payment.payment_number}.pdf"'
    response['Content-Disposition'] = disposition
    return response


@login_required(login_url='log_in')
def resend_document(request, doc_type, doc_id):
    """Resend a PDF document (invoice, credit, debit, or payment) to the tenant's email."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido.'}, status=405)

    if request.user.role != 'O':
        return JsonResponse({'success': False, 'error': 'No tienes permiso.'}, status=403)

    try:
        if doc_type == 'invoice':
            obj = get_object_or_404(Invoice, id=doc_id, rent__owner=request.user)
            rent = obj.rent
            template = 'main/invoice_pdf.html'
            context = {'invoice': obj, 'logo_base64': get_logo_for_pdf()}
            filename = f"Factura_{obj.invoice_number}.pdf"
            subject = f"Factura {obj.invoice_number}"
            body = f"<p>Adjuntamos tu factura <strong>{obj.invoice_number}</strong>.</p>"
        elif doc_type == 'credit':
            obj = get_object_or_404(Credit, id=doc_id, rent__owner=request.user)
            rent = obj.rent
            template = 'main/credit_pdf.html'
            context = {'credit': obj, 'logo_base64': get_logo_for_pdf()}
            filename = f"Credito_{obj.credit_number}.pdf"
            subject = f"Crédito {obj.credit_number}"
            body = f"<p>Adjuntamos tu nota de crédito <strong>{obj.credit_number}</strong>.</p>"
        elif doc_type == 'debit':
            obj = get_object_or_404(Debit, id=doc_id, rent__owner=request.user)
            rent = obj.rent
            template = 'main/debit_pdf.html'
            context = {'debit': obj, 'logo_base64': get_logo_for_pdf()}
            filename = f"Cargo_{obj.debit_number}.pdf"
            subject = f"Cargo {obj.debit_number}"
            body = f"<p>Adjuntamos tu nota de cargo <strong>{obj.debit_number}</strong>.</p>"
        elif doc_type == 'payment':
            obj = get_object_or_404(Payment, id=doc_id, invoice__rent__owner=request.user)
            rent = obj.invoice.rent
            send_payment_receipt(obj)
            return JsonResponse({'success': True})
        else:
            return JsonResponse({'success': False, 'error': 'Tipo de documento inválido.'}, status=400)

        # Resolve tenant email
        if rent.tenant and rent.tenant.email:
            tenant_email = rent.tenant.email
        elif hasattr(rent, 'unregistered_tenant_email') and rent.unregistered_tenant_email:
            tenant_email = rent.unregistered_tenant_email
        else:
            return JsonResponse({'success': False, 'error': 'El inquilino no tiene un correo registrado.'}, status=400)

        html_string = render_to_string(template, context)
        pdf = HTML(string=html_string).write_pdf()

        email_html = f"""
        <html><body style="font-family:Arial,sans-serif;background:#f8f9fa;color:#344767;">
        <div style="max-width:600px;margin:40px auto;background:#fff;border-radius:12px;padding:32px 24px;text-align:center;">
          <h2 style="color:#17c1e8;">Documento adjunto</h2>
          {body}
          <p style="color:#8392ab;font-size:13px;">Gracias por usar Finko - Property Management System.</p>
        </div></body></html>"""

        send_mailgun_simple(
            subject=subject,
            html=email_html,
            to_emails=tenant_email,
            from_email=settings.DEFAULT_FROM_EMAIL,
            attachments=[(filename, pdf)]
        )
        return JsonResponse({'success': True})

    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"resend_document error: {e}")
        return JsonResponse({'success': False, 'error': 'Error al enviar el documento.'}, status=500)


@login_required(login_url='log_in')
@xframe_options_sameorigin
def invoice_pdf(request, invoice_id):
    invoice = get_object_or_404(Invoice, id=invoice_id)
    rent = invoice.rent
    if request.user != rent.owner and request.user != rent.tenant:
        messages.error(request, "No tienes acceso a este documento.")
        return redirect('dashboard')
    context = {'invoice': invoice, 'logo_base64': get_logo_for_pdf()}
    html_string = render_to_string('main/invoice_pdf.html', context)
    pdf = HTML(string=html_string).write_pdf()
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Factura_{invoice.invoice_number}.pdf"'
    return response


@login_required(login_url='log_in')
@xframe_options_sameorigin
def credit_pdf(request, credit_id):
    credit = get_object_or_404(Credit, id=credit_id)
    if request.user != credit.rent.owner:
        messages.error(request, "No tienes acceso a este documento.")
        return redirect('dashboard')
    context = {'credit': credit, 'logo_base64': get_logo_for_pdf()}
    html_string = render_to_string('main/credit_pdf.html', context)
    pdf = HTML(string=html_string).write_pdf()
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Credito_{credit.credit_number}.pdf"'
    return response


@login_required(login_url='log_in')
@xframe_options_sameorigin
def debit_pdf(request, debit_id):
    debit = get_object_or_404(Debit, id=debit_id)
    if request.user != debit.rent.owner:
        messages.error(request, "No tienes acceso a este documento.")
        return redirect('dashboard')
    context = {'debit': debit, 'logo_base64': get_logo_for_pdf()}
    html_string = render_to_string('main/debit_pdf.html', context)
    pdf = HTML(string=html_string).write_pdf()
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Debito_{debit.debit_number}.pdf"'
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

    # Financial Snapshot — confirmed payments this month
    rent_collected = Payment.objects.filter(
        invoice__rent__owner=user,
        invoice__rent__is_active=True,
        status='confirmed',
        payment_date__gte=month_start,
        payment_date__lte=month_end
    ).aggregate(total=models.Sum('amount'))['total'] or 0

    rent_outstanding = expected_monthly_income - rent_collected

    # Recent confirmed payments
    recent_payments = Payment.objects.filter(
        invoice__rent__owner=user,
        status='confirmed'
    ).order_by('-payment_date').select_related('invoice__rent__property', 'invoice__rent__tenant')[:5]

    last_payment = recent_payments.first() if recent_payments else None

    # Monthly debits (manual charges this month)
    expense_summary = Debit.objects.filter(
        rent__owner=user,
        debit_date__gte=month_start,
        debit_date__lte=month_end
    ).aggregate(total=models.Sum('amount'))['total'] or 0

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
      if tenant_next_rent:
        try:
          tenant_next_rent.days_past_due = get_days_past_due(tenant_next_rent)
        except Exception:
          tenant_next_rent.days_past_due = 0
      tenant_total_paid = Payment.objects.filter(
          invoice__rent__tenant=user, status='confirmed'
      ).aggregate(total=models.Sum('amount'))['total'] or 0
      tenant_recent_payments = Payment.objects.filter(
          invoice__rent__tenant=user, status='confirmed'
      ).order_by('-payment_date').select_related('invoice__rent__property')[:5]

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
        last_pmt = Payment.objects.filter(
            invoice__rent__property=p, status='confirmed'
        ).order_by('-payment_date').first()
        p.last_payment_amount = last_pmt.amount if last_pmt else None
        p.last_payment_date = last_pmt.payment_date if last_pmt else None
        props_with_last.append(p)

      pending_confirmations = Payment.objects.filter(invoice__rent__owner=user, status='pending').count()
      context.update({
        'owner_properties': props_with_last,
        'pending_confirmations': pending_confirmations,
      })

    return render(request, 'main/dashboard.html', context)

from django.core.files.base import ContentFile

@login_required(login_url='log_in')
def invoices(request):
    if request.user.role == 'O':
        qs = Invoice.objects.filter(rent__owner=request.user).order_by('-due_date').select_related('rent__property', 'rent__tenant')
    else:
        qs = Invoice.objects.filter(rent__tenant=request.user).order_by('-due_date').select_related('rent__property')

    invoice_filter = InvoiceFilter(request.GET, queryset=qs, user=request.user)

    context = {
        'invoices': invoice_filter.qs,
        'filter': invoice_filter,
    }
    return render(request, 'main/invoices.html', context)

@login_required(login_url='log_in')
def all_transactions(request):
    """Unified view combining invoices, credits, debits, and payments with filtering."""
    if request.user.role != 'O':
        messages.error(request, "Solo los propietarios pueden ver todas las transacciones.")
        return redirect('dashboard')

    # Get transaction type filter
    transaction_type = request.GET.get('transaction_type', 'all')
    
    # Get rent filter
    rent_id = request.GET.get('rent', '')
    
    # Get date filters
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    # Prepare queryset based on transaction type
    transactions = []
    
    if transaction_type in ['all', 'invoice']:
        invoices_qs = Invoice.objects.filter(rent__owner=request.user).select_related('rent__property', 'rent__tenant')
        if rent_id:
            invoices_qs = invoices_qs.filter(rent_id=rent_id)
        if date_from:
            invoices_qs = invoices_qs.filter(invoice_date__gte=date_from)
        if date_to:
            invoices_qs = invoices_qs.filter(invoice_date__lte=date_to)
        invoices_qs = invoices_qs.order_by('-invoice_date')
        for invoice in invoices_qs:
            transactions.append({
                'type': 'invoice',
                'id': invoice.id,
                'number': invoice.invoice_number,
                'date': invoice.invoice_date,
                'due_date': invoice.due_date,
                'property': invoice.rent.property.alias,
                'rent_number': invoice.rent.rent_number,
                'description': f"Factura de renta",
                'amount': invoice.amount,
                'status': invoice.status,
                'pdf_url': reverse('invoice_pdf', args=[invoice.id]),
            })
    
    if transaction_type in ['all', 'credit']:
        credits_qs = Credit.objects.filter(rent__owner=request.user).select_related('rent__property')
        if rent_id:
            credits_qs = credits_qs.filter(rent_id=rent_id)
        if date_from:
            credits_qs = credits_qs.filter(credit_date__gte=date_from)
        if date_to:
            credits_qs = credits_qs.filter(credit_date__lte=date_to)
        credits_qs = credits_qs.order_by('-credit_date')
        for credit in credits_qs:
            transactions.append({
                'type': 'credit',
                'id': credit.id,
                'number': credit.credit_number,
                'date': credit.credit_date,
                'due_date': None,
                'property': credit.rent.property.alias,
                'rent_number': credit.rent.rent_number,
                'description': credit.description,
                'amount': credit.amount,
                'status': 'credit',
                'pdf_url': reverse('credit_pdf', args=[credit.id]),
            })
    
    if transaction_type in ['all', 'debit']:
        debits_qs = Debit.objects.filter(rent__owner=request.user).select_related('rent__property')
        if rent_id:
            debits_qs = debits_qs.filter(rent_id=rent_id)
        if date_from:
            debits_qs = debits_qs.filter(debit_date__gte=date_from)
        if date_to:
            debits_qs = debits_qs.filter(debit_date__lte=date_to)
        debits_qs = debits_qs.order_by('-debit_date')
        for debit in debits_qs:
            transactions.append({
                'type': 'debit',
                'id': debit.id,
                'number': debit.debit_number,
                'date': debit.debit_date,
                'due_date': None,
                'property': debit.rent.property.alias,
                'rent_number': debit.rent.rent_number,
                'description': debit.description,
                'amount': debit.amount,
                'status': 'debit',
                'pdf_url': reverse('debit_pdf', args=[debit.id]),
            })
    
    if transaction_type in ['all', 'payment']:
        payments_qs = Payment.objects.filter(invoice__rent__owner=request.user).select_related('invoice__rent__property')
        if rent_id:
            payments_qs = payments_qs.filter(invoice__rent_id=rent_id)
        if date_from:
            payments_qs = payments_qs.filter(payment_date__gte=date_from)
        if date_to:
            payments_qs = payments_qs.filter(payment_date__lte=date_to)
        payments_qs = payments_qs.order_by('-payment_date')
        for payment in payments_qs:
            transactions.append({
                'type': 'payment',
                'id': payment.id,
                'number': payment.payment_number,
                'date': payment.payment_date,
                'due_date': None,
                'property': payment.invoice.rent.property.alias,
                'rent_number': payment.invoice.rent.rent_number,
                'description': f"Pago recibido - {payment.payment_method}",
                'amount': payment.amount,
                'status': payment.status,
                'pdf_url': reverse('invoice_pdf', args=[payment.invoice.id]),
            })
    
    # Sort all transactions by date (most recent first)
    transactions.sort(key=lambda x: x['date'], reverse=True)
    
    # Get rents for filter dropdown
    rents = Rent.objects.filter(owner=request.user, is_active=True).select_related('property')
    
    context = {
        'transactions': transactions,
        'transaction_type': transaction_type,
        'rent_id': rent_id,
        'date_from': date_from,
        'date_to': date_to,
        'rents': rents,
    }
    return render(request, 'main/all_transactions.html', context)


def payments(request):
    """View for payments received."""
    if request.user.role != 'O':
        messages.error(request, "Solo los propietarios pueden ver los pagos recibidos.")
        return redirect('dashboard')

    qs = Payment.objects.filter(invoice__rent__owner=request.user).select_related('invoice__rent__property', 'invoice__rent__tenant').order_by('-payment_date')
    
    payment_filter = PaymentFilter(request.GET, queryset=qs, user=request.user)

    context = {
        'payments': payment_filter.qs,
        'filter': payment_filter,
    }
    return render(request, 'main/payments.html', context)


@login_required(login_url='log_in')
def report_payment(request):
    """
    Unified payment registration view:
    - Owner: Registers payment received (immediately confirmed)
    - Tenant: Reports payment made (pending confirmation by owner)
    """
    if request.user.role == 'O':
        if request.method == 'POST':
            form = OwnerPaymentForm(request.POST, user=request.user)
            if form.is_valid():
                try:
                    invoice = form.cleaned_data['invoice']
                    if invoice.rent.owner != request.user:
                        messages.error(request, "No tienes acceso a esta factura.")
                        return render(request, 'main/report_payment.html', {'form': form, 'user_role': 'O'})

                    payment = Payment.objects.create(
                        invoice=invoice,
                        amount=form.cleaned_data['amount'],
                        payment_date=form.cleaned_data['payment_date'],
                        payment_method=form.cleaned_data['payment_method'],
                        description=form.cleaned_data['description'],
                        status='confirmed',
                    )

                    if form.cleaned_data['send_receipt']:
                        send_payment_receipt(payment)
                        messages.success(request, f"Pago registrado por ${form.cleaned_data['amount']:.2f}. Recibo enviado al inquilino.")
                    else:
                        messages.success(request, f"Pago registrado por ${form.cleaned_data['amount']:.2f}.")

                    return redirect('properties')

                except Exception as e:
                    import logging
                    logging.getLogger(__name__).error(f"Error registering owner payment: {e}")
                    messages.error(request, "Error al registrar el pago. Por favor intenta de nuevo.")
        else:
            form = OwnerPaymentForm(user=request.user)

        return render(request, 'main/report_payment.html', {'form': form, 'user_role': 'O'})

    else:  # Tenant
        if request.method == 'POST':
            form = TenantPaymentForm(request.POST, request.FILES, user=request.user)
            if form.is_valid():
                invoice = form.cleaned_data['invoice']
                payment = Payment.objects.create(
                    invoice=invoice,
                    amount=form.cleaned_data['amount'],
                    payment_date=form.cleaned_data['payment_date'],
                    payment_method=form.cleaned_data['payment_method'],
                    description=form.cleaned_data.get('description', ''),
                    confirmation_file=request.FILES.get('confirmation_file'),
                    status='pending',
                )

                owner_email = invoice.rent.owner.email
                confirm_url = request.build_absolute_uri(
                    reverse('confirm_payment', args=[payment.id])
                )
                owner_html = f"""
                    <html><body style="font-family:Arial,sans-serif;color:#344767;background:#f8f9fa;">
                    <div style="max-width:600px;margin:40px auto;background:#fff;border-radius:12px;padding:32px 24px;">
                      <h2 style="color:#17c1e8;text-align:center;">Nuevo Pago Pendiente</h2>
                      <p>Tu inquilino ha reportado un pago de <strong>${payment.amount}</strong> para la factura <strong>{invoice.invoice_number}</strong>.</p>
                      <p style="text-align:center;"><a href="{confirm_url}" style="display:inline-block;background:#17c1e8;color:#fff;padding:12px 28px;border-radius:6px;text-decoration:none;font-weight:600;">Confirmar Pago</a></p>
                      <p style="color:#8392ab;font-size:13px;text-align:center;">Finko - Property Management System</p>
                    </div></body></html>"""

                attachments = []
                if payment.confirmation_file:
                    payment.confirmation_file.seek(0)
                    attachments.append((payment.confirmation_file.name, payment.confirmation_file.read()))

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
                    logging.getLogger(__name__).error(f"Failed to send payment notification: {e}")

                messages.success(request, "Pago reportado. Esperando confirmación del propietario.")
                return redirect('report_payment')
        else:
            form = TenantPaymentForm(user=request.user)

        pending_payments = Payment.objects.filter(
            invoice__rent__tenant=request.user, status='pending'
        ).order_by('-payment_date')
        return render(request, 'main/report_payment.html', {
            'form': form,
            'user_role': 'T',
            'pending_payments': pending_payments,
        })


@login_required
@require_POST
def get_unpaid_invoices(request):
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
def confirm_payment(request, payment_id):
    from django.utils import timezone as tz
    payment = get_object_or_404(Payment, id=payment_id)
    rent = payment.invoice.rent

    # Allow owner or public token confirmation
    if request.user != rent.owner:
        messages.error(request, "No tienes permiso para confirmar este pago.")
        return redirect('dashboard')

    if payment.confirmed_at is not None:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': 'Este pago ya ha sido confirmado previamente.'})
        messages.warning(request, "Este pago ya ha sido confirmado previamente.")
        return render(request, 'main/confirm_payment.html', {'payment': payment, 'already_confirmed': True})

    action = request.GET.get('action') or request.POST.get('action')
    if action == 'reject':
        if request.method == 'POST':
            payment.status = 'rejected'
            payment.save()
            messages.success(request, "Pago rechazado.")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True})
            return redirect('properties')
        return render(request, 'main/confirm_payment.html', {'payment': payment, 'confirm_rejection': True})

    if request.method == 'POST':
        resend = request.POST.get('resend') or request.GET.get('resend')
        if request.content_type == 'application/json':
            import json
            try:
                data = json.loads(request.body)
                resend = data.get('resend', False)
            except Exception:
                pass

        if resend:
            send_payment_receipt(payment)
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'message': 'Confirmación reenviada exitosamente'})
            messages.success(request, "Confirmación reenviada al inquilino.")
        else:
            payment.status = 'confirmed'
            payment.confirmed_at = tz.now()
            payment.save()
            # Signal auto-updates invoice
            send_payment_receipt(payment)
            messages.success(request, "Pago confirmado y recibo enviado al inquilino.")

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True})
        return redirect('dashboard')

    return render(request, 'main/confirm_payment.html', {'payment': payment})

from django.template.loader import render_to_string
from weasyprint import HTML

def send_payment_receipt(payment):
    """Send a payment receipt PDF to the tenant."""
    rent = payment.invoice.rent
    # Determine tenant email
    if rent.tenant and rent.tenant.email:
        tenant_email = rent.tenant.email
    elif rent.unregistered_tenant_email:
        tenant_email = rent.unregistered_tenant_email
    else:
        import logging
        logging.getLogger(__name__).info(f"Skipping receipt email for payment {payment.id}: no tenant email")
        return

    context = {'payment': payment, 'logo_base64': get_logo_for_pdf()}
    html_string = render_to_string('main/payment_receipt.html', context)
    pdf = HTML(string=html_string).write_pdf()

    email_html = """
        <html><body style="font-family:Arial,sans-serif;background:#f8f9fa;color:#344767;">
        <div style="max-width:600px;margin:40px auto;background:#fff;border-radius:12px;padding:32px 24px;text-align:center;">
          <h2 style="color:#17c1e8;">¡Pago confirmado!</h2>
          <p>Tu pago ha sido confirmado exitosamente. Adjuntamos tu recibo en PDF.</p>
          <p style="color:#8392ab;font-size:13px;">Gracias por usar Finko - Property Management System.</p>
        </div></body></html>"""

    try:
        send_mailgun_simple(
            subject="Recibo de pago confirmado",
            html=email_html,
            to_emails=tenant_email,
            from_email=settings.DEFAULT_FROM_EMAIL,
            attachments=[(f"recibo_{payment.payment_number}.pdf", pdf)]
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Failed to send receipt email: {e}")

@login_required(login_url='log_in')
def adjustments(request):
    """View for credits and debits (adjustments to rent accounts)."""
    if request.user.role != 'O':
        messages.error(request, "Solo los propietarios pueden gestionar ajustes.")
        return redirect('dashboard')

    credit_form = CreditForm(user=request.user)
    debit_form = DebitForm(user=request.user)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add_credit':
            credit_form = CreditForm(request.POST, user=request.user)
            if credit_form.is_valid():
                Credit.objects.create(
                    rent=credit_form.cleaned_data['rent'],
                    amount=credit_form.cleaned_data['amount'],
                    credit_date=credit_form.cleaned_data['credit_date'],
                    description=credit_form.cleaned_data['description'],
                    created_by=request.user
                )
                messages.success(request, "Crédito aplicado exitosamente.")
                return redirect('adjustments')
        elif action == 'add_debit':
            debit_form = DebitForm(request.POST, user=request.user)
            if debit_form.is_valid():
                Debit.objects.create(
                    rent=debit_form.cleaned_data['rent'],
                    amount=debit_form.cleaned_data['amount'],
                    debit_date=debit_form.cleaned_data['debit_date'],
                    description=debit_form.cleaned_data['description'],
                    created_by=request.user
                )
                messages.success(request, "Cargo aplicado exitosamente.")
                return redirect('adjustments')

    credits_qs = Credit.objects.filter(rent__owner=request.user).order_by('-credit_date').select_related('rent__property')
    debits_qs = Debit.objects.filter(rent__owner=request.user).order_by('-debit_date').select_related('rent__property')

    credit_filter = CreditFilter(request.GET, queryset=credits_qs, user=request.user)
    debit_filter = DebitFilter(request.GET, queryset=debits_qs, user=request.user)

    context = {
        'credit_form': credit_form,
        'debit_form': debit_form,
        'credits': credit_filter.qs,
        'debits': debit_filter.qs,
        'credit_filter': credit_filter,
        'debit_filter': debit_filter,
    }
    return render(request, 'main/adjustments.html', context)

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
    pending_transactions = []  # kept for template compatibility
    
    if request.user.role == 'O':
      # If the user is an owner, filter rents by owner
      rents = Rent.objects.filter(owner=request.user,is_active=True)
      # Get last 10 invoices
      invoices_qs = Invoice.objects.filter(rent__owner=request.user).order_by('-due_date')
      payments = invoices_qs[:10]
      # Get pending payments from Payment model (awaiting confirmation)
      pending_payments = Payment.objects.filter(invoice__rent__owner=request.user, status='pending').order_by('-payment_date')
      pending_transactions = Payment.objects.none()  # kept for template compat
    elif request.user.role == 'T':
      # If the user is a tenant, filter rents by tenant
      rents = Rent.objects.filter(tenant=request.user, is_active=True)
      # Get confirmed payments (last 10)
      payments_qs = Payment.objects.filter(invoice__rent__tenant=request.user, status='confirmed').order_by('-payment_date')
      payments = payments_qs[:10]
      pending_payments = Payment.objects.none()
      pending_transactions = Payment.objects.none()

    for rent in rents:
        last_payment = Payment.objects.filter(invoice__rent=rent, status='confirmed').order_by('-payment_date').first()
        rent.last_payment_date = last_payment.payment_date if last_payment else None
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
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    prop_ids = request.GET.getlist('properties')

    if request.user.role == 'O':
        qs = Payment.objects.filter(invoice__rent__owner=request.user, status='confirmed').select_related('invoice__rent__property', 'invoice__rent__tenant')
    else:
        qs = Payment.objects.filter(invoice__rent__tenant=request.user, status='confirmed').select_related('invoice__rent__property')

    sd = None
    ed = None
    if start_date:
      try:
        sd = datetime.strptime(start_date, '%Y-%m-%d').date()
        qs = qs.filter(payment_date__gte=sd)
      except Exception:
        pass

    if end_date:
      try:
        ed = datetime.strptime(end_date, '%Y-%m-%d').date()
        qs = qs.filter(payment_date__lte=ed)
      except Exception:
        pass

    if prop_ids:
      try:
        ids = [int(x) for x in prop_ids]
        qs = qs.filter(invoice__rent__property__id__in=ids)
      except Exception:
        pass

    payments_list = qs.order_by('-payment_date')

    if payments_list.exists():
      if not sd:
        sd = payments_list.last().payment_date
      if not ed:
        ed = payments_list.first().payment_date

    total_amount = payments_list.aggregate(total=models.Sum('amount'))['total'] or 0

    html_string = render_to_string('main/payment_history_pdf.html', {
      'payments': payments_list,
      'user': request.user,
      'now': date.today(),
      'start_date': sd,
      'end_date': ed,
      'total_amount': total_amount,
      'logo_base64': get_logo_for_pdf(),
    })
    pdf = HTML(string=html_string).write_pdf()
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="payment_history_{request.user.id}.pdf"'
    return response

  if action == 'income_letter':
    if request.user.role == 'O':
        payments_qs = Payment.objects.filter(invoice__rent__owner=request.user, status='confirmed')
    else:
        payments_qs = Payment.objects.filter(invoice__rent__tenant=request.user, status='confirmed')

    available_years = sorted(set(
      p.payment_date.year for p in payments_qs if p.payment_date
    ), reverse=True)

    if not available_years:
      available_years = [date.today().year]

    if request.method == 'POST' or request.GET.get('recipient'):
      recipient = request.POST.get('recipient') or request.GET.get('recipient', '')
      year = request.POST.get('year') or request.GET.get('year', str(date.today().year))

      try:
        year = int(year)
      except (ValueError, TypeError):
        year = date.today().year

      if request.user.role == 'O':
        qs = payments_qs.filter(payment_date__year=year)
      else:
        qs = payments_qs.filter(payment_date__year=year)

      # Group income by property
      property_income_dict = {}
      for p in qs:
        prop_name = p.invoice.rent.property.alias or f"Propiedad {p.invoice.rent.property.id}"
        if prop_name not in property_income_dict:
          property_income_dict[prop_name] = 0
        property_income_dict[prop_name] += float(p.amount)

      property_incomes = [
        {'property_name': prop_name, 'total': amount}
        for prop_name, amount in sorted(property_income_dict.items())
      ]

      total_income = sum(p.amount for p in qs)

      from datetime import datetime as dt
      today = date.today()
      months_es = {
        1: 'enero', 2: 'febrero', 3: 'marzo', 4: 'abril',
        5: 'mayo', 6: 'junio', 7: 'julio', 8: 'agosto',
        9: 'septiembre', 10: 'octubre', 11: 'noviembre', 12: 'diciembre'
      }
      date_formatted = f"{today.day} de {months_es[today.month]} de {today.year}"
      location = 'Panama'

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
      if request.user.role == 'O':
        qs = Payment.objects.filter(
          status='confirmed',
          payment_date__gte=start_date,
          payment_date__lte=end_date,
          invoice__rent__owner=request.user
        ).select_related('invoice__rent__property', 'invoice__rent__tenant')
        if property_id:
          try:
            prop_id = int(property_id)
            qs = qs.filter(invoice__rent__property__id=prop_id)
            property_obj = Properties.objects.get(id=prop_id, owner=request.user)
          except (ValueError, Properties.DoesNotExist):
            pass
      else:
        qs = Payment.objects.filter(
          status='confirmed',
          payment_date__gte=start_date,
          payment_date__lte=end_date,
          invoice__rent__tenant=request.user
        ).select_related('invoice__rent__property')

      payments_list = qs.order_by('invoice__rent__property__alias', '-payment_date')
    else:
      payments_list = Payment.objects.none()
    
    # Also fetch Invoices for the period (what was billed)
    if start_date and end_date:
      inv_qs = Invoice.objects.filter(
        invoice_date__gte=start_date,
        invoice_date__lte=end_date
      ).select_related('rent', 'rent__property', 'rent__tenant', 'rent__owner')
      if request.user.role == 'O':
        inv_qs = inv_qs.filter(rent__owner=request.user)
        if property_id:
          try:
            prop_id = int(property_id)
            inv_qs = inv_qs.filter(rent__property__id=prop_id)
          except ValueError:
            pass
      else:
        inv_qs = inv_qs.filter(rent__tenant=request.user)
      invoices_list = inv_qs.order_by('rent__property__alias', 'due_date')
    else:
      invoices_list = Invoice.objects.none()

    total_amount = sum(p.amount for p in payments_list)
    invoices_total_billed = sum(i.amount for i in invoices_list)
    invoices_total_paid = sum(i.paid_amount for i in invoices_list)
    invoices_total_outstanding = sum(i.get_balance_owed() for i in invoices_list)
    
    months_es = {
      1: 'enero', 2: 'febrero', 3: 'marzo', 4: 'abril',
      5: 'mayo', 6: 'junio', 7: 'julio', 8: 'agosto',
      9: 'septiembre', 10: 'octubre', 11: 'noviembre', 12: 'diciembre'
    }
    
    # Format month display
    month_display = ''
    if start_date:
      month_display = f"{months_es[start_date.month]} de {start_date.year}"
    
    # If request method is POST, preview, or month param supplied (GET download)
    if request.method == 'POST' or preview or month_str:
      html_string = render_to_string('main/statement_pdf.html', {
        'payments': payments_list,
        'invoices': invoices_list,
        'invoices_total_billed': invoices_total_billed,
        'invoices_total_paid': invoices_total_paid,
        'invoices_total_outstanding': invoices_total_outstanding,
        'user': request.user,
        'property': property_obj,
        'month_display': month_display,
        'total_amount': total_amount,
        'now': date.today(),
        'start_date': start_date,
        'end_date': end_date,
        'logo_base64': get_logo_for_pdf(),
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

    if request.user.role == 'O':
      qs = Payment.objects.filter(status='confirmed', invoice__rent__owner=request.user).select_related('invoice__rent__property', 'invoice__rent__tenant')
    else:
      qs = Payment.objects.filter(status='confirmed', invoice__rent__tenant=request.user).select_related('invoice__rent__property')

    sd = None
    ed = None
    if start_date:
      try:
        sd = datetime.strptime(start_date, '%Y-%m-%d').date()
        qs = qs.filter(payment_date__gte=sd)
      except Exception:
        pass
    if end_date:
      try:
        ed = datetime.strptime(end_date, '%Y-%m-%d').date()
        qs = qs.filter(payment_date__lte=ed)
      except Exception:
        pass

    if prop_ids:
      try:
        ids = [int(x) for x in prop_ids]
        qs = qs.filter(invoice__rent__property__id__in=ids)
      except Exception:
        pass

    payments_preview = qs.order_by('-payment_date')
    total = payments_preview.aggregate(total=models.Sum('amount'))['total'] or 0

    selected_props = Properties.objects.filter(id__in=[int(x) for x in prop_ids]) if prop_ids else None

    return render(request, 'main/payment_summary_preview.html', {
      'payments': payments_preview,
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

def public_payment_portal(request):
    """Public payment portal - no login required"""
    if request.method == 'POST':
        form = PublicPaymentForm(request.POST, request.FILES)
        if form.is_valid():
            rent_number = form.cleaned_data['rent_number']
            tenant_email = form.cleaned_data['tenant_email']
            payment_date = form.cleaned_data['payment_date']
            amount = form.cleaned_data['amount']
            payment_method = form.cleaned_data['payment_method']
            description = form.cleaned_data.get('description', '')
            confirmation_file = request.FILES.get('confirmation_file')

            try:
                rent = Rent.objects.get(rent_number=rent_number, is_active=True)

                # Find the most recent unpaid invoice for this rent
                invoice = Invoice.objects.filter(
                    rent=rent,
                    status__in=['pending', 'partial', 'overdue', 'overdue_with_fee']
                ).order_by('-due_date').first()

                if not invoice:
                    messages.error(request, 'No hay facturas pendientes para este contrato.')
                    return render(request, 'main/public_payment_portal.html', {'form': form})

                payment = Payment(
                    invoice=invoice,
                    amount=amount,
                    payment_date=payment_date,
                    payment_method=payment_method,
                    description=description or f'Pago reportado vía portal público - Contrato {rent_number}',
                    status='pending',
                )
                if confirmation_file:
                    payment.confirmation_file = confirmation_file
                payment.save()

                owner_email = rent.owner.email
                confirm_url = request.build_absolute_uri(
                    reverse('confirm_payment', args=[payment.id])
                )
                tenant_name = rent.tenant.full_name if rent.tenant else (rent.unregistered_tenant_name or 'Inquilino')

                owner_html = f"""
                    <html><body style="font-family:Arial,sans-serif;background:#f8f9fa;color:#344767;">
                    <div style="max-width:600px;margin:40px auto;background:#fff;border-radius:12px;padding:32px 24px;">
                      <h2 style="color:#17c1e8;text-align:center;">Nuevo Pago Reportado - Portal Público</h2>
                      <p>Hola {rent.owner.first_name},</p>
                      <p>Se ha reportado un pago para el contrato <strong>{rent_number}</strong>.</p>
                      <div style="background:#f8f9fa;border-left:4px solid #17c1e8;padding:16px;margin:16px 0;">
                        <strong>Propiedad:</strong> {rent.property.alias}<br>
                        <strong>Inquilino:</strong> {tenant_name}<br>
                        <strong>Monto:</strong> ${amount}<br>
                        <strong>Fecha:</strong> {payment_date}<br>
                        <strong>Método:</strong> {payment.get_payment_method_display()}<br>
                        <strong>Número de Pago:</strong> {payment.payment_number}
                      </div>
                      <p style="text-align:center;">
                        <a href="{confirm_url}" style="display:inline-block;background:#17c1e8;color:#fff;padding:12px 28px;border-radius:6px;text-decoration:none;font-weight:600;">Confirmar Pago</a>
                      </p>
                    </div></body></html>"""

                try:
                    send_mailgun_simple(
                        subject=f"Nuevo Pago Reportado - Contrato {rent_number}",
                        html=owner_html,
                        to_emails=owner_email,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                    )
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).error(f"Failed to send owner notification: {e}")

                tenant_html = f"""
                    <html><body style="font-family:Arial,sans-serif;background:#f8f9fa;color:#344767;">
                    <div style="max-width:600px;margin:40px auto;background:#fff;border-radius:12px;padding:32px 24px;text-align:center;">
                      <h2 style="color:#82d616;">¡Pago Reportado Exitosamente!</h2>
                      <div style="background:#f8f9fa;border-left:4px solid #82d616;padding:16px;margin:16px 0;text-align:left;">
                        <strong>Contrato:</strong> {rent_number}<br>
                        <strong>Monto:</strong> ${amount}<br>
                        <strong>Número de Pago:</strong> {payment.payment_number}
                      </div>
                      <p>Recibirás una notificación cuando el propietario confirme el pago.</p>
                    </div></body></html>"""

                for email in filter(None, [tenant_email]):
                    try:
                        send_mailgun_simple(
                            subject="Confirmación de Reporte de Pago",
                            html=tenant_html,
                            to_emails=email,
                            from_email=settings.DEFAULT_FROM_EMAIL
                        )
                    except Exception as e:
                        import logging
                        logging.getLogger(__name__).error(f"Failed to send tenant confirmation: {e}")

                messages.success(request,
                    f'¡Pago reportado exitosamente! Número: {payment.payment_number}. '
                    'Recibirás una confirmación por correo electrónico.')
                return redirect('public_payment_success')

            except Rent.DoesNotExist:
                messages.error(request, 'No se pudo procesar el pago. Verifica el número de contrato.')
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Error processing public payment: {e}")
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
        user_data['payments'] = Payment.objects.filter(invoice__rent__owner=user).order_by('-payment_date')[:20]
    elif user.role == 'T':  # Tenant
        user_data['rents'] = Rent.objects.filter(tenant=user)
        user_data['payments'] = Payment.objects.filter(invoice__rent__tenant=user).order_by('-payment_date')[:20]
    
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
        data['payments'] = list(Payment.objects.filter(invoice__rent__owner=user).order_by('-payment_date').values())
    elif user.role == 'T':
        data['rents'] = list(Rent.objects.filter(tenant=user).values())
        data['payments'] = list(Payment.objects.filter(invoice__rent__tenant=user).order_by('-payment_date').values())
    
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
