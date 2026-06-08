from django.conf import settings
import httpx
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, \
    CallbackQuery, Message, InputMediaPhoto
from aiogram.filters import StateFilter
from aiogram.utils.keyboard import InlineKeyboardBuilder
from asgiref.sync import sync_to_async
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger
from datetime import datetime, timedelta
from tgbot.handlers.states import Query
from tgbot.dispatcher import bot
from tgbot.logics.user import get_specialist_by_id, change_photo_id, get_or_create_telegram_user, \
    get_specialist_data, create_telegram_user, get_client_by_telegram_id, get_specialist_by_telegram_id
from tgbot.logics.order import get_specialist_dict, get_specialists_dict, create_relation, find_active_relation, get_specializations, is_specialist_busy
from tgbot.logics.notify import notify_telegram_session
from tgbot.models import Client, Specialist, TelegramUser
from webtgbot.models import ChatSession, ChatMessage
from channels.layers import get_channel_layer
from django.utils import timezone
from django.conf import settings
import os
import uuid

logger.add("debug.log",
           format="{time} {level} {message} | {name}:{function}:{line}",
           level="DEBUG")
router_utils = Router()

print("utils.py")

chat_send = -1002019476345
scheduler = AsyncIOScheduler()

@router_utils.callback_query(F.data.startswith("list"))
async def list_special_callback(c: CallbackQuery, state: FSMContext):
    list_special = await get_specializations()
    print(list_special)
    builder = InlineKeyboardBuilder()
    for special in list_special:
        builder.row(InlineKeyboardButton(text=special['name'], callback_data=f"special_{special['id']}"))
    print(builder)
    await c.message.answer("Выберите специализацию", reply_markup=builder.as_markup())


async def download_and_save_tg_file(message: Message, file_id: str, message_type: str):
    """Telegramdan faylni yuklab olib, Django media papkasiga saqlaydi"""
    try:
        file = await message.bot.get_file(file_id)
        # Fayl kengaytmasini aniqlash
        ext = os.path.splitext(file.file_path)[1]
        
        # Yangi unikal nom yaratish
        today = timezone.now().strftime('%Y/%m/%d')
        rel_dir = os.path.join('chat_media', today)
        abs_dir = os.path.join(settings.MEDIA_ROOT, rel_dir)
        os.makedirs(abs_dir, exist_ok=True)
        
        filename = f"{uuid.uuid4()}{ext}"
        filepath = os.path.join(abs_dir, filename)
        
        # Bot orqali yuklab olish
        await message.bot.download_file(file.file_path, filepath)
        
        # Django FileField uchun nisbiy yo'lni qaytarish
        return os.path.join(rel_dir, filename)
    except Exception as e:
        logger.error(f"Faylni yuklab olishda xato: {e}")
        return None

@router_utils.callback_query(F.data.startswith("supgroups"))
async def supgroups_callback(c: CallbackQuery, state: FSMContext):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🍷Алкоголь, наркотики, игромания", url="https://t.me/+0hjTIrkfoRc0OGVi"))
    builder.row(InlineKeyboardButton(text="❤️Любовь, отношения и расстования", url="https://t.me/+Hyh5Y9TIfQ45YzEy"))
    builder.row(InlineKeyboardButton(text="⭐Мотивация, поиск себя, начало своего дела", url="https://t.me/+oaUvMaQg40tmNWQy"))
    builder.row(InlineKeyboardButton(text="🍓Секс и всё что с ним связано", url="https://t.me/+7skdrfpJnaY4OGM6"))
    builder.row(InlineKeyboardButton(text="👪Семья, брак и развод", url="https://t.me/+n5e6wC-FS_YwOWY6"))
    builder.row(InlineKeyboardButton(text="👻Дети - воспитание, беременность, рождение", url="https://t.me/+UcpQtFnspnNkOGNi"))
    builder.row(InlineKeyboardButton(text="💪Повышение самооценки, саморазвитие", url="https://t.me/+tghbGamn4PVmMzY6"))
    builder.row(InlineKeyboardButton(text="😣Депрессия, одиночество, не хочу жить", url="https://t.me/+KMz4ghK8n44xMTRi"))
    builder.row(InlineKeyboardButton(text="😬Приступы страха и тревоги / Панические атаки", url="https://t.me/+PE6xNzsisixjMmIy"))
    builder.row(InlineKeyboardButton(text="🤗А может просто поговорить?", url="https://t.me/+CdLyUsqrBEA2ZTYy"))
    await c.message.answer("Список груп поддержки:", reply_markup=builder.as_markup())

@router_utils.callback_query(F.data.startswith("leave_query"))
async def leave_query_callback(c: CallbackQuery, state: FSMContext):
    await state.set_state(Query.name)
    await c.message.answer("Напишите ваше имя:")

@router_utils.message(F.text, StateFilter(Query.name))
async def leave_query_name_callback(msg: Message, state: FSMContext):
    await state.update_data(name=msg.text)
    await state.set_state(Query.desc)
    await msg.answer("Опишите вашу проблему:")

@router_utils.message(F.text, StateFilter(Query.desc))
async def leave_query_phone_callback(msg: Message, state: FSMContext):
    data = await state.get_data()
    txt = f"Пользователь @{msg.chat.username} оставил заявку!\n\n"
    txt += f" Имя: {data['name']}\n"
    txt += f" Проблема: {msg.text}"
    await state.set_state(None)
    await state.set_data({})
    await msg.bot.send_message(chat_send, txt)
    await msg.answer("Заявка отправлена!\n\nВ ближайшее время с вами свяжется наш специалист")

@router_utils.callback_query(F.data.startswith("tinder"))
async def tinder_callback(c: CallbackQuery, state: FSMContext):
    spec = await get_specialists_dict()
    # Формируем кнопку для начала общения
    contact_button = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬Чат|30 мин бесплатно",
                              callback_data=f"contact_{spec['id']}_{c.from_user.id}"),
         InlineKeyboardButton(text="➡️Дальше",
                              callback_data=f"tinder"),
         ]
    ])

    if spec['photo_id']:
        # Отправляем фото с капчей, описанием и кнопкой, если photo_id не пустой
        await c.message.answer_photo(
            photo=spec['photo_id'],
            caption=f"Специалист: {spec['telegram_user']['first_name']}\n"
                    f"Описание: {spec['description']}\n"
                    f"Сеанс: {spec['price']} руб.\n"
                    f"Рейтинг: {spec['rating']}\n",
            reply_markup=contact_button
        )
    else:
        # Отправляем текстовое сообщение без фото, если photo_id пустой
        await c.message.answer(
            text=f"Специалист: {spec['telegram_user']['first_name']}\n"
                    f"Описание: {spec['description']}\n"
                    f"Сеанс: {spec['price']} руб.\n"
                    f"Рейтинг: {spec['rating']}\n",
            reply_markup=contact_button
        )


@router_utils.callback_query(F.data.startswith("special_"))
async def special_callback(c: CallbackQuery, state: FSMContext):
    """Обработчик для callback_data 'special_{i}'"""
    print("special_callback")
    try:
        specialization_id = c.data.split("_")[1]
        print(f"{specialization_id=}")
        await state.update_data(specialization_id=specialization_id)

        specialist_dict = await get_specialist_dict(int(specialization_id))  # Убедитесь, что передаете int
        await state.update_data(specialist_dict=specialist_dict)

        builder = InlineKeyboardBuilder()

        for specialist in specialist_dict:
            # Используйте имя пользователя Telegram для создания текста кнопки
            specialist_name = specialist['telegram_user']['first_name']
            builder.row(InlineKeyboardButton(text=specialist_name, callback_data=f"specialist_{specialist['id']}"))
        await c.message.answer("Выберите специалиста:", reply_markup=builder.as_markup())

    except Exception as e:
        logger.error(f"!!!ERROR: {e}")


@router_utils.callback_query(F.data.startswith("specialist_"))
async def specialist_callback(c: CallbackQuery, state: FSMContext):
    """Обработчик для callback_data 'specialist_{id}'"""
    try:
        specialist_id = int(c.data.split("_")[1])

        state_data = await state.get_data()
        specialist_dict = state_data.get("specialist_dict")

        # Проверяем, есть ли информация о специалисте в состоянии
        if specialist_dict is None or specialist_id not in [d['id'] for d in specialist_dict]:
            # Получаем информацию о специалисте и сохраняем в состояние
            specialist_info = await get_specialist_data(specialist_id)
            if specialist_info:
                specialist_dict = state_data.get("specialist_dict", [])
                specialist_dict.append(specialist_info)
                await state.set_data({"specialist_dict": specialist_dict})
            else:
                await c.message.answer("Информация о специалисте не найдена.")
                return
        else:
            # Извлекаем информацию о специалисте из состояния
            specialist_info = next((item for item in specialist_dict if item["id"] == specialist_id), None)

        if specialist_info:
            # Формируем кнопку для начала общения
            contact_button = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💬Чат | 30 мин бесплатно",
                                      callback_data=f"contact_{specialist_id}_{c.from_user.id}")]
            ])

            if specialist_info['photo_id']:
                # Отправляем фото с капчей, описанием и кнопкой, если photo_id не пустой
                await c.message.answer_photo(
                    photo=specialist_info['photo_id'],
                    caption=f"Специалист: {specialist_info['telegram_user']['first_name']}\n"
                            f"Описание: {specialist_info['description']}\n"
                            f"Сеанс: {specialist_info['price']} руб.\n"
                            f"Рейтинг: {specialist_info['rating']}\n",
                    reply_markup=contact_button
                )
            else:
                # Отправляем текстовое сообщение без фото, если photo_id пустой
                await c.message.answer(
                    text=f"Специалист: {specialist_info['telegram_user']['first_name']}\n"
                         f"Описание: {specialist_info['description']}\n"
                         f"Сеанс: {specialist_info['price']} руб.\n"
                         f"Рейтинг: {specialist_info['rating']}\n",
                    reply_markup=contact_button
                )
        else:
            await c.message.answer("Информация о специалисте не найдена.")

    except Exception as e:
        logger.error(f"Error while processing specialist callback: {e}")
        await c.message.answer("Произошла ошибка при обработке запроса.")


@router_utils.callback_query(F.data.startswith("contact_"))
async def contact_callback(c: CallbackQuery):
    try:
        _, specialist_id_str, telegram_id_str = c.data.split("_")
        specialist_id = int(specialist_id_str)
        telegram_client_id = int(telegram_id_str)
        client: dict = await get_client_by_telegram_id(telegram_client_id)
        print(f"{client=}\n")
        if not client:
            logger.error(f"Client not found: {telegram_client_id}")
            await c.answer("Пользователь не найден. Пожалуйста, используйте /start для регистрации.", show_alert=True)
            return

        specialist_data = await get_specialist_data(specialist_id)
        if specialist_data:
            print(f"SpecialistData: {specialist_data}")

            # Mutaxassis bandligini tekshiramiz (Web + TG)
            is_busy, busy_msg = await is_specialist_busy(specialist_id)
            if is_busy:
                await c.answer(busy_msg, show_alert=True)
                return

            # Создаем связь между клиентом и специалистом
            relation_created, error_msg = await create_relation(client['id'], specialist_id)
            print(f"RelationCreated: {relation_created}, Error: {error_msg}")

            if relation_created:
                with open("tgbot/handlers/stop.txt", "r", encoding="UTF-8") as f:
                    stop_text = f.read()
                msg = f"Начато общение со специалистом 🧑‍🔬 {specialist_data['name']}\n" + stop_text
                # Если связь создана успешно, уведомляем пользователя
                await c.message.answer(msg)

                # 📬 Отправляем уведомление специалисту
                await notify_telegram_session(
                    specialist_telegram_id=specialist_data['telegram_user']['telegram_id'],
                    client_name=c.from_user.first_name
                )
            else:
                await c.answer(error_msg or "Извините, специалист только что стал занят.", show_alert=True)
        else:
            await c.message.answer("Не удалось начать общение. Проверьте ID специалиста.")

    except Exception as e:
        logger.error(f"Error while processing contact callback: {e}")
        await c.message.answer("Этот специалист уже занят")


@router_utils.callback_query(F.data == "specialist_")
async def specialist_callback(c: CallbackQuery, state: FSMContext):
    """Обработчик для callback_data 'specialist_'"""
    print(f"specialist_callback {c.data}")
    specialist_id: int = int(c.data.split("_")[1])
    specialist: dict = await get_specialist_by_id(specialist_id)
    print(f"{specialist=}")

    if specialist['photo_id']:
        # Отправляем фото с капчей, описанием и кнопкой, если photo_id не пустой
        await c.message.answer_photo(
            photo=specialist['photo_id'],
            caption=f"Специалист: {specialist['telegram_user']['first_name']}\n"
                    f"Описание: {specialist['description']}\n"
                    f"Сеанс: {specialist['price']} руб.\n"
                    f"Рейтинг: {specialist['rating']}\n"

        )

    else:
        # Отправляем текстовое сообщение без фото, если photo_id пустой
        await c.message.answer(
            text=f"Специалист: {specialist['telegram_user']['first_name']}\n"
                 f"Описание: {specialist['description']}\n"
                 f"Сеанс: {specialist['price']} руб.\n"
                 f"Рейтинг: {specialist['rating']}\n"
        )
        await c.message.answer("Вы можете продолжить общение с этим специалистом или остановить сессию командой /stop.")

async def mediagroup_send(photos, target_id, msg : Message, caption = None):
    print("HERE ", photos)
    relation_data, role = await find_active_relation(msg.chat.id)
    if role == 'client':
        target_user_id = relation_data['specialist']['telegram_id']
        print(f"{target_user_id=}")
    elif role == 'specialist':
        target_user_id = relation_data['client']['telegram_id']
        print(f"{target_user_id=}")
    else:
        await msg.reply("Не удалось определить роль пользователя.")
        return
    mg = []
    for k in photos:
        mg.append(InputMediaPhoto(media=k))
    if caption:
        mg[0].caption = caption
    await msg.bot.send_media_group(target_id, mg)

# Unified forwarder for all message types
@router_utils.message(F.text | F.photo | F.video | F.video_note | F.voice | F.audio | F.sticker | F.document)
async def forward_message(message: Message, state: FSMContext):
    if message.chat.type != "private":
        return

    await state.set_state(None)
    user_id = message.from_user.id
    
    # 🔍 DEBUG LOGGING
    print(f"\n--- TG MESSAGE RECEIVED ---")
    print(f"From: {message.from_user.first_name} (@{message.from_user.username}) [ID: {user_id}]")
    print(f"Type: {message.content_type}")
    
    # 🌐 1. HAR DOIM BIRINCHI VEB-SESSIYANI TEKSHIRAMIZ
    web_session = await sync_to_async(
        lambda: ChatSession.objects.select_related('client', 'specialist', 'specialist__telegram_user').filter(
            specialist__telegram_user__telegram_id=user_id, is_active=True
        ).first()
    )()

    if not web_session:
        # Diagnostic check: Is this user even a specialist?
        specialist_obj = await sync_to_async(
            lambda: Specialist.objects.select_related('telegram_user').filter(telegram_user__telegram_id=user_id).first()
        )()
        if specialist_obj:
            print(f"DIAGNOSTIC: Found specialist {specialist_obj.id} for TG ID {user_id}, but NO ACTIVE SESSION found.")
            # Check for any active sessions at all
            active_list = await sync_to_async(
                lambda: list(ChatSession.objects.filter(is_active=True).values_list('specialist__id', 'specialist__telegram_user__telegram_id'))
            )()
            print(f"DIAGNOSTIC: All currently active sessions (specialist_id, tg_id): {active_list}")
        else:
            print(f"DIAGNOSTIC: No specialist found for TG ID {user_id}")

    if web_session:
        print(f"FOUND WEB SESSION: {web_session.id} for client: {web_session.client.name}")
        # Sessiya vaqtini tekshirish
        if web_session.expires_at < timezone.now():
            await sync_to_async(web_session.end_session)()
            await message.reply("Время веб-сессии истекло.")
            return
        
        msg_type = 'text'
        content = message.text or message.caption or ""
        file_rel_path = None
        
        # Media turlarini aniqlash
        if message.photo:
            msg_type = 'image'
            file_rel_path = await download_and_save_tg_file(message, message.photo[-1].file_id, 'image')
        elif message.voice:
            msg_type = 'voice'
            file_rel_path = await download_and_save_tg_file(message, message.voice.file_id, 'voice')
        elif message.video_note:
            msg_type = 'video_note'
            file_rel_path = await download_and_save_tg_file(message, message.video_note.file_id, 'video')
        elif message.sticker:
            msg_type = 'sticker'
            content = message.sticker.emoji or "Sticker"
        elif message.video:
            msg_type = 'video'
            file_rel_path = await download_and_save_tg_file(message, message.video.file_id, 'video')
        elif message.audio:
            msg_type = 'file'
            file_rel_path = await download_and_save_tg_file(message, message.audio.file_id, 'audio')
        elif message.document:
            msg_type = 'file'
            file_rel_path = await download_and_save_tg_file(message, message.document.file_id, 'file')
            content = content or message.document.file_name or "Fayl"

        # 1. Xabarni bazaga saqlash
        def save_msg():
            m = ChatMessage.objects.create(
                session=web_session,
                sender_type='specialist',
                message_type=msg_type,
                content=content
            )
            if file_rel_path:
                m.file = file_rel_path
                m.save()
            return m
        
        msg = await sync_to_async(save_msg)()
        
        # 🚀 2. Veb-saytga real-time yuborish
        # Bot alohida jarayonda ishlaydi, shuning uchun HTTP bridge orqali
        # Django serverga xabar yuboramiz (har doim 127.0.0.1:8000)
        bridge_url = "http://127.0.0.1:8001/chat/api/internal-notify/"
        try:
            async with httpx.AsyncClient(timeout=5.0) as http_client:
                # 1. "Typing" signali
                try:
                    await http_client.post(
                        bridge_url,
                        data={'session_id': web_session.id, 'type': 'typing'}
                    )
                except Exception:
                    pass  # typing xatosi kritik emas
                
                # 2. Asosiy xabarni yuboramiz
                resp = await http_client.post(
                    bridge_url,
                    data={
                        'session_id': web_session.id,
                        'message_id': msg.id,
                        'type': 'message'
                    }
                )
                logger.info(f"Bridge API javob: {resp.status_code} msg_id={msg.id}")
        except Exception as bridge_err:
            logger.error(f"Bridge API xatosi: {bridge_err}")

        return
    else:
        print(f"NO WEB SESSION FOUND FOR ID: {user_id}")

    # 🤖 2. AGAR VEB-SESSIYA BOLMASA, TG-TG MUNOSABATLARNI TEKSHIRAMIZ
    relation_data, role = await find_active_relation(user_id)
    if relation_data:
        target_user_id = relation_data['specialist']['telegram_id'] if role == 'client' else relation_data['client']['telegram_id']
        
        try:
            if message.text:
                await message.bot.send_message(target_user_id, message.text)
            elif message.photo:
                await message.bot.send_photo(target_user_id, message.photo[-1].file_id, caption=message.caption)
            elif message.voice:
                await message.bot.send_voice(target_user_id, message.voice.file_id)
            elif message.video_note:
                await message.bot.send_video_note(target_user_id, message.video_note.file_id)
            elif message.sticker:
                await message.bot.send_sticker(target_user_id, message.sticker.file_id)
            elif message.document:
                await message.bot.send_document(target_user_id, message.document.file_id, caption=message.caption)
            elif message.video:
                await message.bot.send_video(target_user_id, message.video.file_id, caption=message.caption)
            elif message.audio:
                await message.bot.send_audio(target_user_id, message.audio.file_id, caption=message.caption)
        except Exception as e:
            logger.error(f"Error forwarding TG-TG message: {e}")
            await message.reply("Произошла ошибка при отправке сообщения.")
        return

    # ❌ 3. AGAR HECH QANDAY FAOL SESSIYA BOLMASA
    specialist_check = await get_specialist_by_telegram_id(user_id)
    if specialist_check:
        if message.photo:
            # 🖼️ Mutaxassis rasmini yangilash
            photo_id = message.photo[-1].file_id
            from tgbot.logics.user import change_photo_id
            res = await change_photo_id(user_id, photo_id)
            await message.reply(f"✅ {res}")
            return
            
        print(f"USER {user_id} IS A SPECIALIST BUT HAS NO ACTIVE SESSIONS.")
        await message.reply("У вас нет активных сессий общения.")
        return

    # START COMMAND LOGIC (catch-all for new users)
    await handle_start_for_new_user(message)

async def handle_start_for_new_user(message: Message):
    f_user = message.from_user
    user, created = await create_telegram_user(f_user.id, f_user.first_name, f_user.last_name, f_user.username)
    
    msg = f"Привет, {f_user.first_name}! Я бот-помощник. Чем могу помочь?"
    client = await get_client_by_telegram_id(f_user.id)
    kb = InlineKeyboardBuilder()
    
    if client and client.get("specialist"):
        specialist = await get_specialist_by_id(client["specialist"])
        if specialist:
            msg = msg + f"\n\n🥸 Ваш текущий специалист: {specialist['name']}\n"
            kb.row(InlineKeyboardButton(text=specialist["name"], callback_data=f"specialist_{specialist['id']}"))
    
    kb.row(InlineKeyboardButton(text="📄Список специальностей", callback_data=f"list"))
    kb.row(InlineKeyboardButton(text="🤳Тиндер специалистов", callback_data=f"tinder"))
    kb.row(InlineKeyboardButton(text="🙋‍♂️Группы поддержки", callback_data=f"supgroups"))
    kb.row(InlineKeyboardButton(text="❓Оставить запрос ", callback_data=f"leave_query"))
    
    await message.answer(msg, reply_markup=kb.as_markup())

