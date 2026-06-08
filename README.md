# STUCK — Telegram & Web Chat Platform

Mijozlarni mutaxassislar bilan bog'laydigan Django platforma. Ikkita asosiy ilovadan iborat:

1. **tgbot** — Aiogram asosidagi Telegram bot
2. **webtgbot** — Django Channels asosidagi veb-chat (WebSocket)

---

## Arxitektura

```
project/
├── Fenix/                    # Django loyiha sozlamalari
│   ├── settings.py
│   ├── asgi.py              # WebSocket uchun ASGI konfiguratsiya
│   ├── urls.py
│   └── wsgi.py
├── tgbot/                    # Telegram bot ilovasi
│   ├── dispatcher.py        # Aiogram bot instance
│   ├── models.py            # TelegramUser, Specialist, Client
│   ├── handlers/            # Bot handlerlari
│   │   ├── commands.py      # /start, /stop, /list, /tinder...
│   │   ├── utils.py         # Callback va xabarlarni yo'naltirish
│   │   └── states.py        # FSM holatlar
│   ├── logics/              # Biznes logika
│   │   ├── user.py          # Foydalanuvchi boshqaruvi
│   │   ├── order.py         # Sessiya boshqaruvi
│   │   └── notify.py        # Bildirishnomalar
│   └── management/commands/
│       └── startbot.py      # Botni ishga tushirish komandasi
├── webtgbot/                 # Veb-chat ilovasi
│   ├── consumers.py         # WebSocket consumerlar
│   ├── models.py            # WebUser, WebSpecialist, ChatSession
│   ├── views.py             # REST API endpointlar
│   ├── routing.py           # WebSocket marshrutlar
│   ├── static/webtgbot/
│   │   ├── js/app.js        # Frontend JavaScript (SPA)
│   │   └── css/style.css
│   ├── templates/webtgbot/
│   │   └── index.html       # Asosiy HTML shablon
│   └── management/commands/
│       └── cleanup_sessions.py  # Sessiyalarni tozalash
└── tgbot2/                   # Ikkinchi bot (eski versiya)
```

---

## Ma'lumotlar bazasi modellari

### tgbot

| Model | Maydonlari | Tavsifi |
|-------|-----------|---------|
| **TelegramUser** | telegram_id, first_name, last_name, username, token | Telegram foydalanuvchisi |
| **TelegramBotToken** | token | Bot tokeni (faqat bitta) |
| **Specialization** | name | Mutaxassislik yo'nalishi |
| **Specialist** | telegram_user (1:1), name, specialization (FK), description, photo_id, price, rating, is_active, client (1:1) | Mutaxassis profili |
| **Client** | telegram_user (1:1), name, phone_number, photo_id, specialist (1:1), has_used_free_session | Mijoz profili |

**Muhim:** Client va Specialist o'rtasida o'zaro OneToOne aloqa mavjud. `Client.specialist` va `Specialist.client` maydonlari orqali bog'lanadi.

### webtgbot

| Model | Maydonlari | Tavsifi |
|-------|-----------|---------|
| **WebSpecialization** | name, order | Mutaxassislik yo'nalishi (veb) |
| **WebSpecialist** | user (1:1 Django User), name, specialization (FK), description, photo, price, rating, is_active, is_online | Mutaxassis profili (veb) |
| **WebUser** | name, session_token | Veb foydalanuvchi (ismsiz ro'yxatdan o'tish) |
| **ChatSession** | client (FK), specialist (FK), started_at, expires_at, is_active, ended_at | Chat sessiyasi (30 daq bepul) |
| **ChatMessage** | session (FK), sender_type, message_type, content, file, is_read | Xabar (sessiya tugagach o'chiriladi) |
| **SupportGroup** | name, url, order | Qo'llab-quvvatlash guruhi havolalari |
| **UserRequest** | name, problem, contact, is_processed | Foydalanuvchi murojaati |

---

## TGBOT — Telegram bot

### Komandalar

| Komanda | Vazifasi |
|---------|----------|
| `/start` | Ro'yxatdan o'tish, salomlashish, menyuni ko'rsatish |
| `/list` | Mutaxassisliklar ro'yxatini ko'rsatish |
| `/tinder` | Tasodifiy mutaxassisni ko'rsatish (surish interfeysi) |
| `/groups` | Qo'llab-quvvatlash guruhlari havolalari |
| `/request` | Muammo/savol qoldirish |
| `/stop` | Faol sessiyani tugatish |
| `/help` | Barcha komandalar ro'yxati |
| `/id` | Telegram ID ni ko'rsatish |

### Callback handlerlar (utils.py)

| Callback | Vazifasi |
|----------|----------|
| `list` | Mutaxassisliklar ro'yxati |
| `special_{id}` | Tanlangan mutaxassislik bo'yicha mutaxassislar |
| `specialist_{id}` | Mutaxassis haqida batafsil ma'lumot |
| `contact_{spec_id}_{user_id}` | Mijoz va mutaxassis o'rtasida sessiya yaratish |
| `tinder` | Tasodifiy mutaxassis |
| `supgroups` | Guruhlar ro'yxati |
| `leave_query` | Murojaat qoldirish formasini boshlash |

### Xabarlarni yo'naltirish (forward_message)

```
Foydalanuvchi xabari
    │
    ├─ 1. Veb-sessiya tekshiriladi (specialist__telegram_user__telegram_id bo'yicha)
    │      └─ Topilsa → veb-chatga yo'naltiriladi
    │
    ├─ 2. TG-TG aloqa tekshiriladi (find_active_relation)
    │      └─ Topilsa → qarshi tarafga yo'naltiriladi
    │
    └─ 3. Hech narsa topilmasa
           ├─ Mutaxassis bo'lsa → "нет активных сессий"
           └─ Oddiy foydalanuvchi → /start kabi menyu ko'rsatiladi
```

### Sessiya yaratish jarayoni (contact_callback)

1. `is_specialist_busy()` — mutaxassis band emasligini tekshiradi (TG + Web)
2. `create_relation()` — `Client.specialist` va `Specialist.client` o'rnatiladi
3. `notify_telegram_session()` — mutaxassisga bildirishnoma yuboriladi
4. Mijozga `stop.txt` matni ko'rsatiladi

### Sessiya tugatish (/stop)

1. Avval veb-sessiya tekshiriladi (`specialist__telegram_user__telegram_id` bo'yicha)
2. Veb-sessiya topilsa → `web_session.end_session()` + WebSocket xabar
3. TG sessiya topilsa → qarshi tarafga bildirishnoma + `end_active_relation()`
4. `end_active_relation()` ikkala tomonni ham tozalaydi va `has_used_free_session = True` qiladi

---

## WEBTGBOT — Veb-chat

### API Endpointlar

**Foydalanuvchi:**
| Endpoint | Metod | Vazifasi |
|----------|-------|----------|
| `/api/register/` | POST | Ism bilan ro'yxatdan o'tish (session_token qaytaradi) |
| `/api/specializations/` | GET | Mutaxassisliklar ro'yxati |
| `/api/specialists/<id>/` | GET | Mutaxassislik bo'yicha mutaxassislar |
| `/api/specialist/random/` | GET | Tasodifiy mutaxassis |
| `/api/groups/` | GET | Qo'llab-quvvatlash guruhlari |
| `/api/request/` | POST | Murojaat qoldirish |

**Sessiya:**
| Endpoint | Metod | Vazifasi |
|----------|-------|----------|
| `/api/session/create/` | POST | Yangi chat sessiyasi yaratish |
| `/api/session/stop/` | POST | Faol sessiyani tugatish |
| `/api/session/active/` | GET | Mutaxassisning faol sessiyalari |
| `/api/session/client/active/` | GET | Mijozning faol sessiyasi |
| `/api/session/<id>/messages/` | GET | Sessiya xabarlari tarixi |
| `/api/upload/` | POST | Media fayl yuklash |

**Mutaxassis profili:**
| Endpoint | Metod | Vazifasi |
|----------|-------|----------|
| `/api/specialist/login/` | POST | Login (Django username/password) |
| `/api/specialist/profile/` | GET | Profil ma'lumotlari |
| `/api/specialist/profile/update/` | POST | Profilni yangilash |
| `/api/specialist/photo/` | POST | Rasm yuklash |
| `/api/specialist/password/` | POST | Parolni o'zgartirish |
| `/api/specialist/stats/` | GET | Statistikalar |
| `/api/specialist/online/` | POST | Online holatini o'zgartirish |

### WebSocket marshrutlari

| URL | Vazifasi |
|-----|----------|
| `ws/chat/<session_id>/` | Chat xonasi (xabarlar, typing, read receipts) |
| `ws/notifications/<specialist_id>/` | Mutaxassis bildirishnomalari (yangi sessiya) |

### WebSocket xabarlar turlari

ChatConsumer qabul qiladigan JSON xabarlar:
```json
{"type": "message", "content": "matn", "message_type": "text"}
{"type": "typing", "is_typing": true}
{"type": "read", "message_id": 123}
{"type": "upload", "file": "base64...", "message_type": "image"}
```

### Sessiya tozalash (cleanup_sessions.py)

Har daqiqada cron orqali ishga tushirilishi kerak:
```bash
* * * * * cd /home/www && python manage.py cleanup_sessions
```

Nima qiladi:
- Muddat tugagan sessiyalarni yakunlaydi
- Media fayllarni diskdan o'chiradi
- Xabarlarni bazadan o'chiradi
- 1 soatdan eski sessiya yozuvlarini o'chiradi

---

## TGBOT va WEBTGBOT farqlari

| Xususiyat | TGBOT | WEBTGBOT |
|-----------|-------|----------|
| Platforma | Telegram bot | Veb-brauzer |
| Mijoz autentifikatsiyasi | Telegram orqali avtomatik | Ism orqali (session_token) |
| Mutaxassis autentifikatsiyasi | Telegram foydalanuvchisi | Django User (login/parol) |
| Chat protokoli | Telegram API | WebSocket |
| Sessiya davomiyligi | Cheksiz | 30 daqiqa (sozlanadi) |
| Xabarlar saqlanishi | Telegram orqali yo'naltiriladi | ChatMessage da saqlanadi, sessiyadan keyin o'chiriladi |
| Media | Telegram file_id orqali | Serverga yuklanadi, sessiyadan keyin o'chiriladi |
| Real-time imkoniyatlar | Telegram'ning o'zida | WebSocket (typing, read receipts) |

---

## O'rnatish

```bash
git clone git@github.com:EldorKenjabayev/stuckapp.git
cd stuckapp
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
```

## Ishga tushirish

```bash
# Telegram bot
python manage.py startbot

# Veb-server (WebSocket bilan)
daphne Fenix.asgi:application

# Sessiya tozalash (cron)
* * * * * cd /home/www && python manage.py cleanup_sessions
```

## Sozlash

### Bot tokeni
Admin panel orqali (`/admin/`):
1. Tgbot → Telegram bot tokens
2. Yangi token qo'shish (faqat bitta bo'lishi kerak)

### Sessiya davomiyligi
`webtgbot/models.py` da `SESSION_DURATION_MINUTES` o'zgaruvchisi (default: 30)

### .env fayli
```
SECRET_KEY=your-secret-key
DEBUG=False
WEB_DOMAIN=https://your-domain.com
```

## Texnologik stack

- **Backend**: Django, Django Channels, Aiogram 3.x
- **WebSocket**: Django Channels + Redis (channels_redis)
- **Ma'lumotlar bazasi**: SQLite
- **Frontend**: Vanilla JS (SPA), Material Symbols icons
- **Server**: Gunicorn + Daphne, Nginx reverse proxy
- **Kutubxonalar**: httpx, loguru, apscheduler
