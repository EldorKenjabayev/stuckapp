import os
from django.conf import settings
from aiogram.types import FSInputFile
from channels.db import database_sync_to_async
from .models import ChatSession, ChatMessage
from tgbot.dispatcher import bot

@database_sync_to_async
def get_message_for_forwarding(message_id):
    try:
        return ChatMessage.objects.select_related('session', 'session__client', 'session__specialist__telegram_user').get(id=message_id)
    except ChatMessage.DoesNotExist:
        return None

async def forward_web_message_to_telegram(message_id):
    """Webdan kelgan xabarni Telegram mutaxassisga yuborish (Sinxronlanuvchi funksiya)"""
    msg = await get_message_for_forwarding(message_id)
    if not msg or msg.sender_type != 'client':
        return

    session = msg.session
    if not session or not session.specialist or not session.specialist.telegram_user:
        return

    tg_id = session.specialist.telegram_user.telegram_id
    client_name = session.client.name
    
    try:
        if msg.message_type == 'text':
            text = msg.content
            await bot.send_message(tg_id, text)
        
        elif msg.message_type in ['image', 'voice', 'audio', 'file', 'video', 'video_note']:
            if not msg.file or not os.path.exists(msg.file.path):
                return
            
            input_file = FSInputFile(msg.file.path)
            caption = ""
            
            if msg.message_type == 'image':
                await bot.send_photo(tg_id, input_file, caption=caption)
            elif msg.message_type == 'voice':
                await bot.send_voice(tg_id, input_file, caption=caption)
            elif msg.message_type == 'audio':
                await bot.send_audio(tg_id, input_file, caption=caption)
            else:
                await bot.send_document(tg_id, input_file, caption=caption)
    except Exception as e:
        print(f"Error forwarding web message to TG: {e}")
