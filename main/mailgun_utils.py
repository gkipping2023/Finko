import os
import requests

MAILGUN_API_KEY = os.environ.get("MAILGUN_API_KEY")
MAILGUN_DOMAIN = os.environ.get("MAILGUN_DOMAIN")  # e.g. "mg.yourdomain.com" or "sandboxXXX.mailgun.org"
MAILGUN_BASE_URL = os.environ.get("MAILGUN_API_URL", f"https://api.mailgun.net/v3/{MAILGUN_DOMAIN}/messages")

def send_mailgun_simple(subject: str, text: str = None, html: str = None, to_emails=None, from_email=None, attachments=None):
    """
    Send a simple text or HTML email via Mailgun HTTP API.
    to_emails can be a string or a list of strings.
    Either text or html (or both) must be provided.
    attachments should be a list of tuples: [(filename, file_content), ...]
    Raises requests.HTTPError on failure.
    Returns Mailgun JSON response on success.
    """
    if isinstance(to_emails, str):
        to_emails = [to_emails]
    from_email = from_email or f"FinkoApp <mailgun@{MAILGUN_DOMAIN}>"
    auth = ("api", MAILGUN_API_KEY)
    data = {
        "from": from_email,
        "to": to_emails,
        "subject": subject,
    }
    
    # Add text and/or html content
    if text:
        data["text"] = text
    if html:
        data["html"] = html
    
    # Ensure at least one content type is provided
    if not text and not html:
        raise ValueError("Either text or html content must be provided")
    
    # Handle attachments
    files = []
    if attachments:
        for filename, file_content in attachments:
            files.append(("attachment", (filename, file_content)))
    
    if files:
        resp = requests.post(MAILGUN_BASE_URL, auth=auth, data=data, files=files, timeout=15)
    else:
        resp = requests.post(MAILGUN_BASE_URL, auth=auth, data=data, timeout=15)
    
    # raise for non-2xx so caller sees exact error
    resp.raise_for_status()
    return resp.json()
