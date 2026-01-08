"""
Vercel serverless function entry point for Django WSGI.
"""
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tuning_buddy.settings')

app = get_wsgi_application()
