# No changes needed - your existing file is correct
from .settings import *

# Override settings for Render production
DEBUG = False
ALLOWED_HOSTS = ["dd-ko-maya.onrender.com"]

# Ensure these are set for production
CSRF_TRUSTED_ORIGINS = [
    'https://dd-ko-maya.onrender.com',
]