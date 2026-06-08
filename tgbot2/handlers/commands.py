import asyncio
from aiogram.fsm.context import FSMContext
from tgbot2.handlers.states import Query
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram import Router, F
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.types import Message, InlineKeyboardMarkup, WebAppInfo, InlineKeyboardButton
from asgiref.sync import sync_to_async
from tgbot2.logics.order import get_specialists_dict
from tgbot2.dispatcher import bot
from tgbot2.logics.order import get_specializations, end_active_relation
from tgbot2.logics.user import create_telegram_user, get_user_by_id, get_client_by_telegram_id, get_specialist_by_id, \
    get_specialist_by_telegram_id, get_client_by_id, get_telegram_id_by_client_id, get_telegram_id_by_specialist_id, \
    get_telegram_id_by_spec
from tgbot2.models import TelegramUser, Specialization, Specialist
from loguru import logger

logger.add("debug.log",
           format="{time} {level} {message} | {name}:{function}:{line}",
           level="DEBUG")

router_commands = Router()


@router_commands.message(CommandStart())
async def send_welcome(message: Message):
    """Отправляет приветственное сообщение пользователю и создает пользователя в базе данных, если его нет."""
    f_user = message.from_user
    username = f_user.username or ""
    last_name = f_user.last_name or ""

    user, created = await create_telegram_user(f_user.id, f_user.first_name, last_name, username)
    print(user)

    client = await get_client_by_telegram_id(f_user.id)
    specialist = await get_specialist_by_telegram_id(f_user.id)  # Предполагается наличие этой функции
    print(f"{client=}, {specialist=}")
    kb = InlineKeyboardBuilder()

    # Если пользователь - клиент
    # if client and not specialist:
    msg = f"Привет, {f_user.first_name}! Я бот-помощник. Чем могу помочь?"
    #     if client.get("specialist"):
    #         specialist_info = await get_specialist_by_id(client["specialist"])
    #         if specialist_info:
    #             msg += f"\n\n🥸 Ваш текущий специалист: {specialist_info['name']}\n чтобы завершить сессию общения нажмите /stop"
    #             kb.row(InlineKeyboardButton(text=specialist_info["name"], callback_data=f"specialist_{specialist_info['id']}"))
    #     else:
    kb.row(InlineKeyboardButton(text="👉 Список городов", callback_data=f"list"))
    kb.row(InlineKeyboardButton(text="🤳 Быстрый подбор брокера", callback_data=f"tinder"))
    kb.row(InlineKeyboardButton(text="🙋‍♂️ Группы по городам", callback_data=f"supgroups"))
    kb.row(InlineKeyboardButton(text="❓Оставить запрос на подбор", callback_data=f"leave_query"))

    # Если пользователь - специалист
    # elif specialist:
    #     msg = f"Привет, {f_user.first_name}! Вы вошли как специалист. Можете скинуть сюда свою фотографию и я вам ее сменю"
    # 
    # else:
    #     msg = f"Привет, {f_user.first_name}! Я не смог определить вашу роль. Пожалуйста, зарегистрируйтесь."
    #     # Можете добавить кнопку для регистрации

    await message.answer(msg, reply_markup=kb.as_markup())

@router_commands.message(Command("request"))
async def request(message: Message, command: CommandObject, state: FSMContext):
    if message.chat.type == "private":
        await state.set_state(Query.name)
        await message.answer("Напишите ваше имя:")

@router_commands.message(Command("groups"))
async def groups(message: Message, command: CommandObject):
    if message.chat.type == "private":
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="🍷Алкоголь, наркотики, игромания", url="https://t.me/+0hjTIrkfoRc0OGVi"))
        builder.row(InlineKeyboardButton(text="❤️Любовь, отношения и расстования", url="https://t.me/+Hyh5Y9TIfQ45YzEy"))
        builder.row(
            InlineKeyboardButton(text="⭐Мотивация, поиск себя, начало своего дела", url="https://t.me/+oaUvMaQg40tmNWQy"))
        builder.row(InlineKeyboardButton(text="🍓Секс и всё что с ним связано", url="https://t.me/+7skdrfpJnaY4OGM6"))
        builder.row(InlineKeyboardButton(text="👪Семья, брак и развод", url="https://t.me/+n5e6wC-FS_YwOWY6"))
        builder.row(
            InlineKeyboardButton(text="👻Дети - воспитание, беременность, рождение", url="https://t.me/+UcpQtFnspnNkOGNi"))
        builder.row(InlineKeyboardButton(text="💪Повышение самооценки, саморазвитие", url="https://t.me/+tghbGamn4PVmMzY6"))
        builder.row(
            InlineKeyboardButton(text="😣Депрессия, одиночество, не хочу жить", url="https://t.me/+KMz4ghK8n44xMTRi"))
        builder.row(InlineKeyboardButton(text="😬Приступы страха и тревоги / Панические атаки",
                                         url="https://t.me/+PE6xNzsisixjMmIy"))
        builder.row(InlineKeyboardButton(text="🤗А может просто поговорить?", url="https://t.me/+CdLyUsqrBEA2ZTYy"))
        await message.answer("Список групп по городам", reply_markup=builder.as_markup())

@router_commands.message(Command("tinder"))
async def tinder(message: Message, command: CommandObject):
    if message.chat.type == "private":
        spec = await get_specialists_dict()
        # Формируем кнопку для начала общения
        contact_button = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💬 Чат с брокером",
                                  callback_data=f"contact_{spec['id']}_{message.from_user.id}"),
             InlineKeyboardButton(text="➡️Дальше",
                                  callback_data=f"tinder"),
             ]
        ])

        if spec['photo_id']:
            # Отправляем фото с капчей, описанием и кнопкой, если photo_id не пустой
            await message.answer_photo(
                photo=spec['photo_id'],
                caption=f"Специалист: {spec['telegram_user']['first_name']}\n"
                        f"Описание: {spec['description']}\n"
                        f"Сеанс: {spec['price']} руб.\n"
                        f"Рейтинг: {spec['rating']}\n",
                reply_markup=contact_button
            )
        else:
            # Отправляем текстовое сообщение без фото, если photo_id пустой
            await message.answer(
                text=f"Специалист: {spec['telegram_user']['first_name']}\n"
                     f"Описание: {spec['description']}\n"
                     f"Сеанс: {spec['price']} руб.\n"
                     f"Рейтинг: {spec['rating']}\n",
                reply_markup=contact_button
            )

@router_commands.message(Command("list"))
async def special_list(message: Message, command: CommandObject):
    if message.chat.type == "private":
        """Добавляет специальное предложение."""
        """Отправляет пользователю его токен."""
        list_special = await get_specializations()
        print(list_special)
        builder = InlineKeyboardBuilder()
        for special in list_special:
            builder.row(InlineKeyboardButton(text=special['name'], callback_data=f"special_{special['id']}"))
        await message.answer("Выберите город", reply_markup=builder.as_markup())


@router_commands.message(Command("stop"))
async def stop_session(message: Message):
    if message.chat.type == "private":
        user_id = message.from_user.id
        role = None
        client = await get_client_by_telegram_id(user_id)
        specialist = await get_specialist_by_telegram_id(user_id)
        print(f"{client=}, {specialist=}")
        if client:
            role = "client"
            specialist_dict = await get_specialist_by_id(client["specialist"])
            logger.debug(f"{specialist_dict=}")
            telegram_user = await get_telegram_id_by_spec(specialist_dict["telegram_user"])
            print(f"{telegram_user=}")
            await bot.send_message(telegram_user, "С вами завершили сессию. Спасибо за общение! 🙏🏻")

        elif specialist:
            role = "specialist"
            logger.debug(specialist["telegram_user"])
            telegram_id = await get_telegram_id_by_specialist_id(specialist["client"])
            logger.debug(f"{telegram_id=}")
            await bot.send_message(telegram_id, "С вами завершили сессию. Спасибо за общение! 🙏🏻")
        else:
            await message.reply("Сейчас у вас нет активных сессий общения.")
            return

        success = await end_active_relation(user_id)  # Завершаем активную сессию для пользователя

        if success:

            kb = InlineKeyboardBuilder()
            msg = f"Ваша сессия общения была успешно завершена. Спасибо за общение! 🙏🏻"
            if role == "client":
                kb.row(InlineKeyboardButton(text="Список городов", callback_data=f"list"))

            # Если пользователь - специалист
            elif role == "specialist":
                pass

            else:
                msg = f"Привет, {message.from_user.first_name}! Я не смог определить вашу роль. Пожалуйста, зарегистрируйтесь."
                # Можете добавить кнопку для регистрации

            await message.answer(msg, reply_markup=kb.as_markup())
        else:
            await message.reply("Сейчас у вас нет активных сессий общения.")


@router_commands.message(Command("help"))
async def help_command(message: Message):
    if message.chat.type == "private":
        """Отправляет пользователю список команд."""
        await message.answer("Список команд:\n"
                             "/list - список специализаций\n"
                             "/stop - завершить активную сессию общения\n"
                             "/help - список команд\n"
                             "/start - начать общение с ботом\n"
                             "/id - получить свой id\n"
                             "/tinder - Тиндер специалистов\n"
                             "/groups - Группы поддержки\n"
                             "/request - Оставить запрос")


@router_commands.message(Command('id'))
async def get_id(message: Message):
    if message.chat.type == "private":
        """Отправляет пользователю его токен."""
        await message.answer(f"Ваш id: {message.from_user.id}")


