# STUCK — Telegram & Web Chat Platform

Telegram bot va veb-chat orqali mijozlarni mutaxassislar bilan bog'laydigan Django platforma.

## Ilovalar

| Ilova | Tavsif |
|-------|--------|
| **tgbot** | Aiogram asosidagi Telegram bot. Mijoz va mutaxassislar o'rtasida muloqot. |
| **webtgbot** | Django Channels asosidagi veb-chat. Real-time WebSocket muloqot. |

## Asosiy imkoniyatlar

- Mijozlar mutaxassisni ixtisoslik bo'yicha qidirishi yoki "tinder" orqali tasodifiy tanlashi
- Telegram bot orqali mijoz-mutaxassis xabarlarini avtomatik yo'naltirish
- Veb-chat orqali 30 daqiqalik bepul sessiyalar (WebSocket)
- Fayl almashish (rasm, ovozli xabar, video)
- Admin panel orqali mutaxassislar va guruhlarni boshqarish

## O'rnatish

```bash
# Reponi klonlash
git clone git@github.com:EldorKenjabayev/stuckapp.git
cd stuckapp

# Virtual muhit yaratish
python3 -m venv venv
source venv/bin/activate

# Bog'liqliklarni o'rnatish
pip install -r requirements.txt

# Migratsiyalarni bajarish
python manage.py migrate

# Superuser yaratish
python manage.py createsuperuser
```

## Ishga tushirish

### Telegram bot
```bash
python manage.py startbot
```

### Veb-server (WebSocket bilan)
```bash
daphne Fenix.asgi:application
```

### Sessiya tozalash (cron)
```bash
* * * * * cd /path/to/project && python manage.py cleanup_sessions
```

## Muhit o'zgaruvchilari

`.env` faylida:
```
SECRET_KEY=your-secret-key
DEBUG=False
WEB_DOMAIN=https://your-domain.com
```

## Stack

- **Backend**: Django, Django Channels, Aiogram
- **WebSocket**: Redis (channels_redis)
- **Ma'lumotlar bazasi**: SQLite (default)
- **Frontend**: Vanilla JS, Material Symbols
