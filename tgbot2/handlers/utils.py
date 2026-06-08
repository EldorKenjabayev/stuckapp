

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
from tgbot2.handlers.states import Query
from tgbot2.dispatcher import bot
from tgbot2.logics.order import get_specialist_dict, get_specialists_dict, create_relation, find_active_relation, get_specializations
from tgbot2.logics.user import get_specialist_by_id, change_photo_id, get_or_create_telegram_user, \
    get_specialist_data, create_telegram_user, get_client_by_telegram_id, get_specialist_by_telegram_id
from tgbot2.models import Client, Specialist, TelegramUser

logger.add("debug.log",
           format="{time} {level} {message} | {name}:{function}:{line}",
           level="DEBUG")
router_utils = Router()

print("utils.py")

chat_send = -1002589927775
scheduler = AsyncIOScheduler()

@router_utils.callback_query(F.data.startswith("list"))
async def list_special_callback(c: CallbackQuery, state: FSMContext):
    list_special = await get_specializations()
    print(list_special)
    builder = InlineKeyboardBuilder()
    for special in list_special:
        builder.row(InlineKeyboardButton(text=special['name'], callback_data=f"special_{special['id']}"))
    print(builder)
    await c.message.answer("Выберите город", reply_markup=builder.as_markup())

@router_utils.callback_query(F.data.startswith("supgroups"))
async def supgroups_callback(c: CallbackQuery, state: FSMContext):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="SPIRE | Казань", url="https://t.me/+J_2tNDPWOLRiNjQy "))
    builder.row(InlineKeyboardButton(text="SPIRE | Санкт-Петербург", url="https://t.me/+RmXvEycuXeQ0YWMy "))
    builder.row(InlineKeyboardButton(text="SPIRE | Москва", url="https://t.me/+wnVICYeFQXE3NDhi"))
    await c.message.answer("Список групп по городам", reply_markup=builder.as_markup())

@router_utils.callback_query(F.data.startswith("leave_query"))
async def leave_query_callback(c: CallbackQuery, state: FSMContext):
    await state.set_state(Query.name)
    await c.message.answer("Напишите ваше имя:")

@router_utils.message(F.text, StateFilter(Query.name))
async def leave_query_name_callback(msg: Message, state: FSMContext):
    await state.update_data(name=msg.text)
    await state.set_state(Query.desc)
    await msg.answer("Опишите ваш запрос:")

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
        [InlineKeyboardButton(text="💬 Чат с брокером",
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
                [InlineKeyboardButton(text="💬 Чат с брокером",
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

        specialist_data = await get_specialist_data(specialist_id)
        if specialist_data:
            print(f"SpecialistData: {specialist_data}")

            # Создаем связь между клиентом и специалистом
            relation_created = await create_relation(client['id'], specialist_id)
            print(f"RelationCreated: {relation_created}")

            if relation_created:
                with open("tgbot/handlers/stop.txt", "r", encoding="UTF-8") as f:
                    stop_text = f.read()
                msg = f"Начато общение со специалистом 🧑‍🔬 {specialist_data['name']}\n" + stop_text
                # Если связь создана успешно, уведомляем пользователя
                await c.message.answer(msg)
                await bot.send_message(specialist_data['telegram_user']['telegram_id'], f"Начато общение с клиентом {c.from_user.first_name}")
            else:
                await c.message.answer("Уже существует активное общение с этим специалистом.")
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

@router_utils.message(F.photo)
async def photo_handler(message: Message, state: FSMContext):
    if message.chat.type == "private":
        relation_data, role = await find_active_relation(message.chat.id)
        if relation_data:
            if message.media_group_id:
                target_user_id = 0
                if role == 'client':
                    target_user_id = relation_data['specialist']['telegram_id']
                elif role == 'specialist':
                    target_user_id = relation_data['client']['telegram_id']
                if not scheduler.running:
                    scheduler.start()
                nd = datetime.now() + timedelta(seconds=2)
                if scheduler.get_job("mediagroup"):
                    fids, tid, tt, cap =  scheduler.get_job("mediagroup").args
                    fids.append(message.photo[0].file_id)
                    scheduler.modify_job(job_id='mediagroup', args=[fids, tid, message, cap])
                    scheduler.reschedule_job(job_id='mediagroup', trigger='date', run_date=nd)
                else:
                    scheduler.add_job(mediagroup_send, 'date', run_date=nd, args=[[message.photo[0].file_id], target_user_id, message, message.caption], id="mediagroup")
            else:
                if role == 'client':
                    target_user_id = relation_data['specialist']['telegram_id']
                    print(f"{target_user_id=}")
                elif role == 'specialist':
                    target_user_id = relation_data['client']['telegram_id']
                    print(f"{target_user_id=}")
                else:
                    await message.reply("Не удалось определить роль пользователя.")
                    return
                await message.bot.send_photo(target_user_id, message.photo[0].file_id, caption=message.caption)
        else:
            """Обработчик для сообщений с фото"""
            photo_id = message.photo[-1].file_id
            telegram_id = message.from_user.id
            msg: str = await change_photo_id(telegram_id, photo_id)
            await message.reply(msg)

@router_utils.message(F.video_note)
async def forward_video_note_message(message: Message):
    if message.chat.type == "private":
        relation_data, role = await find_active_relation(message.chat.id)
        if relation_data:
            if role == 'client':
                target_user_id = relation_data['specialist']['telegram_id']
                print(f"{target_user_id=}")
            elif role == 'specialist':
                target_user_id = relation_data['client']['telegram_id']
                print(f"{target_user_id=}")
            else:
                await message.reply("Не удалось определить роль пользователя.")
                return
            await message.bot.send_video_note(target_user_id, message.video_note.file_id)

@router_utils.message(F.voice)
async def forward_voice_message(message: Message):
    if message.chat.type == "private":
        relation_data, role = await find_active_relation(message.chat.id)
        if relation_data:
            if role == 'client':
                target_user_id = relation_data['specialist']['telegram_id']
                print(f"{target_user_id=}")
            elif role == 'specialist':
                target_user_id = relation_data['client']['telegram_id']
                print(f"{target_user_id=}")
            else:
                await message.reply("Не удалось определить роль пользователя.")
                return
            await message.bot.send_voice(target_user_id, message.voice.file_id)

@router_utils.message(F.text)
async def forward_message(message: Message, state: FSMContext):
    if message.chat.type == "private":
        await state.set_state(None)
        user_id = message.from_user.id
        specialist = await get_specialist_by_telegram_id(user_id)
        print(f"{specialist=}")
        if specialist:
            if not specialist['client']:
                await message.reply("У вас нет активных сессий общения.")
                return None

        relation_data, role = await find_active_relation(user_id)
        print(f"{relation_data=}")
        print(f"{role=}")
        if relation_data:

            if role == 'client':
                target_user_id = relation_data['specialist']['telegram_id']
                print(f"{target_user_id=}")
            elif role == 'specialist':
                target_user_id = relation_data['client']['telegram_id']
                print(f"{target_user_id=}")
            else:
                await message.reply("Не удалось определить роль пользователя.")
                return
            await message.bot.send_message(target_user_id, f"Сообщение от {message.from_user.first_name}: \n{message.text}")
        else:
            f_user = message.from_user
            user, created = await create_telegram_user(f_user.id, f_user.first_name, f_user.last_name, f_user.username)
            print(user)

            msg = f"Привет, {f_user.first_name}! Я бот-помощник. Чем могу помочь?"

            client = await get_client_by_telegram_id(f_user.id)
            kb = InlineKeyboardBuilder()
            if client and client.get("specialist"):
                specialist = await get_specialist_by_id(client["specialist"])
                if specialist:
                    msg = msg + f"\n\n🥸 Ваш текущий специалист: {specialist['name']}\n"
                    kb.row(InlineKeyboardButton(text=specialist["name"], callback_data=f"specialist_{specialist['id']}"))
                else:
                    kb.row(InlineKeyboardButton(text="📄Список специальностей", callback_data=f"list"))
                    kb.row(InlineKeyboardButton(text="🤳Тиндер специалистов", callback_data=f"tinder"))
                    kb.row(InlineKeyboardButton(text="🙋‍♂️Группы поддержки", callback_data=f"supgroups"))
                    kb.row(InlineKeyboardButton(text="❓Оставить запрос ", callback_data=f"leave_query"))
                await message.answer(msg, reply_markup=kb.as_markup())

            else:
                kb.row(InlineKeyboardButton(text="📄Список специальностей", callback_data=f"list"))
                kb.row(InlineKeyboardButton(text="🤳Тиндер специалистов", callback_data=f"tinder"))
                kb.row(InlineKeyboardButton(text="🙋‍♂️Группы поддержки", callback_data=f"supgroups"))
                kb.row(InlineKeyboardButton(text="❓Оставить запрос ", callback_data=f"leave_query"))
                await message.answer("Сейчас у вас нет активных сессий общения. Используйте команду для начала общения с "
                                     "специалистом.", reply_markup=kb.as_markup())
