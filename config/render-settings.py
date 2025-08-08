# config/render_settings.py
from .settings import *

# Override settings for Render production
DEBUG = False

# Ensure these are set for production
CSRF_TRUSTED_ORIGINS = [
    'https://dd-ko-maya.onrender.com',
]