# PythonAnywhere specific settings
from .settings import *

# Remove Celery-related apps
INSTALLED_APPS = [app for app in INSTALLED_APPS if 'celery' not in app.lower()]

# Remove Celery settings
CELERY_BROKER_URL = None
CELERY_ACCEPT_CONTENT = None
CELERY_TASK_SERIALIZER = None

# PythonAnywhere specific configurations
ALLOWED_HOSTS = ['yourusername.pythonanywhere.com', 'localhost', '127.0.0.1']

# Use file-based cache instead of Redis
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
        'LOCATION': '/tmp/django_cache',
    }
}

# Static files configuration for PythonAnywhere
STATIC_URL = '/static/'
STATIC_ROOT = '/home/yourusername/mysite/static'

MEDIA_URL = '/media/'
MEDIA_ROOT = '/home/yourusername/mysite/media'