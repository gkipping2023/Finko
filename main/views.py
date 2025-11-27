from django.views.decorators.http import require_POST
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
import re
import stripe
from datetime import date, datetime, timedelta
from django.utils.timezone import now
# import calendar
from django.urls import reverse
from django.conf import settings
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, get_backends
from django.contrib.auth.decorators import login_required
from .models import Properties, Transaction,Rent,User, PromoCode, Roles
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


#PDF Generation Function
def render_transaction_pdf(transaction):
    html_string = render_to_string('main/transaction_confirmation.html', {'transaction': transaction})
    html = HTML(string=html_string)
    pdf = html.write_pdf()
    return pdf

#Download Pdf Function
@login_required(login_url='log_in')
def transaction_pdf(request, transaction_id):
    transaction = get_object_or_404(Transaction, id=transaction_id)
    pdf = render_transaction_pdf(transaction)
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Transaccion_{transaction.transaction_number}.pdf"'
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
    rent = get_object_or_404(Rent, id=rent_id, owner=request.user)
    data = {
        'tenant_id': rent.tenant.id,
        'property_id': rent.property.id,
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
        
        # Send email notification
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
                to_email=settings.DEFAULT_FROM_EMAIL,
                subject=email_subject,
                body=email_body
            )
            messages.success(request, 'Tu mensaje ha sido enviado exitosamente. Te contactaremos pronto.')
        except Exception as e:
            messages.error(request, 'Hubo un error al enviar tu mensaje. Por favor intenta de nuevo.')
        
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
    collected_income = Transaction.objects.filter(owner=user, type='receipt', status='confirmed').aggregate(total=models.Sum('amount'))['total'] or 0
    pending_income = Transaction.objects.filter(owner=user, type='receipt', status='pending').aggregate(total=models.Sum('amount'))['total'] or 0
    upcoming_renewals = Rent.objects.filter(owner=user, end_date__gte=datetime.now(), end_date__lte=datetime.now() + timedelta(days=30)).count()

    # Financial Snapshot
    rent_collected = collected_income
    rent_outstanding = pending_income
    recent_payments = Transaction.objects.filter(owner=user, type='receipt').order_by('-transaction_date')[:5]
    last_payment = Transaction.objects.filter(owner=user, type='receipt').order_by('-transaction_date')[:1] # Get the second most recent payment
    expense_summary = Transaction.objects.filter(owner=user, type='debit').aggregate(total=models.Sum('amount'))['total'] or 0
    net_cash_flow = collected_income - expense_summary

    # Alerts / Notifications
    overdue_rent_alerts = Rent.objects.filter(owner=user, status=True).count()  # Customize logic for overdue rents
    leases_expiring_soon = Rent.objects.filter(owner=user, end_date__gte=datetime.now(), end_date__lte=datetime.now() + timedelta(days=30)).count()
    pending_maintenance_requests = Properties.objects.filter(owner=user, maint_status='requested').count()

    context = {
        'last_payment': last_payment,
        'total_properties': total_properties,
        'occupancy_rate': occupancy_rate,
        'collected_income': collected_income,
        'pending_income': pending_income,
        'upcoming_renewals': upcoming_renewals,
        'rent_collected': rent_collected,
        'rent_outstanding': rent_outstanding,
        'recent_payments': recent_payments,
        'expense_summary': expense_summary,
        'net_cash_flow': net_cash_flow,
        'overdue_rent_alerts': overdue_rent_alerts,
        'leases_expiring_soon': leases_expiring_soon,
        'pending_maintenance_requests': pending_maintenance_requests,
    }
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
            transaction = form.save(commit=False)
            transaction.owner = request.user  # Set the logged-in user as the owner
            transaction.status = 'confirmed' 
            transaction.save()
            pdf = render_transaction_pdf(transaction)
            messages.success(request, f"¡{transaction.get_type_display()} creado exitosamente!")
            return redirect('transaction_pdf', transaction_id=transaction.id)  # Redirect to a transaction list or dashboard
        else:
            messages.error(request, "Hubo un error al crear la transacción.")
    else:
        form = TransactionForm(user=request.user)
    context = {
        'form': form,
    }
    return render(request, 'main/add_transaction.html', context)

@login_required(login_url='log_in')
def report_payments(request):
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
                return render(request, 'main/report_payment.html', {'form': form})
            
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
    context = {'transactions': transactions, 'form': form}
    return render(request, 'main/report_payment.html', context)

@login_required(login_url='log_in')
def confirm_payment(request, transaction_id):
    transaction = get_object_or_404(Transaction, id=transaction_id)
    if request.method == 'POST':
        transaction.status = 'confirmed'
        transaction.type = 'receipt' #Cambia el tipo de pago a recibo al confirmar.
        transaction.save()
        # Generate PDF and send to tenant (see next step)
        send_receipt_to_tenant(transaction)
        messages.success(request, "Pago confirmado y recibo enviado al inquilino.")
        return redirect('dashboard')
    return render(request, 'main/confirm_payment.html', {'transaction': transaction})

from django.template.loader import render_to_string
from weasyprint import HTML

def send_receipt_to_tenant(transaction):
    html_string = render_to_string('main/transaction_confirmation.html', {'transaction': transaction})
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
    properties = Properties.objects.filter(owner=request.user)
    rents = []
    payments = []
    if request.user.role == 'O':
        # If the user is an owner, filter rents by owner
        rents = Rent.objects.filter(owner=request.user,is_active=True)
        payments = Transaction.objects.filter(owner=request.user, type='receipt').order_by('-transaction_date')[:10]
    elif request.user.role == 'T':
        # If the user is a tenant, filter rents by tenant
        rents = Rent.objects.filter(tenant=request.user, is_active=True)
        payments = Transaction.objects.filter(tenant=request.user, type='receipt').order_by('-created_at')[:10]

    for rent in rents:
        last_payment = Transaction.objects.filter(rent=rent, type='receipt',status='confirmed').order_by('-created_at').first()
        rent.last_payment_date = last_payment.created_at if last_payment else None
        rent.last_payment_amount = last_payment.amount if last_payment else None
        rent.days_past_due = get_days_past_due(rent)

    context = {
        'rents': rents,
        'properties':properties,
        'payments':payments,
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

def get_days_past_due(rent):
    today = date.today()
    # Calculate the due date for this month
    due_day = rent.rent_due_date
    try:
        due_date = date(today.year, today.month, due_day)
    except ValueError:
        # Handles months with fewer days (e.g., Feb 30)
        from calendar import monthrange
        last_day = monthrange(today.year, today.month)[1]
        due_date = date(today.year, today.month, last_day)

    # Calculate total confirmed payments for current month
    first_day_of_month = date(today.year, today.month, 1)
    total_payments = Transaction.objects.filter(
        rent=rent, 
        type='receipt', 
        status='confirmed',
        transaction_date__gte=first_day_of_month
    ).aggregate(total=models.Sum('amount'))['total'] or 0

    # If confirmed payments cover the full rent amount, not past due
    if total_payments >= rent.rent_amount:
        return 0

    # If today is before or on due date, not past due
    if today <= due_date:
        return 0

    # Otherwise, calculate days past due
    return (today - due_date).days


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
    return render(request, 'main/transaction_confirmation.html', {'transaction': dummy_transaction})

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
