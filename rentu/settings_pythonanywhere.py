# PythonAnywhere specific settings
from .settings import *

# Remove Celery-related apps
INSTALLED_APPS = [app for app in INSTALLED_APPS if 'celery' not in app.lower()]

# Remove Celery settings
CELERY_BROKER_URL = None
CELERY_ACCEPT_CONTENT = None
CELERY_TASK_SERIALIZER = None

# PythonAnywhere specific configurations
ALLOWED_HOSTS = ['finko.pythonanywhere.com', 'localhost', '127.0.0.1']

# Use file-based cache instead of Redis
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
        'LOCATION': '/tmp/django_cache',
    }
}

# MySQL configuration
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'finko$default',
        'USER': 'finko',
        'PASSWORD': os.environ.get('MYSQL_PASSWORD'),
        'HOST': 'finko.mysql.pythonanywhere-services.com',
        'PORT': '3306',
        'OPTIONS': {
            'charset': 'utf8mb4',
            'sql_mode': 'STRICT_TRANS_TABLES',
        },
    }
}

# Static files configuration for PythonAnywhere
STATIC_URL = '/static/'
STATIC_ROOT = '/home/finko/Finko/static'
# Clear STATICFILES_DIRS to avoid conflict with STATIC_ROOT
STATICFILES_DIRS = []

MEDIA_URL = '/media/'
MEDIA_ROOT = '/home/finko/Finko/media'