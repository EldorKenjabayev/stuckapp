"""
Notification helper for sending Telegram notifications to specialists.

This module handles sending notifications when sessions are created:
- Web chat sessions: notify with link to web chat
- Telegram bot sessions: notify with info about client
"""
import logging
from django.conf import settings
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from aiogram.enums import ParseMode

from tgbot.dispatcher import bot


logger = logging.getLogger(__name__)


# ============================================
# CONFIGURATION
# ============================================

# Web sayt domeni - settings.py dan o'qiladi
WEB_DOMAIN = getattr(settings, 'WEB_DOMAIN', 'https://your-domain.com')


def set_web_domain(domain: str):
    """Set web domain for notifications (called from settings or config)"""
    global WEB_DOMAIN
    WEB_DOMAIN = domain
    logger.info(f"Web domain set to: {WEB_DOMAIN}")


# ============================================
# NOTIFICATION FUNCTIONS
# ============================================

async def notify_web_session(specialist_telegram_id: int, client_name: str, session_id: int) -> bool:
    """
    Send notification to specialist when a web chat session is opened.

    Args:
        specialist_telegram_id: Telegram ID of the specialist
        client_name: Name of the client
        session_id: ID of the chat session

    Returns:
        bool: True if notification sent successfully, False otherwise
    """
    if not specialist_telegram_id:
        logger.warning("No telegram_id provided for specialist notification")
        return False

    # Localhost bo'lsa ham notification yuborishga ruxsat etiladi (test uchun)
    # if 'localhost' in WEB_DOMAIN or '127.0.0.1' in WEB_DOMAIN:
    #     logger.info(f"Dev mode: Skipping web session notification (localhost: {WEB_DOMAIN})")
    #     return True

    try:
        # Send notification message
        await bot.send_message(
            specialist_telegram_id,
            (
                f"🔔 <b>Новая веб-сессия!</b>\n\n"
                f"👤 Клиент: {client_name}\n"
                f"💻 Платформа: Веб-чат\n\n"
                f"💬 Вы можете писать ответы прямо здесь 👇"
            ),
            parse_mode=ParseMode.HTML
        )

        logger.info(f"Web session notification sent to specialist {specialist_telegram_id} for client {client_name}")
        return True

    except Exception as e:
        logger.error(f"Failed to send web session notification: {e}", exc_info=True)
        return False


async def notify_telegram_session(specialist_telegram_id: int, client_name: str) -> bool:
    """
    Send notification to specialist when a Telegram bot session is started.

    Args:
        specialist_telegram_id: Telegram ID of the specialist
        client_name: Name of the client

    Returns:
        bool: True if notification sent successfully, False otherwise
    """
    if not specialist_telegram_id:
        logger.warning("No telegram_id provided for specialist notification")
        return False

    try:
        await bot.send_message(
            specialist_telegram_id,
            (
                f"🔔 <b>Начато общение в Telegram!</b>\n\n"
                f"👤 Клиент: {client_name}\n"
                f"📱 Платформа: Telegram бот\n\n"
                f"💬 Сообщения будут пересылаться в бот"
            ),
            parse_mode=ParseMode.HTML
        )

        logger.info(f"Telegram session notification sent to specialist {specialist_telegram_id} for client {client_name}")
        return True

    except Exception as e:
        logger.error(f"Failed to send telegram session notification: {e}", exc_info=True)
        return False


async def notify_session_ended(specialist_telegram_id: int, client_name: str) -> bool:
    """
    Send notification when a session is ended.

    Args:
        specialist_telegram_id: Telegram ID of the specialist
        client_name: Name of the client

    Returns:
        bool: True if notification sent successfully, False otherwise
    """
    if not specialist_telegram_id:
        return False

    try:
        await bot.send_message(
            specialist_telegram_id,
            (
                f"✅ <b>Сессия завершена</b>\n\n"
                f"👤 Клиент: {client_name}\n"
                f"📅 Время: Текущее\n\n"
                f"💡 Спасибо за общение!"
            ),
            parse_mode=ParseMode.HTML
        )

        logger.info(f"Session ended notification sent to specialist {specialist_telegram_id}")
        return True

    except Exception as e:
        logger.error(f"Failed to send session ended notification: {e}", exc_info=True)
        return False
