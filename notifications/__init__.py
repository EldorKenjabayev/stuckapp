"""
Notifications app for asynchronous notification delivery.
Uses Celery for Telegram and other notifications.
"""
default_app_config = 'Fenix.settings'

# Import Celery app
from .celery import app as celery_app

__all__ = ['celery_app']
