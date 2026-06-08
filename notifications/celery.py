"""
Celery configuration for the notifications app.
"""
import os
from celery import Celery

# Set default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Fenix.settings')

app = Celery('Fenix')
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks in all installed apps
app.autodiscover_tasks()

# Load task modules from installed apps
# app.autodiscover_tasks(['notifications'])
