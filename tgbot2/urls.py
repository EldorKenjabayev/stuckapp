
from django.contrib import admin
from django.urls import path

from tgbot2.views import TelegramUserView

app_name = 'tgbot2'

urlpatterns = [
    path('', TelegramUserView.as_view(), name='main'),
]
