# Adding Images to PDFs with WeasyPrint - Options & Implementation Guide

## Overview
Your project uses **WeasyPrint** to generate PDFs from HTML templates. Images can be added through multiple methods. Here are the viable options:

---

## Option 1: Local File System Path (Recommended for Logos)
**Best for:** Static logos, icons, watermarks that are part of your application

### Implementation:
```python
from pathlib import Path
from django.conf import settings
from weasyprint import HTML, CSS

def render_transaction_pdf(transaction):
    base_dir = settings.BASE_DIR
    logo_path = base_dir / 'static' / 'assets' / 'img' / 'finko_logo.png'
    
    context = {
        'transaction': transaction,
        'logo_path': f'file://{logo_path}'  # Absolute filesystem URL
    }
    html_string = render_to_string('main/transaction_confirmation.html', context)
    html = HTML(string=html_string)
    pdf = html.write_pdf()
    return pdf
```

### In Template:
```html
<img src="{{ logo_path }}" alt="Logo" class="logo">
```

### Pros:
- Reliable and consistent
- No external dependencies
- Works offline
- Best performance

### Cons:
- Limited to files on your server

---

## Option 2: Base64 Encoded Images (Portable & Self-Contained)
**Best for:** Ensuring PDFs work everywhere without path issues

### Implementation:
```python
import base64
from pathlib import Path
from django.conf import settings

def get_image_as_base64(relative_path):
    """Convert image to base64 for embedding in PDF"""
    image_path = settings.BASE_DIR / relative_path
    with open(image_path, 'rb') as img_file:
        return base64.b64encode(img_file.read()).decode('utf-8')

def render_transaction_pdf(transaction):
    logo_base64 = get_image_as_base64('static/assets/img/finko_logo.png')
    
    context = {
        'transaction': transaction,
        'logo_base64': f'data:image/png;base64,{logo_base64}'
    }
    html_string = render_to_string('main/transaction_confirmation.html', context)
    html = HTML(string=html_string)
    pdf = html.write_pdf()
    return pdf
```

### In Template:
```html
<img src="{{ logo_base64 }}" alt="Logo" class="logo">
```

### Pros:
- Self-contained PDFs
- Works with any path configuration
- No external requests needed
- Ideal for emailing PDFs

### Cons:
- Slightly larger file size
- Encoding/decoding overhead

---

## Option 3: External URLs (CDN or Remote Server)
**Best for:** Dynamic images, images hosted on CDN, remote assets

### Implementation:
```python
def render_transaction_pdf(transaction):
    context = {
        'transaction': transaction,
        'logo_url': 'https://finkoapp.com/static/assets/img/finko_logo.png'
    }
    html_string = render_to_string('main/transaction_confirmation.html', context)
    html = HTML(string=html_string, base_url='https://finkoapp.com')
    pdf = html.write_pdf()
    return pdf
```

### In Template:
```html
<img src="{{ logo_url }}" alt="Logo" class="logo">
```

### Pros:
- Dynamic image sources
- Can use CDN for optimization
- Centralized image management

### Cons:
- Requires internet connection
- Slower than local files
- External dependencies
- Potential CORS issues
- May fail if external service is down

---

## Option 4: Absolute URLs with Base URL (For Production)
**Best for:** Cross-environment compatibility

### Implementation:
```python
from django.conf import settings

def render_transaction_pdf(transaction):
    domain = settings.ALLOWED_HOSTS[0] if settings.ALLOWED_HOSTS else 'localhost:8000'
    protocol = 'https' if not settings.DEBUG else 'http'
    base_url = f'{protocol}://{domain}'
    
    context = {
        'transaction': transaction,
        'static_url': f'{base_url}/static/'
    }
    html_string = render_to_string('main/transaction_confirmation.html', context)
    html = HTML(string=html_string, base_url=base_url)
    pdf = html.write_pdf()
    return pdf
```

### In Template:
```html
<img src="{{ static_url }}assets/img/finko_logo.png" alt="Logo" class="logo">
```

### Pros:
- Works in development and production
- Respects your URL configuration
- Flexible across environments

### Cons:
- Requires internet connection during PDF generation
- Network dependency

---

## Option 5: Hybrid Approach (Recommended for Production)
**Best for:** Production-ready solution with fallbacks

### Implementation:
```python
import base64
from pathlib import Path
from django.conf import settings

def get_embedded_image(relative_path, external_url=None):
    """Get image embedded as base64, with optional external fallback"""
    try:
        image_path = settings.BASE_DIR / relative_path
        if image_path.exists():
            with open(image_path, 'rb') as img_file:
                b64 = base64.b64encode(img_file.read()).decode('utf-8')
                return f'data:image/png;base64,{b64}'
    except Exception as e:
        print(f"Error embedding image: {e}")
    
    # Fallback to external URL if embedding fails
    return external_url or ''

def render_transaction_pdf(transaction):
    context = {
        'transaction': transaction,
        'logo': get_embedded_image(
            'static/assets/img/finko_logo.png',
            external_url='https://finkoapp.com/static/assets/img/finko_logo.png'
        )
    }
    html_string = render_to_string('main/transaction_confirmation.html', context)
    html = HTML(string=html_string)
    pdf = html.write_pdf()
    return pdf
```

### In Template:
```html
<img src="{{ logo }}" alt="Logo" class="logo">
```

### Pros:
- Reliable and self-contained
- Has fallback for external sources
- Works offline and online
- Best of both worlds

### Cons:
- Slightly more complex

---

## WeasyPrint CSS Considerations

### Image Filters
```css
.logo {
    filter: brightness(0) invert(1);  /* Make transparent PNGs white */
    filter: drop-shadow(0 2px 4px rgba(0,0,0,0.1));
}
```

### Sizing for PDFs
```css
img {
    max-width: 100%;
    height: auto;
    page-break-inside: avoid;
}
```

### Background Images
```css
.header {
    background-image: url('data:image/png;base64,...');
    background-size: cover;
    background-position: center;
}
```

---

## Common Issues & Solutions

### Issue: Image not showing in PDF
**Solutions:**
1. Use absolute filesystem path: `file:///Users/george/Documents/GitHub/rentu/...`
2. Use base64 encoding
3. Ensure `base_url` is set correctly

### Issue: CORS errors with external URLs
**Solutions:**
1. Use base64 encoding instead
2. Serve images from same domain
3. Configure CORS on external server

### Issue: Slow PDF generation with external images
**Solutions:**
1. Use local files or base64
2. Optimize image file sizes
3. Cache base64 versions

### Issue: Image path works locally but not in production
**Solutions:**
1. Use `settings.BASE_DIR` for absolute paths
2. Use base64 encoding
3. Use absolute URLs with domain

---

## Recommended Implementation for Your Project

For Finko, I recommend **Option 5 (Hybrid Approach)**:

```python
# In main/views.py

import base64
from pathlib import Path
from django.conf import settings

def get_logo_for_pdf():
    """Get Finko logo embedded as base64 for reliable PDF rendering"""
    logo_path = settings.BASE_DIR / 'static' / 'assets' / 'img' / 'finko_logo.png'
    
    try:
        if logo_path.exists():
            with open(logo_path, 'rb') as f:
                b64 = base64.b64encode(f.read()).decode('utf-8')
                return f'data:image/png;base64,{b64}'
    except Exception as e:
        print(f"Error loading logo: {e}")
    
    return ''

def render_transaction_pdf(transaction):
    context = {
        'transaction': transaction,
        'logo_base64': get_logo_for_pdf()
    }
    html_string = render_to_string('main/transaction_confirmation.html', context)
    html = HTML(string=html_string)
    pdf = html.write_pdf()
    return pdf
```

### In Template:
```html
{% if logo_base64 %}
    <img src="{{ logo_base64 }}" alt="Finko Logo" class="logo-img">
{% endif %}
```

**Benefits:**
- ✅ Works in all environments
- ✅ Self-contained PDFs
- ✅ No external dependencies
- ✅ Fast rendering
- ✅ Perfect for email attachments

---

## Testing Your Implementation

```python
# Quick test in Django shell
from main.views import render_transaction_pdf
from main.models import Transaction

transaction = Transaction.objects.first()
pdf = render_transaction_pdf(transaction)

# Save to file for inspection
with open('test.pdf', 'wb') as f:
    f.write(pdf)
```

---

## Additional Resources

- **WeasyPrint Docs:** https://doc.courtbouillon.org/weasyprint/stable/
- **Image Handling:** https://doc.courtbouillon.org/weasyprint/stable/api_reference.html
- **Base64 Encoding:** Python's built-in `base64` module
