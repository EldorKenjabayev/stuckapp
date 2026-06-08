import asyncio
import logging

from asgiref.sync import sync_to_async
from django.core.management.base import BaseCommand

from tgbot.dispatcher import bot
from tgbot.handlers.commands import router_commands
from tgbot.handlers.utils import router_utils
from tgbot.models import TelegramUser

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

    async def main(self):
        from aiogram import Dispatcher
        dp = Dispatcher()
        dp.include_routers(
            router_commands,
            router_utils
        )
        await self.send_admin_notification()
        logger.info('Start bot polling...')
        await dp.start_polling(bot)

    def handle(self, *args, **options):
        # Bot token tekshirish
        if not bot:
            self.stdout.write(self.style.ERROR(
                'Telegram bot token is required! Set TELEGRAM_BOT_TOKEN environment variable or add token to database via admin panel.'
            ))
            return

        self.stdout.write(self.style.SUCCESS('Start bot...'))
        
        try:
            asyncio.run(self.main())
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Ошибка при запуске бота: {e}'))
            logger.error(f"!!!ERROR: {e}")

