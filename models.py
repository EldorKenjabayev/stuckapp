from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import pre_save
from django.dispatch import receiver
import secrets


class TelegramUser(models.Model):
    """Пользователь Telegram"""
    telegram_id = models.IntegerField(verbose_name='ID пользователя', unique=True)
    first_name = models.CharField(verbose_name='Имя пользователя', max_length=255)
    username = models.CharField(verbose_name='Username пользователя', max_length=255, null=True, blank=True)
    last_name = models.CharField(verbose_name='Фамилия пользователя', max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(verbose_name='Дата создания', auto_now_add=True)
    updated_at = models.DateTimeField(verbose_name='Дата обновления', auto_now=True)
    is_admin = models.BooleanField(verbose_name='Администратор', default=False)
    phone_number = models.CharField(max_length=20, verbose_name='Номер телефона', blank=True, null=True)
    avatar_url = models.URLField(verbose_name='URL аватара', blank=True, null=True)
    token = models.CharField(max_length=255, verbose_name='Токен', blank=True, null=True)

    def __str__(self):
        return f'{self.first_name} {self.last_name}'

    def save(self, *args, **kwargs):
        print(f'Saving {self}')
        if not self.token:
            self.token = secrets.token_hex(16)
            print(f'Generated token for {self}: {self.token}')
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'Пользователь Telegram'
        verbose_name_plural = 'Пользователи Telegram'
        ordering = ('-created_at',)


class TelegramBotToken(models.Model):
    """Токен бота для Telegram"""
    token = models.CharField(max_length=255, verbose_name='Токен бота')

    def __str__(self):
        return self.token

    class Meta:
        verbose_name = 'Токен бота'
        verbose_name_plural = 'Токены ботов'


@receiver(pre_save, sender=TelegramBotToken)
def ensure_single_bot_token(sender, instance, **kwargs):
    # Проверяем, есть ли уже записи в модели
    existing_tokens = TelegramBotToken.objects.all()
    if existing_tokens.count() > 0:
        # Если есть больше одной записи, удаляем все записи, кроме текущей
        existing_tokens.exclude(pk=instance.pk).delete()


class Specialization(models.Model):
    """Специализация"""
    name = models.CharField(max_length=255, verbose_name='Город')

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Город'
        verbose_name_plural = 'Города'
        ordering = ('name',)


class Specialist(models.Model):
    """Специалист"""
    telegram_user = models.OneToOneField(TelegramUser, verbose_name='Пользователь Telegram', on_delete=models.CASCADE)
    name = models.CharField(max_length=255, verbose_name='Имя', blank=True, null=True)
    specialization = models.ForeignKey(Specialization, verbose_name='Город', on_delete=models.CASCADE)
    description = models.TextField(verbose_name='Описание', blank=True, null=True)
    photo_id = models.CharField(max_length=255, verbose_name='ID фото', blank=True, null=True)
    price = models.DecimalField(verbose_name='Цена', max_digits=10, decimal_places=2, blank=True, null=True, default=0.00)
    rating = models.DecimalField(verbose_name='Рейтинг', max_digits=3, decimal_places=2, blank=True, null=True)
    is_active = models.BooleanField(verbose_name='Активен', default=True)
    created_at = models.DateTimeField(verbose_name='Дата создания', auto_now_add=True)
    updated_at = models.DateTimeField(verbose_name='Дата обновления', auto_now=True)
    client = models.OneToOneField("Client", verbose_name='Клиент', on_delete=models.SET_NULL, null=True, blank=True, related_name='client_specialist')

    def __str__(self):
        return f'{self.telegram_user.first_name} {self.telegram_user.last_name}'

    def save(self, *args, **kwargs):
        # if Client.objects.filter(telegram_user=self.telegram_user).exists():
        #     raise ValidationError("Этот TelegramUser уже является клиентом.")
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'Специалист'
        verbose_name_plural = 'Специалисты'
        ordering = ('-created_at',)


class Client(models.Model):
    """Клиент"""
    telegram_user = models.OneToOneField(TelegramUser, verbose_name='Пользователь Telegram', on_delete=models.CASCADE)
    name = models.CharField(max_length=255, verbose_name='Имя', blank=True, null=True)
    phone_number = models.CharField(max_length=20, verbose_name='Номер телефона', blank=True, null=True)
    photo_id = models.CharField(max_length=255, verbose_name='ID фото', blank=True, null=True)
    created_at = models.DateTimeField(verbose_name='Дата создания', auto_now_add=True)
    updated_at = models.DateTimeField(verbose_name='Дата обновления', auto_now=True)
    specialist = models.OneToOneField(Specialist, verbose_name='Специалист', on_delete=models.SET_NULL, null=True, blank=True, related_name='specialist_client')

    def has_specialist(self):
        return self.specialist is not None

    def save(self, *args, **kwargs):
        if Specialist.objects.filter(telegram_user=self.telegram_user).exists():
            raise ValidationError("Этот TelegramUser уже является специалистом.")
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.telegram_user.first_name} {self.telegram_user.last_name}'

    class Meta:
        verbose_name = 'Клиент'
        verbose_name_plural = 'Клиенты'
        ordering = ('-created_at',)

#
class ClientSpecialistRelation(models.Model):
    """Модель связи между клиентом и специалистом."""
    client = models.ForeignKey(Client, verbose_name='Клиент', related_name='client_relations', on_delete=models.CASCADE)
    specialist = models.ForeignKey(Specialist, verbose_name='Специалист', related_name='specialist_relations', on_delete=models.CASCADE)
    active = models.BooleanField(verbose_name='Активная связь', default=True)
    start_time = models.DateTimeField(verbose_name='Время начала', auto_now_add=True)
    end_time = models.DateTimeField(verbose_name='Время окончания', null=True, blank=True)

    def __str__(self):
        return f'{self.client.name} -> {self.specialist.name}'

    class Meta:
        verbose_name = 'Связь Клиент-Специалист'
        verbose_name_plural = 'Связи Клиент-Специалист'
        ordering = ('-start_time',)
