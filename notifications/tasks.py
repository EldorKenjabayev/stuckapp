"""
Celery tasks for sending notifications (Telegram, Email, etc.)
This module handles sending notifications asynchronously using Celery.
"""
import logging
from celery import shared_task
from aiogram import InlineKeyboardBuilder, InlineKeyboardButton
from aiogram.enums import ParseMode


logger = logging.getLogger(__name__)

# ─── Configuration ───────────────────────────────
# Web domain - Django settings.dan o'qiladi
from django.conf import settings
WEB_DOMAIN = getattr(settings, 'WEB_DOMAIN', 'https://your-domain.com')


# ─── Telegram Bot Initialization ──────────────────
def get_telegram_bot():
    """Get bot instance for sending notifications"""
    try:
        from aiogram import Bot
        token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
        if not token:
            logger.warning("Telegram bot token not configured")
            return None

        bot = Bot(token, parse_mode=ParseMode.HTML)
        logger.info("Telegram bot initialized for notifications")
        return bot
    except ImportError:
        logger.warning("Aiogram not installed for notifications")
        return None
    except Exception as e:
        logger.error(f"Failed to initialize Telegram bot: {e}")
        return None


# ─── Notification Tasks ────────────────────────────
@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_web_session_notification(self, specialist_telegram_id: int, client_name: str, session_id: int):
    """
    Send notification to specialist when a web chat session is opened.

    Args:
        specialist_telegram_id: Telegram ID of the specialist
        client_name: Name of the client
        session_id: ID of the chat session
    """
    if not specialist_telegram_id:
        logger.info(f"No telegram_id for specialist, skipping notification")
        return

    # Skip localhost in development
    if 'localhost' in WEB_DOMAIN or '127.0.0.1' in WEB_DOMAIN:
        logger.info(f"Dev mode: Skipping notification (localhost: {WEB_DOMAIN})")
        return

    bot = get_telegram_bot()
    if not bot:
        logger.error("Telegram bot not available")
        return

    try:
        # Generate session URL
        session_url = f"{WEB_DOMAIN}/chat/?session_id={session_id}"

        # Create inline keyboard
        kb = InlineKeyboardBuilder()
        kb.row(
            InlineKeyboardButton(text="💬 Чатга кириш", url=session_url),
            InlineKeyboardButton(text="🌐 Веб-сайт", url=WEB_DOMAIN)
        )

        # Send notification
        bot.send_message(
            specialist_telegram_id,
            (
                f"🔔 <b>Новая веб-сессия!</b>\n\n"
                f"👤 Клиент: {client_name}\n"
                f"💻 Платформа: Веб-чат\n"
                f"⏱️ 30 минут бесплатно\n\n"
                f"👇 Нажмите кнопку ниже, чтобы перейти к чату"
            ),
            reply_markup=kb.as_markup(),
            parse_mode=ParseMode.HTML
        )

        logger.info(f"Web session notification sent to specialist {specialist_telegram_id}")

    except Exception as exc:
        logger.error(f"Failed to send web session notification: {exc}", exc_info=True)
        # Retry will be handled by Celery's retry mechanism


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_telegram_session_notification(self, specialist_telegram_id: int, client_name: str):
    """
    Send notification when a Telegram bot session is started.

    Args:
        specialist_telegram_id: Telegram ID of the specialist
        client_name: Name of the client
    """
    bot = get_telegram_bot()
    if not bot:
        return

    try:
        bot.send_message(
            specialist_telegram_id,
            (
                f"🔔 <b>Начато общение в Telegram!</b>\n\n"
                f"👤 Клиент: {client_name}\n"
                f"📱 Платформа: Telegram бот\n"
                f"💬 Сообщения будут пересылаться в бот"
            ),
            parse_mode=ParseMode.HTML
        )

        logger.info(f"Telegram session notification sent to specialist {specialist_telegram_id}")

    except Exception as exc:
        logger.error(f"Failed to send telegram session notification: {exc}", exc_info=True)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_session_ended_notification(self, specialist_telegram_id: int, client_name: str):
    """
    Send notification when a session is ended.

    Args:
        specialist_telegram_id: Telegram ID of the specialist
        client_name: Name of the client
    """
    bot = get_telegram_bot()
    if not bot:
        return

    try:
        bot.send_message(
            specialist_telegram_id,
            (
                f"✅ <b>Сессия завершена</b>\n\n"
                f"👤 Клиент: {client_name}\n"
                f"📅 Время: Текущее\n"
                f"💡 Спасибо за общение!"
            ),
            parse_mode=ParseMode.HTML
        )

        logger.info(f"Session ended notification sent to specialist {specialist_telegram_id}")

    except Exception as exc:
        logger.error(f"Failed to send session ended notification: {exc}", exc_info=True)
