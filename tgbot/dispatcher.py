import json
import logging
import traceback

import requests
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from django.conf import settings

from tgbot.models import TelegramBotToken


import socket
from aiogram.client.session.aiohttp import AiohttpSession
from aiohttp import TCPConnector

def get_bot_token():
    # Token - environment variablega avval qaraydi, DB ga fallback
    token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
    if not token:
        # Environment topilmadi - database dan o'qiymiz
        try:
            from django.db import connection
            # Check if we can safely query the DB
            if 'tgbot_telegrambottoken' in connection.introspection.table_names():
                token_obj = TelegramBotToken.objects.first()
                if token_obj:
                    token = token_obj.token
                    logging.info("Telegram bot token loaded from database")
        except Exception as e:
            logging.error(f"Error loading bot token from database: {e}")
    return token

bot_token = get_bot_token()

if bot_token:
    session = AiohttpSession()
    session._connector_init["family"] = socket.AF_INET
    bot = Bot(
        token=bot_token,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    logging.info("Telegram bot initialized successfully")
else:
    logging.critical("Telegram bot token is required!")
    bot = None




