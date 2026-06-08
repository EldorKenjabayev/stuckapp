import json
import os
from asgiref.sync import async_to_sync
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from django.conf import settings
from aiogram.types import FSInputFile
from .models import ChatSession, ChatMessage, WebUser
from .utils import forward_web_message_to_telegram
from tgbot.dispatcher import bot
from tgbot.models import Specialist


class ChatConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer для реального времени чата"""

    async def connect(self):
        self.session_id = self.scope['url_route']['kwargs']['session_id']
        self.room_group_name = f'chat_{self.session_id}'

        # Подключаемся к группе чата
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

        # Отправляем информацию о сессии
        session_info = await self.get_session_info()
        if session_info:
            await self.send(text_data=json.dumps({
                'type': 'session_info',
                'data': session_info
            }))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        msg_type = data.get('type', 'message')

        if msg_type == 'message':
            await self.handle_message(data)
        elif msg_type == 'typing':
            await self.handle_typing(data)
        elif msg_type == 'read':
            await self.handle_read(data)
        elif msg_type == 'file_sent':
            await self.handle_file_notification(data)
        elif msg_type == 'session_check':
            session_info = await self.get_session_info()
            if session_info:
                await self.send(text_data=json.dumps({
                    'type': 'session_info',
                    'data': session_info
                }))

    async def handle_message(self, data):
        """Обработка текстового/стикер сообщения"""
        content = data.get('content', '')
        sender = data.get('sender', 'client')
        message_type = data.get('message_type', 'text')

        # Проверяем сессию
        is_valid = await self.check_session_valid()
        if not is_valid:
            await self.send(text_data=json.dumps({
                'type': 'session_expired',
                'message': 'Сессия истекла. Спасибо за общение! 🙏'
            }))
            return

        # Сохраняем сообщение в БД
        msg = await self.save_message(content, sender, message_type)

        # Отправляем в группу чата (веб-интерфейс)
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': {
                    'id': msg['id'],
                    'content': content,
                    'sender': sender,
                    'message_type': message_type,
                    'time': msg['time'],
                    'is_read': False,
                }
            }
        )

        # 🚀 Telegramga yuborish (agar mijoz yozgan bo'lsa)
        if sender == 'client':
            await forward_web_message_to_telegram(msg['id'])

    async def handle_typing(self, data):
        """Отправка индикатора печатания"""
        sender = data.get('sender', 'client')
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'typing_indicator',
                'sender': sender,
            }
        )

    async def handle_read(self, data):
        """Отметка сообщений как прочитанных"""
        message_ids = data.get('message_ids', [])
        reader = data.get('reader', 'client')
        await self.mark_messages_read(message_ids)

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'messages_read',
                'message_ids': message_ids,
                'reader': reader,
            }
        )

    async def handle_file_notification(self, data):
        """Уведомление о загруженном файле"""
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': data.get('message', {}),
            }
        )

    # Обработчики событий группы
    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'message',
            'message': event['message'],
        }))

    async def typing_indicator(self, event):
        await self.send(text_data=json.dumps({
            'type': 'typing',
            'sender': event['sender'],
        }))

    async def messages_read(self, event):
        await self.send(text_data=json.dumps({
            'type': 'messages_read',
            'message_ids': event['message_ids'],
            'reader': event['reader'],
        }))

    async def specialist_status(self, event):
        await self.send(text_data=json.dumps({
            'type': 'specialist_status',
            'is_online': event['is_online'],
        }))

    async def session_expired_notification(self, event):
        await self.send(text_data=json.dumps({
            'type': 'session_expired',
            'message': event.get('message', 'Сессия завершена.'),
        }))

    async def session_warning(self, event):
        await self.send(text_data=json.dumps({
            'type': 'session_warning',
            'remaining_seconds': event.get('remaining_seconds', 300),
            'message': event.get('message', 'До конца сессии осталось 5 минут!'),
        }))

    # Утилиты БД
    @database_sync_to_async
    def get_session_info(self):
        try:
            session = ChatSession.objects.select_related('client', 'specialist__telegram_user').get(
                id=self.session_id, is_active=True
            )
            if session.is_expired:
                session.end_session()
                return None
            
            # Specialist name preference: Custom Name > Telegram First Name
            spec_name = session.specialist.name if session.specialist.name else session.specialist.telegram_user.first_name
            
            return {
                'id': session.id,
                'client_name': session.client.name,
                'specialist_name': spec_name,
                'specialist_photo': None, # Fetching from TG file_id is complex for simple img src
                'remaining_seconds': session.remaining_seconds,
                'expires_at': session.expires_at.isoformat(),
            }
        except ChatSession.DoesNotExist:
            return None

    @database_sync_to_async
    def get_session_telegram_data(self):
        try:
            session = ChatSession.objects.select_related('client', 'specialist__telegram_user').get(
                id=self.session_id, is_active=True
            )
            return {
                'telegram_id': session.specialist.telegram_user.telegram_id,
                'client_name': session.client.name
            }
        except Exception:
            return None

    @database_sync_to_async
    def check_session_valid(self):
        try:
            session = ChatSession.objects.get(id=self.session_id, is_active=True)
            if session.is_expired:
                session.end_session()
                return False
            return True
        except ChatSession.DoesNotExist:
            return False

    @database_sync_to_async
    def save_message(self, content, sender_type, message_type='text'):
        session = ChatSession.objects.get(id=self.session_id)
        msg = ChatMessage.objects.create(
            session=session,
            sender_type=sender_type,
            message_type=message_type,
            content=content,
        )
        return {
            'id': msg.id,
            'time': msg.created_at.strftime('%H:%M'),
        }

    @database_sync_to_async
    def mark_messages_read(self, message_ids):
        ChatMessage.objects.filter(id__in=message_ids).update(is_read=True)


class NotificationConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer для уведомлений специалисту"""

    async def connect(self):
        self.specialist_id = self.scope['url_route']['kwargs']['specialist_id']
        self.notification_group = f'specialist_{self.specialist_id}'

        await self.channel_layer.group_add(
            self.notification_group,
            self.channel_name
        )
        await self.accept()

        # Обновить статус онлайн
        await self.set_online(True)

    async def disconnect(self, close_code):
        await self.set_online(False)
        await self.channel_layer.group_discard(
            self.notification_group,
            self.channel_name
        )

    async def receive(self, text_data):
        pass  # Специалист только получает уведомления

    async def new_session_notification(self, event):
        await self.send(text_data=json.dumps({
            'type': 'new_session',
            'session': event['session'],
        }))

    async def session_ended_notification(self, event):
        await self.send(text_data=json.dumps({
            'type': 'session_ended',
            'session_id': event['session_id'],
        }))

    @database_sync_to_async
    def set_online(self, status):
        # Web mutaxassislar o'chirildi, endi bu funksiya kerak emas
        pass
