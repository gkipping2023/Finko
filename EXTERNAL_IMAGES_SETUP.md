# Setting Up External Image Sources for PDFs

Your Finko project is now using **Option 5 (Hybrid Approach)** for embedding the logo in PDFs. Here's how to use external sources as fallbacks.

## Current Setup

The `get_logo_for_pdf()` function in `main/views.py` now:
1. ✅ Embeds `finko_logo.png` as base64 by default
2. ✅ Accepts an optional fallback external URL
3. ✅ Works in all environments (local, production, PythonAnywhere)

## How to Use an External Image as Fallback

### Option A: Using a CDN (Recommended)

#### 1. Upload Logo to CDN (e.g., Cloudinary, AWS S3, or your own server)

**Example: Cloudinary (Free tier available)**
- Sign up: https://cloudinary.com
- Upload `finko_logo.png`
- Copy the URL (e.g., `https://res.cloudinary.com/your-account/image/upload/v1/finko_logo.png`)

**Example: AWS S3**
- Upload to S3 bucket
- Make file public
- Copy URL (e.g., `https://your-bucket.s3.amazonaws.com/finko_logo.png`)

#### 2. Configure in your Django settings

Add to `rentu/settings.py`:
```python
# Image URLs for PDF generation
EXTERNAL_LOGO_URL = 'https://res.cloudinary.com/your-account/image/upload/v1/finko_logo.png'
```

Or use environment variables:
```python
EXTERNAL_LOGO_URL = os.environ.get('EXTERNAL_LOGO_URL', '')
```

#### 3. Update views.py to use the external URL

```python
# In main/views.py, update the render_transaction_pdf function:

def render_transaction_pdf(transaction):
    context = {
        'transaction': transaction,
        'logo_base64': get_logo_for_pdf(
            fallback_url=settings.EXTERNAL_LOGO_URL
        )
    }
    html_string = render_to_string('main/transaction_confirmation.html', context)
    html = HTML(string=html_string)
    pdf = html.write_pdf()
    return pdf
```

### Option B: Hosting on Your Own Server

#### 1. Ensure static files are accessible

Your static files are already at:
```
/Users/george/Documents/GitHub/rentu/static/assets/img/finko_logo.png
```

#### 2. Configure Django to serve static files in production

In `rentu/settings.py` for production:
```python
if not DEBUG:
    STATIC_URL = 'https://yourdomain.com/static/'
    # or if using PythonAnywhere:
    STATIC_URL = 'https://yourusername.pythonanywhere.com/static/'
```

#### 3. In your views, use the STATIC_URL:

```python
def render_transaction_pdf(transaction):
    logo_url = f'{settings.STATIC_URL}assets/img/finko_logo.png'
    context = {
        'transaction': transaction,
        'logo_base64': get_logo_for_pdf(fallback_url=logo_url)
    }
    html_string = render_to_string('main/transaction_confirmation.html', context)
    html = HTML(string=html_string)
    pdf = html.write_pdf()
    return pdf
```

## Testing Your Configuration

### Test Locally

```bash
# Django shell
python manage.py shell
```

```python
from main.views import get_logo_for_pdf
from django.conf import settings

# Test with local file (default)
logo = get_logo_for_pdf()
print("Has logo:" , bool(logo))
print(f"Logo starts with: {logo[:50]}...")

# Test with fallback URL
logo_with_fallback = get_logo_for_pdf(
    fallback_url='https://yourdomain.com/static/assets/img/finko_logo.png'
)
print("With fallback:", bool(logo_with_fallback))
```

### Test PDF Generation

```python
from main.views import render_transaction_pdf
from main.models import Transaction

transaction = Transaction.objects.first()
pdf = render_transaction_pdf(transaction)

# Save to file
with open('test_receipt.pdf', 'wb') as f:
    f.write(pdf)

print("PDF created! Check test_receipt.pdf")
```

## Environment Variables Setup

### For Local Development
Add to `.env`:
```
EXTERNAL_LOGO_URL=https://res.cloudinary.com/your-account/image/upload/v1/finko_logo.png
```

### For PythonAnywhere Production
1. Go to Web app settings
2. Add environment variables:
   ```
   EXTERNAL_LOGO_URL=https://yourusername.pythonanywhere.com/static/assets/img/finko_logo.png
   ```

Or in `rentu/settings.py`:
```python
EXTERNAL_LOGO_URL = os.environ.get(
    'EXTERNAL_LOGO_URL',
    'https://finkoapp.com/static/assets/img/finko_logo.png'
)
```

## Benefits of Your Current Setup (Hybrid)

✅ **Local Mode** (Default):
- Uses embedded base64 logo
- Zero external dependencies
- Works offline
- Perfect for email attachments
- Fast rendering

✅ **Fallback Mode** (Optional):
- If local file unavailable, uses external URL
- Useful for distributed systems
- CDN-friendly
- Handles edge cases

✅ **Best of Both Worlds**:
- Reliable and self-contained
- Has graceful fallback
- Works everywhere

## Troubleshooting

### Logo not showing in PDF?
1. Verify file exists: `ls -la /Users/george/Documents/GitHub/rentu/static/assets/img/finko_logo.png`
2. Check for errors in terminal
3. Try using fallback URL

### External URL not working?
1. Verify URL is accessible from your server
2. Check CORS headers if using CDN
3. Use online tools to test image URL:
   ```
   curl -I https://your-image-url.com/logo.png
   ```

### PDF generation slow?
1. Local files (base64) will be faster than external URLs
2. If using external URL, consider compressing image
3. Cache base64 if generating many PDFs

## Complete Implementation Example

Here's how your `get_logo_for_pdf()` function works:

```python
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
            # Use local file embedded as base64
            with open(logo_path, 'rb') as f:
                b64 = base64.b64encode(f.read()).decode('utf-8')
                return f'data:image/png;base64,{b64}'
    except Exception as e:
        print(f"Error loading logo for PDF: {e}")
    
    # Return fallback external URL if provided
    return fallback_url or ''
```

## Next Steps (Optional)

If you want to add other images to PDFs:

1. **Add watermark**: Update card-body background-image
2. **Add company seal**: Create separate function like `get_seal_for_pdf()`
3. **Add QR code**: Generate QR code and embed as base64
4. **Add signature**: Same pattern as logo

All images can follow the same hybrid approach!
