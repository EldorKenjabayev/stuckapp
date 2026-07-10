import json
import logging
import os
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.shortcuts import render, get_object_or_404
from django.contrib.auth import authenticate, login, update_session_auth_hash
from django.utils import timezone
from django.conf import settings
from .models import (
    WebUser,
    ChatSession, ChatMessage, SupportGroup, UserRequest,
    SESSION_DURATION_MINUTES
)
from tgbot.models import Specialist, Specialization
from .utils import forward_web_message_to_telegram


logger = logging.getLogger(__name__)


def get_client_ip(request):
    """Mijoz IP manzilini aniqlash (nginx proxy orqasida)"""
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if x_forwarded:
        return x_forwarded.split(',')[0].strip()
    x_real = request.META.get('HTTP_X_REAL_IP', '')
    if x_real:
        return x_real
    return request.META.get('REMOTE_ADDR', '0.0.0.0')


def is_ip_blocked(ip):
    """IP bloklanganligini tekshirish"""
    try:
        from .models import BlockedIP
        return BlockedIP.objects.filter(ip_address=ip, is_active=True).exists()
    except Exception:
        return False


def index(request):
    """Главная страница — веб-чат приложение"""
    return render(request, 'webtgbot/index.html')

@csrf_exempt
@require_http_methods(["POST"])
def register(request):
    """Регистрация пользователя по имени"""
    try:
        ip = get_client_ip(request)

        # IP bloklanganmi?
        if is_ip_blocked(ip):
            return JsonResponse({'error': 'Доступ ограничен'}, status=403)

        # Har bir IP ga faqat 1 ta akkunt
        existing = WebUser.objects.filter(ip_address=ip).first()
        if existing:
            logger.warning(f"IP {ip} qayta register qilmoqchi, oldingi akkunti: {existing.name}")
            return JsonResponse({
                'error': 'Вы уже регистрировались ранее'
            }, status=429)

        data = json.loads(request.body)
        name = data.get('name', '').strip()
        if not name or len(name) < 2:
            return JsonResponse({'error': 'Имя должно содержать минимум 2 символа'}, status=400)
        if len(name) > 50:
            return JsonResponse({'error': 'Имя слишком длинное'}, status=400)

        user = WebUser.objects.create(name=name, ip_address=ip)
        return JsonResponse({
            'success': True,
            'user': {
                'id': user.id,
                'name': user.name,
                'token': user.session_token,
            }
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
@csrf_exempt
def get_specializations(request):
    """Получить список специализаций"""
    specs = Specialization.objects.all()
    data = [{
        'id': s.id,
        'name': s.name,
        'count': s.specialist_set.filter(is_active=True).count(),
    } for s in specs]
    return JsonResponse({'specializations': data})


@csrf_exempt
def get_specialists_by_spec(request, spec_id):
    """Получить специалистов по специализации"""
    specialists = Specialist.objects.filter(
        specialization_id=spec_id,
        is_active=True
    ).select_related('specialization', 'telegram_user')

    data = []
    for sp in specialists:
        name = sp.name if sp.name else sp.telegram_user.first_name
        photo_url = f"/chat/api/specialist/{sp.id}/photo/" if sp.photo_id else None
        data.append({
            'id': sp.id,
            'name': name,
            'specialization': sp.specialization.name,
            'description': sp.description,
            'photo': photo_url,
            'price': float(sp.price or 0.0),
            'rating': float(sp.rating or 0.0),
            'is_online': True,
        })
    return JsonResponse({'specialists': data})


@csrf_exempt
async def get_specialist_photo(request, sp_id):
    """Telegramdan mutaxassis rasmini olib berish (Asinxron va Lokal kesh bilan)"""
    from tgbot.dispatcher import bot
    import aiohttp
    import aiofiles
    from django.http import HttpResponse, Http404
    from django.conf import settings
    from asgiref.sync import sync_to_async
    try:
        # Mutaxassisni bazadan asinxron olamiz
        specialist = await sync_to_async(get_object_or_404)(Specialist, id=sp_id)
        photo_id = specialist.photo_id
        if not photo_id:
            logger.warning(f"Specialist {sp_id} has no photo_id")
            return HttpResponse(status=404)

        # Kesh katalogini yaratish
        cache_dir = os.path.join(settings.MEDIA_ROOT, 'specialists_cache')
        await sync_to_async(os.makedirs)(cache_dir, exist_ok=True)
        
        # Har bir photo_id uchun alohida nom bilan faylni saqlash
        local_file_path = os.path.join(cache_dir, f"{photo_id}.jpg")

        # Agar rasm lokal keshda bo'lsa, uni tezda va asinxron o'qib beramiz
        if await sync_to_async(os.path.exists)(local_file_path):
            async with aiofiles.open(local_file_path, 'rb') as f:
                content = await f.read()
                return HttpResponse(content, content_type='image/jpeg')

        if bot is None:
            logger.error("Telegram bot is not initialized (bot is None)")
            return HttpResponse("Bot initialization error", status=500)

        # 1. Telegramdan fayl yo'lini olish (to'g'ridan-to'g'ri await)
        try:
            file = await bot.get_file(photo_id)
        except Exception as te:
            logger.error(f"Telegram get_file error for {photo_id}: {te}")
            return HttpResponse(f"TG Error: {te}", status=500)

        # 2. Faylni asinxron yuklab olish va keshga saqlash
        file_url = f"https://api.telegram.org/file/bot{bot.token}/{file.file_path}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(file_url) as response:
                if response.status == 200:
                    content = await response.read()
                    async with aiofiles.open(local_file_path, 'wb') as f:
                        await f.write(content)
                    return HttpResponse(content, content_type='image/jpeg')
                else:
                    logger.error(f"Telegram file download failed: HTTP {response.status}")
                    return HttpResponse(f"Download error: {response.status}", status=500)

    except Exception as e:
        logger.exception(f"Unexpected error in get_specialist_photo for ID {sp_id}")
        return HttpResponse(f"Internal error: {str(e)}", status=500)


@csrf_exempt
def get_random_specialist(request):
    """Получить случайного специалиста (тиндер)"""
    exclude_id = request.GET.get('exclude', None)
    qs = Specialist.objects.filter(is_active=True).select_related('specialization', 'telegram_user')
    if exclude_id:
        qs = qs.exclude(id=exclude_id)
    specialist = qs.order_by('?').first()
    if not specialist:
        return JsonResponse({'specialist': None})

    name = specialist.name if specialist.name else specialist.telegram_user.first_name
    photo_url = f"/chat/api/specialist/{specialist.id}/photo/" if specialist.photo_id else None
    return JsonResponse({
        'specialist': {
            'id': specialist.id,
            'name': name,
            'specialization': specialist.specialization.name,
            'description': specialist.description,
            'photo': photo_url,
            'price': float(specialist.price or 0.0),
            'rating': float(specialist.rating or 0.0),
            'is_online': True,
        }
    })


@csrf_exempt
def get_support_groups(request):
    """Получить группы поддержки"""
    groups = SupportGroup.objects.all()
    data = [{
        'id': g.id,
        'name': g.name,
        'url': g.url,
    } for g in groups]
    return JsonResponse({'groups': data})


@csrf_exempt
@csrf_exempt
@require_http_methods(["POST"])
def create_request(request):
    """Оставить запрос"""
    try:
        data = json.loads(request.body)
        name = data.get('name', '').strip()
        contact = data.get('contact', '').strip()
        problem = data.get('problem', '').strip()
        
        if not name or not problem or not contact:
            return JsonResponse({'error': 'Заполните все поля'}, status=400)

        # Bazaga saqlash
        user_request = UserRequest.objects.create(
            name=name, 
            contact=contact, 
            problem=problem
        )

        # Telegramga yuborish
        try:
            from tgbot.dispatcher import bot
            chat_send = -1002019476345
            
            txt = f"🆕 <b>Новая заявка с WEB-сайта!</b>\n\n"
            txt += f"👤 <b>Имя:</b> {name}\n"
            txt += f"📞 <b>Контакт:</b> {contact}\n"
            txt += f"📝 <b>Проблема:</b> {problem}"
            
            async_to_sync(bot.send_message)(
                chat_id=chat_send,
                text=txt,
                parse_mode="HTML"
            )
        except Exception as tg_err:
            logger.error(f"Web request TG yuborishda xato: {tg_err}")

        return JsonResponse({'success': True, 'id': user_request.id})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def create_session(request):
    """Создать сессию чата между клиентом и специалистом"""
    try:
        ip = get_client_ip(request)

        # IP bloklanganmi?
        if is_ip_blocked(ip):
            return JsonResponse({'error': 'Доступ ограничен'}, status=403)

        data = json.loads(request.body)
        token = data.get('token', '').strip()
        specialist_id = data.get('specialist_id')

        if not token or not specialist_id:
            return JsonResponse({'error': 'Недостаточно данных'}, status=400)

        try:
            client = WebUser.objects.get(session_token=token, is_active=True)
        except WebUser.DoesNotExist:
            return JsonResponse({'error': 'Пользователь не найден'}, status=404)

        specialist = get_object_or_404(Specialist, id=specialist_id, is_active=True)

        # Проверяем, была ли УЖЕ сессия в прошлом
        past_session = ChatSession.objects.filter(
            client=client, specialist=specialist
        ).first()

        if past_session and not past_session.is_active:
            return JsonResponse({
                'error': 'Вы уже использовали свою 30-минутную бесплатную сессию с этим специалистом.'
            }, status=400)

        # Проверяем активную сессию клиента со ВСЕМИ специалистами
        active_client_session = ChatSession.objects.filter(
            client=client, is_active=True
        ).first()
        if active_client_session:
            if active_client_session.is_expired:
                active_client_session.end_session()
            else:
                return JsonResponse({
                    'success': True,
                    'reconnected': True,
                    'session': {
                        'id': active_client_session.id,
                        'specialist_name': active_client_session.specialist.name or active_client_session.specialist.telegram_user.first_name,
                        'specialist_photo': f"/chat/api/specialist/{active_client_session.specialist.id}/photo/" if active_client_session.specialist.photo_id else None,
                        'expires_at': active_client_session.expires_at.isoformat(),
                        'remaining_seconds': active_client_session.remaining_seconds,
                    }
                })

        # 1. Проверяем активную сессию в ВЕБ (ChatSession)
        active_spec_session = ChatSession.objects.filter(
            specialist=specialist, is_active=True
        ).first()
        if active_spec_session:
            if active_spec_session.is_expired:
                active_spec_session.end_session()
            else:
                return JsonResponse({
                    'error': 'Этот специалист сейчас занят в другом веб-чате.'
                }, status=400)

        # 2. Проверяем активную сессию в TELEGRAM (Relation)
        # В модели Specialist поле client указывает на активного ТГ-клиента
        if specialist.client is not None:
            return JsonResponse({
                'error': 'Этот специалист сейчас проводит консультацию в Telegram.'
            }, status=400)

        session = ChatSession.objects.create(
            client=client,
            specialist=specialist,
            expires_at=timezone.now() + timezone.timedelta(minutes=SESSION_DURATION_MINUTES),
        )

        try:
            telegram_id = specialist.telegram_user.telegram_id
            if telegram_id:
                from asgiref.sync import async_to_sync
                from tgbot.logics.notify import notify_web_session
                async_to_sync(notify_web_session)(
                    specialist_telegram_id=telegram_id,
                    client_name=client.name,
                    session_id=session.id
                )
        except Exception as e:
            logger.error(f"Telegram notify yuborishda xatolik: {e}")

        return JsonResponse({
            'success': True,
            'session': {
                'id': session.id,
                'specialist_name': specialist.name or specialist.telegram_user.first_name,
                'specialist_photo': f"/chat/api/specialist/{specialist.id}/photo/" if specialist.photo_id else None,
                'expires_at': session.expires_at.isoformat(),
                'remaining_seconds': session.remaining_seconds,
            }
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def stop_session(request):
    """Завершить активную сессию"""
    try:
        data = json.loads(request.body)
        token = data.get('token', '').strip()
        session_id = data.get('session_id')

        if token:
            # Клиент завершает сессию
            try:
                client = WebUser.objects.get(session_token=token)
                session = ChatSession.objects.get(id=session_id, client=client, is_active=True)
            except (WebUser.DoesNotExist, ChatSession.DoesNotExist):
                return JsonResponse({'error': 'Сессия не найдена'}, status=404)
        else:
            return JsonResponse({'error': 'Специалисты могут завершать чат только через Telegram'}, status=403)

        # Specialist ma'lumotlarini oldindan saqlaymiz
        specialist_tg_id = None
        client_name = session.client.name
        session_id_val = session.id
        try:
            specialist_tg_id = session.specialist.telegram_user.telegram_id
        except Exception:
            pass

        # Sessiyani tugatamiz
        session.end_session()

        # 1. WebSocket orqali chatdagi ikki tomonga session_expired yuboramiz
        channel_layer = get_channel_layer()
        try:
            async_to_sync(channel_layer.group_send)(
                f"chat_{session_id_val}",
                {
                    "type": "session_expired_notification",
                    "message": f"Клиент {client_name} завершил сессию. Спасибо за общение! 🙏"
                }
            )
        except Exception as ws_err:
            logger.error(f"WebSocket session_expired yuborishda xato: {ws_err}")

        # 2. Specialistga Telegram orqali xabar yuboramiz
        if specialist_tg_id:
            try:
                from tgbot.logics.notify import notify_session_ended
                async_to_sync(notify_session_ended)(
                    specialist_telegram_id=specialist_tg_id,
                    client_name=client_name
                )
            except Exception as tg_err:
                logger.error(f"Specialistga xabar yuborishda xato: {tg_err}")

        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def upload_file(request):
    """Загрузка медиа-файла"""
    try:
        token = request.POST.get('token', '')
        session_id = request.POST.get('session_id')
        message_type = request.POST.get('type', 'file')
        file = request.FILES.get('file')

        if not file:
            return JsonResponse({'error': 'Файл не загружен'}, status=400)

        # Ограничение размера файла: 20 МБ
        if file.size > 20 * 1024 * 1024:
            return JsonResponse({'error': 'Файл слишком большой (макс. 20 МБ)'}, status=400)

        # Проверяем тип файла
        allowed_types = {
            'image': ['image/jpeg', 'image/png', 'image/gif', 'image/webp'],
            'audio': ['audio/mpeg', 'audio/wav', 'audio/ogg', 'audio/webm', 'audio/mp4'],
            'voice': ['audio/webm', 'audio/ogg', 'audio/wav', 'audio/mpeg', 'audio/mp4'],
            'file': None,  # Любой тип
        }
        if message_type in allowed_types and allowed_types[message_type]:
            if file.content_type not in allowed_types[message_type]:
                return JsonResponse({'error': f'Недопустимый тип файла для {message_type}'}, status=400)

        # Определяем отправителя
        sender_type = 'client'
        session = None

        if token:
            try:
                client = WebUser.objects.get(session_token=token)
                session = ChatSession.objects.get(id=session_id, client=client, is_active=True)
                sender_type = 'client'
            except (WebUser.DoesNotExist, ChatSession.DoesNotExist):
                return JsonResponse({'error': 'Сессия не найдена'}, status=404)
        else:
            return JsonResponse({'error': 'Специалисты могут отправлять файлы только через Telegram'}, status=403)

        if session.is_expired:
            session.end_session()
            return JsonResponse({'error': 'Сессия истекла'}, status=400)

        msg = ChatMessage.objects.create(
            session=session,
            sender_type=sender_type,
            message_type=message_type,
            file=file,
        )

        # 🚀 Telegramga (mutaxassisga) yuborish
        async_to_sync(forward_web_message_to_telegram)(msg.id)

        return JsonResponse({
            'success': True,
            'message': {
                'id': msg.id,
                'type': msg.message_type,
                'file_url': msg.file.url,
                'sender': msg.sender_type,
                'time': msg.created_at.strftime('%H:%M'),
            }
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
def internal_notify_chat(request):
    """
    Ichki API: Bot jarayonidan Web serverga xabarni ko'prik qilish.
    InMemoryChannelLayer ishlatilganda ikki jarayon o'rtasida real-time aloqa uchun zarur.
    """
    session_id = request.POST.get('session_id')
    message_id = request.POST.get('message_id')
    msg_type = request.POST.get('type', 'message') # 'message' yoki 'typing'
    
    if not session_id:
        return JsonResponse({'error': 'No session_id'}, status=400)
        
    channel_layer = get_channel_layer()
    
    if msg_type == 'typing':
        # "Pechataet" holatini ko'rsatish
        async_to_sync(channel_layer.group_send)(
            f"chat_{session_id}",
            {
                "type": "typing_indicator",
                "sender": "specialist"
            }
        )
        return JsonResponse({'success': True})

    try:
        msg = ChatMessage.objects.select_related('session').get(id=message_id)
        
        # Real-time xabarni yuborish
        async_to_sync(channel_layer.group_send)(
            f"chat_{session_id}",
            {
                "type": "chat_message",
                "message": {
                    "id": msg.id,
                    "content": msg.content,
                    "sender": msg.sender_type,
                    "message_type": msg.message_type,
                    "file_url": msg.file.url if msg.file else None,
                    "time": msg.created_at.strftime("%H:%M"),
                    "is_read": False,
                }
            }
        )
        return JsonResponse({'success': True})
    except ChatMessage.DoesNotExist:
        return JsonResponse({'error': 'Message not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)





@csrf_exempt
@require_http_methods(["POST"])
def get_active_session_client(request):
    """Получить активную сессию клиента по токену"""
    try:
        data = json.loads(request.body)
        token = data.get('token', '').strip()
        if not token:
            return JsonResponse({'session': None})

        try:
            client = WebUser.objects.get(session_token=token, is_active=True)
        except WebUser.DoesNotExist:
            return JsonResponse({'session': None})

        active_session = ChatSession.objects.filter(client=client, is_active=True).first()
        if active_session:
            if active_session.is_expired:
                active_session.end_session()
                return JsonResponse({'session': None})
            
            return JsonResponse({
                'session': {
                    'id': active_session.id,
                    'specialist_name': active_session.specialist.name or active_session.specialist.telegram_user.first_name,
                    'specialist_photo': f"/chat/api/specialist/{active_session.specialist.id}/photo/" if active_session.specialist.photo_id else None,
                    'expires_at': active_session.expires_at.isoformat(),
                    'remaining_seconds': active_session.remaining_seconds,
                }
            })
        return JsonResponse({'session': None})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def get_session_messages(request, session_id):
    """Получить историю сообщений сессии"""
    try:
        session = ChatSession.objects.get(id=session_id, is_active=True)
    except ChatSession.DoesNotExist:
        return JsonResponse({'error': 'Сессия не найдена'}, status=404)

    messages = session.messages.order_by('created_at')
    data = []
    for m in messages:
        msg_data = {
            'id': m.id,
            'sender': m.sender_type,
            'type': m.message_type,
            'content': m.content,
            'is_read': m.is_read,
            'time': m.created_at.strftime('%H:%M'),
        }
        if m.file:
            msg_data['file_url'] = m.file.url
        data.append(msg_data)

    return JsonResponse({'messages': data})

@csrf_exempt
def internal_notify_chat_stop(request):
    """
    Ichki API: Bot jarayonidan Web serverga sessiya to'xtatilgani haqida xabar yuborish.
    """
    session_id = request.POST.get('session_id')
    if not session_id:
        return JsonResponse({'error': 'No session_id'}, status=400)
        
    channel_layer = get_channel_layer()
    try:
        async_to_sync(channel_layer.group_send)(
            f"chat_{session_id}",
            {
                "type": "session_expired_notification",
                "message": "Специалист завершил сессию. Спасибо за общение! 🙏"
            }
        )
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)



