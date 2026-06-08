from django.utils import timezone

from asgiref.sync import sync_to_async
from django.forms import model_to_dict
from loguru import logger
import random
from tgbot2.models import Specialization, Specialist, Client


logger.add("debug.log",
           format="{time} {level} {message} | {name}:{function}:{line}",
           level="DEBUG")

@sync_to_async
def get_specializations():
    """Get specializations from database and return as list of dicts with model_to_dict."""
    specializations_query_set = Specialization.objects.all()
    print(f"{specializations_query_set=}\n")
    specializations_list = [model_to_dict(specialization, fields=['id', 'name']) for specialization in specializations_query_set]
    print(f"{specializations_list=}\n")
    return specializations_list


@sync_to_async
def get_specialist_dict(specialization_id: int):
    """Get specialists by specialization id and return as list of dicts including TelegramUser info."""
    specialists = Specialist.objects.filter(specialization_id=specialization_id).select_related('telegram_user').all()
    print(f"{specialists=}\n")
    specialist_dicts = []
    for specialist in specialists:
        # Используем model_to_dict для получения данных специалиста
        specialist_dict = model_to_dict(specialist,
                                        fields=['id', 'name', 'specialization', 'description', 'price', 'rating', 'photo_id', 'is_active'])

        specialization_dict = model_to_dict(specialist.specialization, fields=['id', 'name'])
        # Добавляем данные пользователя Telegram
        telegram_user_dict = model_to_dict(specialist.telegram_user,
                                           fields=['telegram_id', 'first_name', 'username', 'last_name'])
        specialist_dict['telegram_user'] = telegram_user_dict
        specialist_dict['specialization'] = specialization_dict
        specialist_dicts.append(specialist_dict)

    print(f"specialist_dicts={specialist_dicts}\n")
    return specialist_dicts

@sync_to_async
def get_specialists_dict():
    """Get specialists by specialization id and return as list of dicts including TelegramUser info."""
    specialist = Specialist.objects.order_by('?').first()
    specialist_dict = model_to_dict(specialist,
                                    fields=['id', 'name', 'specialization', 'description', 'price', 'rating',
                                            'photo_id', 'is_active'])

    specialization_dict = model_to_dict(specialist.specialization, fields=['id', 'name'])
    # Добавляем данные пользователя Telegram
    telegram_user_dict = model_to_dict(specialist.telegram_user,
                                       fields=['telegram_id', 'first_name', 'username', 'last_name'])
    specialist_dict['telegram_user'] = telegram_user_dict
    specialist_dict['specialization'] = specialization_dict

    #random_spec = random.choice(specialists)
    #print(random_spec)
    return specialist_dict


@sync_to_async
def create_relation(client_id: int, specialist_id: int):
    try:
        client = Client.objects.filter(id=client_id).first()
        specialist = Specialist.objects.filter(id=specialist_id).first()
        if client is None or specialist is None:
            print(f"Either client with ID {client_id} or specialist with ID {specialist_id} does not exist.")
            return False
            # Проверяем, есть ли у специалиста уже клиент
        if specialist.client is not None:
            print(f"Specialist with ID {specialist_id} already has a client.")
            return False

        # Проверяем, есть ли у клиента уже специалист
        if client.specialist is not None:
            print(f"Client with ID {client_id} already has a specialist.")
            return False
        # Устанавливаем связь
        client.specialist = specialist
        client.save()
        specialist.client = client
        specialist.save()
        print(f"New relation created between {client} and {specialist}\n")
        return True
    except (Client.DoesNotExist, Specialist.DoesNotExist) as e:
        print(f"Error creating relation: {e}")
        return False



@sync_to_async
def end_relation(client_id: int, specialist_id: int):
    try:
        client = Client.objects.get(id=client_id)
        specialist = Specialist.objects.get(id=specialist_id)
        # Очищаем связь
        client.specialist = None
        client.save()
        specialist.client = None
        specialist.save()
        print(f"Relation between {client} and {specialist} has been ended")
        return True
    except (Client.DoesNotExist, Specialist.DoesNotExist) as e:
        print(f"Error ending relation: {e}")
        return False


@sync_to_async
def find_active_relation(telegram_id: int) -> dict or None:
    try:
        client = Client.objects.select_related('telegram_user', 'specialist', 'specialist__telegram_user').get(telegram_user__telegram_id=telegram_id)
        if client.specialist:
            relation_data = {
                "client": {
                    "name": client.name,
                    "telegram_id": client.telegram_user.telegram_id,
                    "first_name": client.telegram_user.first_name,
                    "last_name": client.telegram_user.last_name,
                    "username": client.telegram_user.username,
                    "phone_number": client.phone_number,
                    "photo_id": client.photo_id,
                },
                "specialist": {
                    "name": client.specialist.name,
                    "telegram_id": client.specialist.telegram_user.telegram_id,
                    "first_name": client.specialist.telegram_user.first_name,
                    "last_name": client.specialist.telegram_user.last_name,
                    "username": client.specialist.telegram_user.username,
                    "specialization": client.specialist.specialization.name if client.specialist.specialization else None,
                    "description": client.specialist.description,
                    "photo_id": client.specialist.photo_id,
                    "price": client.specialist.price,
                    "rating": client.specialist.rating,
                    "is_active": client.specialist.is_active,
                },
            }
            return relation_data, 'client'
    except Client.DoesNotExist:
        pass

    try:
        specialist = Specialist.objects.select_related('telegram_user', 'client', 'client__telegram_user').get(telegram_user__telegram_id=telegram_id)
        if specialist.client:
            relation_data = {
                "specialist": {
                    "name": specialist.name,
                    "telegram_id": specialist.telegram_user.telegram_id,
                    "first_name": specialist.telegram_user.first_name,
                    "last_name": specialist.telegram_user.last_name,
                    "username": specialist.telegram_user.username,
                    "specialization": specialist.specialization.name if specialist.specialization else None,
                    "description": specialist.description,
                    "photo_id": specialist.photo_id,
                    "price": specialist.price,
                    "rating": specialist.rating,
                    "is_active": specialist.is_active,
                },
                "client": {
                    "name": specialist.client.name,
                    "telegram_id": specialist.client.telegram_user.telegram_id,
                    "first_name": specialist.client.telegram_user.first_name,
                    "last_name": specialist.client.telegram_user.last_name,
                    "username": specialist.client.telegram_user.username,
                    "phone_number": specialist.client.phone_number,
                    "photo_id": specialist.client.photo_id,
                },
            }
            return relation_data, 'specialist'
    except Specialist.DoesNotExist:
        print(f"Client not found for telegram_id={telegram_id}")

    return None, None


@sync_to_async
def end_active_relation(telegram_id: int):
    try:
        client = Client.objects.get(telegram_user__telegram_id=telegram_id)
        if client.specialist:
            client.specialist.client = None
            client.specialist.save()
            client.specialist = None
            client.save()
            print(f"Relation ended for client {client}")
            return True
    except Client.DoesNotExist:
        print(f"Client not found for telegram_id={telegram_id}")

    try:
        specialist = Specialist.objects.get(telegram_user__telegram_id=telegram_id)
        if specialist.client:
            specialist.client.specialist = None
            specialist.client.save()
            specialist.client = None
            specialist.save()
            print(f"Relation ended for specialist {specialist}")
            return True
    except Specialist.DoesNotExist:
        print(f"Specialist not found for telegram_id={telegram_id}")

    return False
