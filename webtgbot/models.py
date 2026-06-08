import secrets
import os
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta





class WebUser(models.Model):
    """Пользователь веб-чата — регистрируется только по имени"""
    name = models.CharField(max_length=255, verbose_name='Имя')
    session_token = models.CharField(max_length=64, verbose_name='Токен сессии',
                                     unique=True, blank=True)
    created_at = models.DateTimeField(verbose_name='Дата создания', auto_now_add=True)
    is_active = models.BooleanField(verbose_name='Активен', default=True)

    def save(self, *args, **kwargs):
        if not self.session_token:
            self.session_token = secrets.token_hex(32)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Пользователь (Web)'
        verbose_name_plural = 'Пользователи (Web)'
        ordering = ('-created_at',)


SESSION_DURATION_MINUTES = 30


class ChatSession(models.Model):
    """Сессия чата — 30 минут бесплатно"""
    client = models.ForeignKey(WebUser, verbose_name='Клиент', on_delete=models.CASCADE,
                               related_name='sessions')
    specialist = models.ForeignKey('tgbot.Specialist', verbose_name='Специалист', on_delete=models.CASCADE,
                                   related_name='web_sessions')
    started_at = models.DateTimeField(verbose_name='Начало сессии', auto_now_add=True)
    expires_at = models.DateTimeField(verbose_name='Истекает в', blank=True, null=True)
    is_active = models.BooleanField(verbose_name='Активна', default=True)
    ended_at = models.DateTimeField(verbose_name='Завершена в', null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(minutes=SESSION_DURATION_MINUTES)
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    @property
    def remaining_seconds(self):
        delta = self.expires_at - timezone.now()
        return max(0, int(delta.total_seconds()))

    def end_session(self):
        """Завершить сессию и очистить все данные"""
        self.is_active = False
        self.ended_at = timezone.now()
        self.save()
        # Удалить все медиа-файлы
        for msg in self.messages.all():
            if msg.file and msg.file.name:
                try:
                    if os.path.isfile(msg.file.path):
                        os.remove(msg.file.path)
                except Exception:
                    pass
            msg.delete()

    def __str__(self):
        status = '🟢 Активна' if self.is_active else '🔴 Завершена'
        return f'{self.client.name} ↔ {self.specialist.name} [{status}]'

    class Meta:
        verbose_name = 'Сессия чата (Web)'
        verbose_name_plural = 'Сессии чатов (Web)'
        ordering = ('-started_at',)


class ChatMessage(models.Model):
    """Сообщение в чате — удаляется после завершения сессии"""
    MESSAGE_TYPES = [
        ('text', 'Текст'),
        ('image', 'Изображение'),
        ('audio', 'Аудио'),
        ('voice', 'Голосовое'),
        ('sticker', 'Стикер'),
        ('file', 'Файл'),
    ]
    SENDER_TYPES = [
        ('client', 'Клиент'),
        ('specialist', 'Специалист'),
    ]

    session = models.ForeignKey(ChatSession, verbose_name='Сессия', on_delete=models.CASCADE,
                                related_name='messages')
    sender_type = models.CharField(max_length=20, verbose_name='Тип отправителя',
                                   choices=SENDER_TYPES)
    message_type = models.CharField(max_length=20, verbose_name='Тип сообщения',
                                    choices=MESSAGE_TYPES, default='text')
    content = models.TextField(verbose_name='Содержимое', blank=True, default='')
    file = models.FileField(verbose_name='Файл', upload_to='chat_media/%Y/%m/%d/',
                           blank=True, null=True)
    is_read = models.BooleanField(verbose_name='Прочитано', default=False)
    created_at = models.DateTimeField(verbose_name='Дата создания', auto_now_add=True)

    def __str__(self):
        return f'[{self.sender_type}] {self.message_type}: {self.content[:50]}'

    class Meta:
        verbose_name = 'Сообщение (Web)'
        verbose_name_plural = 'Сообщения (Web)'
        ordering = ('created_at',)


class SupportGroup(models.Model):
    """Группы поддержки — ссылки на Telegram группы"""
    name = models.CharField(max_length=255, verbose_name='Название группы')
    url = models.URLField(verbose_name='Ссылка на группу')
    order = models.IntegerField(verbose_name='Порядок', default=0, blank=True)

    def save(self, *args, **kwargs):
        if not self.id and (self.order == 0 or self.order is None):
            last_order = SupportGroup.objects.aggregate(models.Max('order'))['order__max']
            self.order = (last_order or 0) + 1
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Группа поддержки (Web)'
        verbose_name_plural = 'Группы поддержки (Web)'
        ordering = ('order',)


class UserRequest(models.Model):
    """Запрос от пользователя"""
    name = models.CharField(max_length=255, verbose_name='Имя пользователя')
    contact = models.CharField(max_length=255, verbose_name='Контактные данные', blank=True, null=True)
    problem = models.TextField(verbose_name='Описание проблемы')
    created_at = models.DateTimeField(verbose_name='Дата создания', auto_now_add=True)
    is_processed = models.BooleanField(verbose_name='Обработано', default=False)

    def __str__(self):
        return f'{self.name} — {self.problem[:50]}'

    class Meta:
        verbose_name = 'Запрос пользователя (Web)'
        verbose_name_plural = 'Запросы пользователей (Web)'
        ordering = ('-created_at',)
