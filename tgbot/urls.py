
from django.contrib import admin
from django.urls import path

from tgbot.views import TelegramUserView

app_name = 'tgbot'

urlpatterns = [
    path('', TelegramUserView.as_view(), name='main'),
]
