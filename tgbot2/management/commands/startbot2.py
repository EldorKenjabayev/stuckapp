import asyncio
import os
import logging

from aiogram import Bot
from aiogram.types import BotCommand
from django.core.management.base import BaseCommand
from asgiref.sync import sync_to_async
from django.core.management.base import BaseCommand
import asyncio
import logging

from tgbot2.dispatcher import bot
from tgbot2.handlers.commands import router_commands
from tgbot2.handlers.utils import router_utils
from tgbot2.models import TelegramUser

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s - %(filename)s:%(lineno)d - %(funcName)s'
)

logger = logging.getLogger(__name__)



class Command(BaseCommand):
    help = 'Запускает Telegram бота'

    async def send_admin_notification(self):
        admins = await sync_to_async(list)(TelegramUser.objects.filter(is_admin=True))
        if admins:
            try:
                for admin in admins:
                    await bot.send_message(admin.telegram_id, "Бот был успешно запущен! 🚀 /start")
            except Exception as e:
                logger.error(f"!!!ERROR: {e}")
                self.stdout.write(self.style.ERROR(f'Ошибка при отправке сообщения администратору: {e}'))

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Start bot...'))
        from aiogram import Dispatcher
        dp = Dispatcher()

        async def set_main_menu(bot: Bot):

            # Создаем список с командами и их описанием для кнопки menu
            main_menu_commands = [
                BotCommand(command='/start',
                           description='Запуск бота'),
                BotCommand(command='/stop',
                           description='Закончить диалог')
            ]
            await bot.set_my_commands(main_menu_commands)
            
        dp.startup.register(set_main_menu)

        dp.include_routers(
            router_commands,
            router_utils
        )
        # Отправка уведомления администратору
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.send_admin_notification())

        # Запуск поллинга
        try:
            logger.info('Start bot polling...')
            loop.run_until_complete(dp.start_polling(bot))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Ошибка при запуске бота: {e}'))
            logger.error(f"!!!ERROR: {e}")


