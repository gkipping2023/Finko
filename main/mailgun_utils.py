# import os
# import requests

# MAILGUN_API_KEY = os.environ.get("MAILGUN_API_KEY")
# MAILGUN_DOMAIN = os.environ.get("MAILGUN_DOMAIN")  # e.g. "mg.yourdomain.com" or "sandboxXXX.mailgun.org"
# MAILGUN_BASE_URL = os.environ.get("MAILGUN_API_URL", f"https://api.mailgun.net/v3/{MAILGUN_DOMAIN}/messages")

# def send_mailgun_simple(subject: str, text: str = None, html: str = None, to_emails=None, from_email=None, attachments=None):
#     """
#     Send a simple text or HTML email via Mailgun HTTP API.
#     to_emails can be a string or a list of strings.
#     Either text or html (or both) must be provided.
#     attachments should be a list of tuples: [(filename, file_content), ...]
#     Raises requests.HTTPError on failure.
#     Returns Mailgun JSON response on success.
#     """
#     if isinstance(to_emails, str):
#         to_emails = [to_emails]
#     from_email = from_email or f"FinkoApp <mailgun@{MAILGUN_DOMAIN}>"
#     auth = ("api", MAILGUN_API_KEY)
#     data = {
#         "from": from_email,
#         "to": to_emails,
#         "subject": subject,
#     }
    
#     # Add text and/or html content
#     if text:
#         data["text"] = text
#     if html:
#         data["html"] = html
    
#     # Ensure at least one content type is provided
#     if not text and not html:
#         raise ValueError("Either text or html content must be provided")
    
#     # Handle attachments
#     files = []
#     if attachments:
#         for filename, file_content in attachments:
#             files.append(("attachment", (filename, file_content)))
    
#     if files:
#         resp = requests.post(MAILGUN_BASE_URL, auth=auth, data=data, files=files, timeout=15)
#     else:
#         resp = requests.post(MAILGUN_BASE_URL, auth=auth, data=data, timeout=15)
    
#     # raise for non-2xx so caller sees exact error
#     resp.raise_for_status()
#     return resp.json()
import requests
from django.conf import settings
from django.core.mail import EmailMessage
import logging

logger = logging.getLogger(__name__)

def send_mailgun_simple(subject: str, text: str = None, html: str = None, to_emails=None, from_email=None, attachments=None):
    """
    Send a simple text or HTML email via Mailgun HTTP API with fallback support.
    
    Args:
        subject: Email subject
        text: Plain text content (optional)
        html: HTML content (optional)
        to_emails: String or list of recipient emails
        from_email: Sender email (uses DEFAULT_FROM_EMAIL if not provided)
        attachments: List of tuples [(filename, file_content), ...]
    
    Returns:
        Mailgun JSON response on success
    
    Raises:
        ValueError: If neither text nor html is provided
        Exception: If email sending fails
    """
    # Validate inputs
    if not text and not html:
        raise ValueError("Either text or html content must be provided")
    
    if isinstance(to_emails, str):
        to_emails = [to_emails]
    
    # Get configuration from Django settings
    MAILGUN_API_KEY = getattr(settings, 'MAILGUN_API_KEY', None)
    MAILGUN_DOMAIN = getattr(settings, 'MAILGUN_DOMAIN', None)
    MAILGUN_REGION = getattr(settings, 'MAILGUN_REGION', 'US')
    
    # Set default from_email
    if not from_email:
        from_email = settings.DEFAULT_FROM_EMAIL
    
    # Determine API endpoint based on region
    if MAILGUN_REGION == 'EU':
        MAILGUN_BASE_URL = f"https://api.eu.mailgun.net/v3/{MAILGUN_DOMAIN}/messages"
    else:
        MAILGUN_BASE_URL = f"https://api.mailgun.net/v3/{MAILGUN_DOMAIN}/messages"
    
    # Prepare request data
    data = {
        "from": from_email,
        "to": to_emails,
        "subject": subject,
    }
    
    if text:
        data["text"] = text
    if html:
        data["html"] = html
    
    # Prepare attachments
    files = []
    if attachments:
        for filename, file_content in attachments:
            files.append(("attachment", (filename, file_content)))
    
    # Try sending via Mailgun
    try:
        logger.info(f"Attempting to send email via Mailgun to {to_emails}")
        
        if not MAILGUN_API_KEY or not MAILGUN_DOMAIN:
            raise ValueError("Mailgun credentials not configured")
        
        auth = ("api", MAILGUN_API_KEY)
        
        if files:
            resp = requests.post(MAILGUN_BASE_URL, auth=auth, data=data, files=files, timeout=15)
        else:
            resp = requests.post(MAILGUN_BASE_URL, auth=auth, data=data, timeout=15)
        
        resp.raise_for_status()
        logger.info(f"Email sent successfully via Mailgun")
        return resp.json()
    
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout, ValueError) as e:
        # Connection failed - likely PythonAnywhere free tier or network issue
        logger.warning(f"Mailgun connection failed: {e}")
        logger.info("Attempting fallback to Django email backend")
        
        try:
            # Fallback to Django's email backend
            email = EmailMessage(
                subject=subject,
                body=text or "",
                from_email=from_email,
                to=to_emails,
            )
            
            # Set HTML content if provided
            if html:
                email.content_subtype = "html"
                email.body = html
            
            # Add attachments if provided
            if attachments:
                for filename, content in attachments:
                    email.attach(filename, content)
            
            email.send(fail_silently=False)
            logger.info(f"Email sent successfully via Django fallback")
            return {"message": "Email sent via fallback", "status": "fallback"}
        
        except Exception as fallback_error:
            logger.error(f"Both Mailgun and Django email failed: {fallback_error}")
            raise Exception(f"Failed to send email: {fallback_error}")
    
    except requests.exceptions.HTTPError as e:
        # HTTP error from Mailgun API
        logger.error(f"Mailgun HTTP Error {e.response.status_code}: {e.response.text}")
        
        if e.response.status_code == 401:
            raise Exception("Mailgun authentication failed. Check your API key.")
        elif e.response.status_code == 404:
            raise Exception(f"Mailgun domain '{MAILGUN_DOMAIN}' not found. Verify domain in Mailgun dashboard.")
        else:
            raise Exception(f"Mailgun error {e.response.status_code}: {e.response.text}")
    
    except Exception as e:
        logger.error(f"Unexpected error sending email: {e}")
        raise Exception(f"Failed to send email: {e}")