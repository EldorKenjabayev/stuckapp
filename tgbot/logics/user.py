from asgiref.sync import sync_to_async
from django.core.exceptions import ObjectDoesNotExist
from django.forms import model_to_dict
from django.utils import timezone
from loguru import logger

from tgbot.models import TelegramUser, Client, Specialist

import time
from django.db import transaction

logger.add("debug.log",
           format="{time} {level} {message} | {name}:{function}:{line}",
           level="DEBUG")

def timing_decorator(func):
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        execution_time = end_time - start_time
        print(f"Execution time for {func.__name__}: {execution_time:.4f} seconds")
        return result

    return wrapper


@timing_decorator
@sync_to_async
def get_client_by_telegram_id(telegram_id: int) -> dict:
    """Получение клиента по ID Telegram."""
    try:
        client = Client.objects.get(telegram_user__telegram_id=telegram_id)
        return model_to_dict(client)
    except Client.DoesNotExist:
        logger.error(f"Client with telegram_id={telegram_id} does not exist.")
        return {}


@sync_to_async
def create_telegram_user(telegram_id: int, first_name: str, last_name: str, username: str) -> tuple:
    """Создание пользователя Telegram
    :param telegram_id: ID пользователя в Telegram
    :param first_name: Имя пользователя
    :param last_name: Фамилия пользователя
    :param username: Username пользователя
    :return: TelegramUser, created"""
    with transaction.atomic():
        user, created = TelegramUser.objects.update_or_create(
            telegram_id=telegram_id,  # Убедитесь, что здесь используется правильное имя поля
            defaults={'first_name': first_name, 'last_name': last_name, 'username': username}
        )
    if created:
        Client.objects.create(telegram_user=user)
    return user, created


@sync_to_async
def get_user_by_id(telegram_id: int) -> TelegramUser:
    """Получение пользователя по ID
    :param telegram_id: ID пользователя в Telegram
    :return: TelegramUser"""
    return TelegramUser.objects.get(telegram_id=telegram_id)


@sync_to_async
def get_client_by_id(telegram_user_id: int) -> Client or None:
    """Получение клиента по ID пользователя в Telegram
    :param telegram_user_id: ID пользователя в Telegram
    :return: Client"""
    try:
        logger.debug(f"get_client_by_id: {telegram_user_id=}")
        telegram_user, _ = TelegramUser.objects.get_or_create(telegram_id=telegram_user_id)
        client, created = Client.objects.get_or_create(telegram_user=telegram_user)
        logger.debug(f"get_client_by_id: {client=}, {created=}")
        return model_to_dict(client)
    except Client.DoesNotExist:
        return None


@sync_to_async
def get_specialist_by_id(specialist_id: int) -> Specialist or None:
    """Получение специалиста по ID
    :param specialist_id: ID специалиста
    :return: Specialist"""
    try:
        specialist = Specialist.objects.get(pk=specialist_id)
        return model_to_dict(specialist)
    except Specialist.DoesNotExist:
        return None


@sync_to_async
def get_specialist_by_telegram_id(telegram_id: int):
    """Получение специалиста по ID пользователя в Telegram
    :param telegram_id: ID пользователя в Telegram
    :return: Specialist"""
    try:
        specialist = Specialist.objects.get(telegram_user__telegram_id=telegram_id)
        print(f"get_specialist_by_telegram_id: {specialist}\n")
        return model_to_dict(specialist)
    except Specialist.DoesNotExist:
        return None


@sync_to_async
def get_telegram_id_by_specialist_id(client_id: int) -> int or None:
    """Получение ID пользователя в Telegram по ID клиента"""
    try:
        if client_id is None:
            return None
        client = Client.objects.get(id=client_id)
        return client.telegram_user.telegram_id
    except Client.DoesNotExist:
        return None


@sync_to_async
def change_photo_id(telegram_id: int, photo_id: str) -> str:
    """Изменение photo_id для пользователя
    :param telegram_id: ID пользователя в Telegram
    :param photo_id: ID фото
    :return: None"""
    try:
        specialist = Specialist.objects.get(telegram_user__telegram_id=telegram_id)
        specialist.photo_id = photo_id
        specialist.save()
        return "Фото ID успешно сохранен для специалиста"
    except ObjectDoesNotExist:
        try:
            client = Client.objects.get(telegram_user__telegram_id=telegram_id)
            client.photo_id = photo_id
            client.save()
            return "Фото ID успешно сохранен для клиента"
        except ObjectDoesNotExist:
            return "Пользователь не найден"


async def get_or_create_telegram_user(telegram_id, first_name, username):
    telegram_user, created = await sync_to_async(TelegramUser.objects.get_or_create, thread_sensitive=True)(
        telegram_id=telegram_id,
        defaults={'first_name': first_name, 'username': username}
    )
    print(f"get_or_create_telegram_user: {telegram_user}, {created}")
    return model_to_dict(telegram_user)


@sync_to_async
def get_client_by_telegram_id(telegram_id) -> dict or None:
    """"""
    try:
        telegram_user = TelegramUser.objects.get(telegram_id=telegram_id)
        client = Client.objects.get(telegram_user=telegram_user)
        print(f"get_client_by_telegram_id: {client}")
        return model_to_dict(client)
    except Client.DoesNotExist:
        return None


@sync_to_async
def get_telegram_user(telegram_id) -> TelegramUser:
    return TelegramUser.objects.get(telegram_id=telegram_id)

@sync_to_async
def get_or_create_client_sync(telegram_user):
    return Client.objects.get_or_create(telegram_user=telegram_user)


@sync_to_async
def get_telegram_id_by_client_id(client_id: int):
    try:
        client = Client.objects.get(id=client_id)
        logger.debug(f"get_telegram_id_by_client_id: {client.__dict__}")
        return client.telegram_user.telegram_id
    except Client.DoesNotExist:
        return None


@sync_to_async
def get_telegram_id_by_spec(telegram_id: int):
    telegram_user_id = TelegramUser.objects.get(id=telegram_id).telegram_id
    return telegram_user_id

async def get_specialist_data(specialist_id):
    try:
        specialist = await sync_to_async(
            Specialist.objects.select_related('telegram_user').get,
            thread_sensitive=True
        )(pk=specialist_id)
        specialist_data = {
            "id": specialist.pk,
            "telegram_user": {
                "telegram_id": specialist.telegram_user.telegram_id,
                "first_name": specialist.telegram_user.first_name,
                "username": specialist.telegram_user.username,
            },
            "name": specialist.name,
            "description": specialist.description,
            "photo_id": specialist.photo_id,
            "price": float(specialist.price) if specialist.price else None,
            "rating": float(specialist.rating) if specialist.rating else None,
        }
        return specialist_data
    except Specialist.DoesNotExist:
        return None


async def create_relation(client_id, specialist_id):
    # Получаем экземпляры клиента и специалиста по их ID
    client = await sync_to_async(Client.objects.get, thread_sensitive=True)(id=client_id)
    specialist = await sync_to_async(Specialist.objects.get, thread_sensitive=True)(id=specialist_id)

    # Проверяем, есть ли уже активная связь между данным клиентом и специалистом
    if client.specialist is None and specialist.client is None:
        # Устанавливаем связь между клиентом и специалистом
        client.specialist = specialist
        specialist.client = client

        # Сохраняем обновленные экземпляры клиента и специалиста
        await sync_to_async(client.save, thread_sensitive=True)()
        await sync_to_async(specialist.save, thread_sensitive=True)()

        return True
    return False
