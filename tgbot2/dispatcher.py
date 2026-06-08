import json
import logging
import traceback

import requests
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from tgbot2.models import TelegramBotToken



bot = Bot(TelegramBotToken.objects.first().token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
