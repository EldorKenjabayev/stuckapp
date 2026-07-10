"""
Management command для очистки истекших сессий.
Удаляет сообщения и медиа файлы после завершения сессии.
Запускать через cron каждую минуту:
  python manage.py cleanup_sessions
"""
import os
from django.core.management.base import BaseCommand
from django.utils import timezone
from webtgbot.models import ChatSession, ChatMessage


class Command(BaseCommand):
    help = 'Очистка истекших сессий: удаление сообщений и медиа файлов'

    def handle(self, *args, **options):
        now = timezone.now()

        # Найти все активные сессии, которые истекли
        expired_sessions = ChatSession.objects.filter(
            is_active=True,
            expires_at__lte=now
        )

        count = 0
        for session in expired_sessions:
            self.stdout.write(f'Завершаем сессию #{session.id}: {session.client.name} <-> {session.specialist.name}')

            # Удаляем медиа файлы
            messages = ChatMessage.objects.filter(session=session)
            for msg in messages:
                if msg.file and msg.file.name:
                    file_path = msg.file.path
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        self.stdout.write(f'  Удалён файл: {file_path}')

            # Удаляем все сообщения
            deleted_count = messages.delete()[0]
            self.stdout.write(f'  Удалено {deleted_count} сообщений')

            # Завершаем сессию
            session.is_active = False
            session.ended_at = now
            session.save()
            count += 1

        # Eski sessiyalarni o'chirib yubormasdan, cleaned=True belgilaymiz
        # Sessiya yozuvi qoladi — kim qachon ochgani admin panelda ko'rinib turadi
        old_sessions = ChatSession.objects.filter(
            is_active=False,
            cleaned=False,
            ended_at__lte=now - timezone.timedelta(hours=1)
        )
        old_count = old_sessions.update(cleaned=True)

        if count or old_count:
            self.stdout.write(self.style.SUCCESS(
                f'Завершено: {count} сессий, xabarlar tozalandi: {old_count} ta sessiya'
            ))
        else:
            self.stdout.write('Нет истекших сессий')
