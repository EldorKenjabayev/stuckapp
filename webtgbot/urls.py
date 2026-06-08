from django.urls import path
from . import views

app_name = 'webtgbot'

urlpatterns = [
    # Страницы
    path('', views.index, name='index'),

    # API — Foydalanuvchi
    path('api/register/', views.register, name='register'),
    path('api/specializations/', views.get_specializations, name='specializations'),
    path('api/specialists/<int:spec_id>/', views.get_specialists_by_spec, name='specialists_by_spec'),
    path('api/specialist/<int:sp_id>/photo/', views.get_specialist_photo, name='specialist_photo'),
    path('api/specialist/random/', views.get_random_specialist, name='random_specialist'),
    path('api/groups/', views.get_support_groups, name='support_groups'),
    path('api/request/', views.create_request, name='create_request'),

    # API — Sessiya
    path('api/session/create/', views.create_session, name='create_session'),
    path('api/session/stop/', views.stop_session, name='stop_session'),
    path('api/session/client/active/', views.get_active_session_client, name='client_active_session'),
    path('api/session/<int:session_id>/messages/', views.get_session_messages, name='session_messages'),
    path('api/upload/', views.upload_file, name='upload_file'),
    path('api/internal-notify/', views.internal_notify_chat, name='internal_notify_chat'),
    path('api/internal-notify-stop/', views.internal_notify_chat_stop, name='internal_notify_chat_stop'),
]
