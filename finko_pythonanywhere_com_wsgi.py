
# +++++++++++ DJANGO +++++++++++
import os
import sys

path = '/home/finko/Finko'  # adjust to your project folder
if path not in sys.path:
    sys.path.append(path)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'rentu.settings')

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
# +++++++++++ END DJANGO +++++++++++