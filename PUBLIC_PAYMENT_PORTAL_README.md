# Public Payment Portal - Feature Documentation

## Overview
The Public Payment Portal allows tenants to report payments without logging into the system. Tenants simply enter their rent number (provided by the property owner) and payment details.

## Features
- **No Login Required**: Tenants can submit payments using just their rent number
- **Email Verification**: The system verifies the tenant's email matches the rent contract
- **Dual Notifications**: Both owner and tenant receive email confirmations
- **File Uploads**: Support for payment confirmation attachments (images/PDF)
- **Pending Status**: Payments are marked as pending until owner confirms

## How It Works

### For Tenants
1. Visit `/pay/` URL
2. Enter rent number (e.g., RENT-1-6-0001)
3. Provide email address registered on the rent contract
4. Fill in payment details:
   - Transaction date
   - Amount paid
   - Payment method
   - Optional description
   - Optional payment confirmation file
5. Submit the form
6. Receive confirmation email with payment details
7. Wait for owner to confirm the payment

### For Owners
1. Receive email notification when tenant submits payment
2. Email includes:
   - Tenant information
   - Payment details
   - Link to confirm the payment in the system
3. Click "Confirm Payment" link or log in to dashboard
4. Review payment details and confirmation file
5. Confirm or reject the payment

## Rent Number Format
Rent numbers follow this format: `RENT-{OWNER_ID}-{PROPERTY_ID}-{SEQUENCE}`

Examples:
- `RENT-1-6-0001` - First rent for owner ID 1, property ID 6
- `RENT-3-2-0005` - Fifth rent for owner ID 3, property ID 2

## Technical Details

### Models
- **Rent**: Added `rent_number` and `rent_sequence_number` fields
  - `rent_number`: Unique identifier (CharField, max 100 chars)
  - `rent_sequence_number`: Sequential number per owner/property combination
  - Auto-generated on save for new rents

### Forms
- **PublicPaymentForm** (`main/forms.py`):
  - Validates rent_number exists and rent is active
  - Verifies tenant_email matches registered email
  - Handles file uploads for payment confirmations
  - All fields have Bootstrap styling

### Views
- **public_payment_portal** (`main/views.py`):
  - GET: Display payment form
  - POST: Process payment submission
  - Creates Transaction with type='pago', status='pending'
  - Sends email to owner (notification with confirm link)
  - Sends email to tenant (confirmation receipt)
  - No authentication required

- **public_payment_success** (`main/views.py`):
  - Success page after payment submission
  - No authentication required

### URLs
- `/pay/` - Public payment portal form
- `/pay/success/` - Payment success confirmation page

### Templates
- `main/templates/main/public_payment_portal.html`:
  - Responsive form with Bootstrap styling
  - Info banner explaining the process
  - Form validation error display
  - Help section for tenants
  - Icons and color scheme matching site design (#17c1e8)

- `main/templates/main/public_payment_success.html`:
  - Success confirmation message
  - Next steps information
  - Link to submit another payment

### Email Notifications
Two emails are sent when payment is submitted:

1. **Owner Notification**:
   - Subject: "Nuevo Pago Reportado - {rent_number}"
   - Contains tenant info, payment details, property info
   - Includes "Confirm Payment" button linking to transaction confirmation
   - Styled with HTML template

2. **Tenant Confirmation**:
   - Subject: "Confirmación de Pago Reportado - {rent_number}"
   - Receipt-style confirmation
   - Payment details summary
   - Next steps information
   - Styled with HTML template

### Management Commands
- **generate_rent_numbers**:
  - Purpose: Generate rent numbers for existing rents
  - Usage: `python manage.py generate_rent_numbers`
  - Useful when upgrading existing system with rent data

## Security Considerations
1. **Email Verification**: Tenant must provide email that matches rent contract
2. **Active Rent Check**: Only active rents can receive payments
3. **Pending Status**: Payments require owner confirmation before being marked paid
4. **File Validation**: Only image and PDF files accepted for confirmations
5. **Rate Limiting**: Consider adding rate limiting in production

## Future Enhancements
- Add CAPTCHA to prevent spam submissions
- SMS notifications in addition to email
- Support for recurring payment reminders
- Payment history view for tenants (by rent number + email)
- QR code generation for rent numbers
- Integration with payment gateways (Stripe, PayPal)

## Deployment Notes
- Ensure Mailgun is configured with proper API credentials
- Test email delivery in staging environment
- Generate rent numbers for existing data before deployment
- Add rate limiting middleware for production
- Consider CDN for static assets (form icons, etc.)

## Testing
To test the feature:
1. Create a rent with a tenant
2. Note the generated rent_number
3. Visit `/pay/` in browser
4. Submit payment using the rent_number and tenant's email
5. Check both owner and tenant emails
6. Log in as owner and confirm the payment

## Support
For issues or questions:
- Check email configuration in `settings.py`
- Review Mailgun logs for email delivery issues
- Ensure rent records have valid tenant emails
- Verify URLs are properly configured in `main/urls.py`
