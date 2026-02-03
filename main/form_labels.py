# Form Labels Configuration
# This file contains all customizable labels for forms in the application
# You can modify these labels without touching the form code

FORM_LABELS = {
    # NewUserForm labels
    'NewUserForm': {
        'first_name': 'Nombre',
        'last_name': 'Apellido', 
        'phone': 'Teléfono',
        'password1': 'Contraseña',
        'password2': 'Confirmación de Contraseña',
        'email': 'Correo Electrónico',
        'role': '¿Eres Inquilino o Propietario?',
        'username': 'Nombre de Usuario',
    },
    
    # UpdateUserForm labels
    'UpdateUserForm': {
        'first_name': 'Nombre',
        'last_name': 'Apellido',
        'id_type': 'Tipo de Identificación',
        'role': 'Inquilino o Propietario',
        'personal_id': 'Número de Identificación',
        'nac': 'Nacionalidad',
        'dob': 'Fecha de Nacimiento',
        'sex': 'Sexo',
        'promo_code': 'Código Promocional',
    },
    
    # AddPropertyForm labels
    'AddPropertyForm': {
        'alias': 'Nombre de la Propiedad',
        'address': 'Dirección',
        'city': 'Ciudad',
        'state': 'Estado/Provincia',
        'zip_code': 'Código Postal',
        'country': 'País',
        'category': 'Categoría',
        'description': 'Descripción',
        'maint_fee': 'Cuota de Mantenimiento',
        'pictures': 'Fotografías',
    },
    
    # NewRentForm labels
    'NewRentForm': {
        'tenant': 'Inquilino Registrado',
        'start_date': 'Fecha de Inicio',
        'end_date': 'Fecha de Finalización',
        'rent_amount': 'Monto del Alquiler',
        'rent_due_date': 'Día de Vencimiento',
        'next_invoice_date': 'Próxima Fecha de Facturación',
        # Unregistered tenant fields
        'unregistered_tenant_name': 'Nombre Completo (Inquilino No Registrado)',
        'unregistered_tenant_email': 'Correo Electrónico (Inquilino No Registrado)',
        'unregistered_tenant_phone': 'Teléfono (Inquilino No Registrado)',
        'unregistered_tenant_id_type': 'Tipo de Identificación (Inquilino No Registrado)',
        'unregistered_tenant_personal_id': 'Número de Identificación (Inquilino No Registrado)',
        'unregistered_tenant_dob': 'Fecha de Nacimiento (Inquilino No Registrado)',
        'unregistered_tenant_nac': 'Nacionalidad (Inquilino No Registrado)',
        'unregistered_tenant_sex': 'Sexo (Inquilino No Registrado)',
    },
    
    # RenewLeaseForm labels
    'RenewLeaseForm': {
        'start_date': 'Nueva Fecha de Inicio',
        'end_date': 'Nueva Fecha de Finalización',
        'rent_amount': 'Nuevo Monto del Alquiler',
    },
    
    # NewTenantForm labels
    'NewTenantForm': {
        'first_name': 'Nombre',
        'last_name': 'Apellido',
        'phone': 'Teléfono',
        'email': 'Correo Electrónico',
        'personal_id': 'Número de Identificación',
        'id_type': 'Tipo de Identificación',
        'nac': 'Nacionalidad',
        'dob': 'Fecha de Nacimiento',
        'sex': 'Sexo',
        'role': 'Rol',
    },
    
    # TransactionForm labels
    'TransactionForm': {
        'transaction_date': 'Fecha de Transacción',
        'type': 'Tipo de Transacción',
        'rent': 'Contrato de Alquiler',
        'tenant': 'Inquilino',
        'property': 'Propiedad',
        'amount': 'Monto',
        'description': 'Descripción',
        'payment_method': 'Método de Pago',
        'confirmation_file': 'Archivo de Confirmación',
    },
    
    # ReportPaymentForm labels
    'ReportPaymentForm': {
        'transaction_date': 'Fecha del Pago',
        'type': 'Tipo de Transacción',
        'rent': 'Contrato de Alquiler',
        'tenant': 'Inquilino',
        'property': 'Propiedad',
        'amount': 'Monto Pagado',
        'description': 'Descripción del Pago',
        'payment_method': 'Método de Pago',
        'confirmation_file': 'Comprobante de Pago',
    },
}

# Help texts for form fields
FORM_HELP_TEXTS = {
    'NewUserForm': {
        'password1': 'Mínimo 8 caracteres. No puede ser completamente numérica.',
        'password2': 'Ingrese la misma contraseña para verificación.',
        'phone': 'Ingrese su número de teléfono con código de área.',
        'role': 'Seleccione si es inquilino o propietario.',
    },
    
    'UpdateUserForm': {
        'promo_code': 'Código promocional opcional para descuentos.',
        'dob': 'Formato: DD/MM/AAAA',
    },
    
    'AddPropertyForm': {
        'alias': 'Nombre identificativo de la propiedad (ej: Casa Principal, Apartamento 2B)',
        'description': 'Describa las características principales de la propiedad.',
        'maint_fee': 'Cuota mensual de mantenimiento (opcional).',
    },
    
    'NewRentForm': {
        'rent_due_date': 'Día del mes en que vence el alquiler (1-31).',
        'next_invoice_date': 'Si no se especifica, se calculará automáticamente.',
        'unregistered_tenant_name': 'Complete solo si el inquilino no está registrado en el sistema.',
        'unregistered_tenant_email': 'Requerido para inquilinos no registrados.',
    },
    
    'ReportPaymentForm': {
        'confirmation_file': 'Adjunte comprobante de pago, recibo o captura de pantalla.',
        'amount': 'Monto exacto que fue pagado.',
        'description': 'Detalle adicional sobre el pago realizado.',
    },
}

# Placeholders for form fields
FORM_PLACEHOLDERS = {
    'NewUserForm': {
        'first_name': 'Ej: Juan',
        'last_name': 'Ej: Pérez',
        'phone': 'Ej: +507 6123-4567',
        'email': 'ejemplo@correo.com',
        'password1': 'Ingrese su contraseña',
        'password2': 'Confirme su contraseña',
    },
    
    'AddPropertyForm': {
        'alias': 'Ej: Casa Principal, Apartamento 2B',
        'address': 'Ej: Calle 50, Edificio Plaza, Apto 15B',
        'city': 'Ej: Ciudad de Panamá',
        'zip_code': 'Ej: 0823',
        'description': 'Describa las características de la propiedad...',
    },
    
    'NewRentForm': {
        'rent_amount': 'Ej: 850.00',
        'rent_due_date': 'Ej: 5 (día 5 de cada mes)',
        'unregistered_tenant_name': 'Ej: María González',
        'unregistered_tenant_email': 'maria@correo.com',
        'unregistered_tenant_phone': '+507 6987-6543',
    },
    
    'ReportPaymentForm': {
        'amount': 'Ej: 850.00',
        'description': 'Pago de alquiler correspondiente a...',
    },
}