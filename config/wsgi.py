import os
from django.core.wsgi import get_wsgi_application

# Use your existing IS_RENDER variable
if os.environ.get('IS_RENDER'):
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.render_settings')
else:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

application = get_wsgi_application()