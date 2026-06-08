# STUCK — Telegram & Web Chat Platform

A Django-based platform connecting clients with specialists through two channels:

1. **tgbot** — Aiogram-based Telegram bot
2. **webtgbot** — Django Channels WebSocket chat application

---

## Architecture

```
project/
├── Fenix/                    # Django project settings
│   ├── settings.py
│   ├── asgi.py              # ASGI config for WebSocket
│   ├── urls.py
│   └── wsgi.py
├── tgbot/                    # Telegram bot app
│   ├── dispatcher.py        # Aiogram bot instance
│   ├── models.py            # TelegramUser, Specialist, Client
│   ├── handlers/            # Bot message/command handlers
│   │   ├── commands.py      # /start, /stop, /list, /tinder...
│   │   ├── utils.py         # Callback handlers & message forwarding
│   │   └── states.py        # FSM state definitions
│   ├── logics/              # Business logic
│   │   ├── user.py          # User CRUD operations
│   │   ├── order.py         # Session/relation management
│   │   └── notify.py        # Telegram notifications
│   └── management/commands/
│       └── startbot.py      # Bot startup command
├── webtgbot/                 # Web chat app
│   ├── consumers.py         # WebSocket consumers (Chat + Notification)
│   ├── models.py            # WebUser, WebSpecialist, ChatSession, ChatMessage
│   ├── views.py             # REST API endpoints
│   ├── routing.py           # WebSocket URL routing
│   ├── static/webtgbot/
│   │   ├── js/app.js        # Frontend SPA
│   │   └── css/style.css
│   ├── templates/webtgbot/
│   │   └── index.html       # Main HTML template (multi-screen SPA)
│   └── management/commands/
│       └── cleanup_sessions.py  # Expired session cleanup
└── tgbot2/                   # Secondary bot (legacy version)
```

---

## Database Models

### tgbot

| Model | Fields | Description |
|-------|--------|-------------|
| **TelegramUser** | telegram_id, first_name, last_name, username, token | Telegram user record |
| **TelegramBotToken** | token | Bot token (single row enforced) |
| **Specialization** | name | Specialist category |
| **Specialist** | telegram_user (1:1), name, specialization (FK), description, photo_id, price, rating, is_active, client (1:1) | Specialist profile |
| **Client** | telegram_user (1:1), name, phone_number, photo_id, specialist (1:1), has_used_free_session | Client profile |

**Key relationship:** `Client.specialist` and `Specialist.client` form a circular OneToOne — both sides are set when a session is created and cleared when it ends.

### webtgbot

| Model | Fields | Description |
|-------|--------|-------------|
| **WebSpecialization** | name, order | Specialist category (web) |
| **WebSpecialist** | user (1:1 Django User), name, specialization (FK), description, photo, price, rating, is_active, is_online | Specialist profile (web) |
| **WebUser** | name, session_token | Web client (auth by name only) |
| **ChatSession** | client (FK), specialist (FK), started_at, expires_at, is_active, ended_at | Chat session (30 min free) |
| **ChatMessage** | session (FK), sender_type, message_type, content, file, is_read | Chat message (deleted after session) |
| **SupportGroup** | name, url, order | Support group links |
| **UserRequest** | name, problem, contact, is_processed | User query submission |

---

## TGBOT — Telegram Bot

### Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Register user, show welcome menu |
| `/list` | Browse specializations |
| `/tinder` | Swipe through random specialists |
| `/groups` | Show support group links |
| `/request` | Submit a query/problem |
| `/stop` | End active session |
| `/help` | Show available commands |
| `/id` | Show user's Telegram ID |

### Callback Handlers (utils.py)

| Callback Pattern | Action |
|-----------------|--------|
| `list` | Show specialization list |
| `special_{id}` | Show specialists for a specialization |
| `specialist_{id}` | Show specialist details with contact button |
| `contact_{spec_id}_{user_id}` | Create client-specialist session |
| `tinder` | Show next random specialist |
| `supgroups` | Show support groups |
| `leave_query` | Start query submission flow |

### Message Forwarding Logic (forward_message)

```
Incoming message from user
    │
    ├─ 1. Check WEB session (by specialist__telegram_user__telegram_id)
    │      └─ Found → route to web chat via HTTP bridge
    │
    ├─ 2. Check TG-TG relation (find_active_relation)
    │      └─ Found → forward to counterparty
    │
    └─ 3. No active sessions
           ├─ Is specialist → "no active sessions"
           ├─ Sends photo → save as profile photo
           └─ Otherwise → show /start menu
```

**Priority:** Web sessions are checked first. If a specialist has both an active web session and a TG session, messages go to the web chat.

### Session Creation Flow (contact_callback)

1. `is_specialist_busy()` — checks both TG `client` field and web `ChatSession`
2. `create_relation()` — sets `Client.specialist = Specialist` and `Specialist.client = Client`
3. `notify_telegram_session()` — sends "New session" notification to specialist
4. Client sees instructions from `stop.txt`

### Session Termination (/stop)

1. Check web session first → `end_session()` + WebSocket notification
2. Check TG relation → notify counterparty + `end_active_relation()`
3. `end_active_relation()` clears both sides and sets `has_used_free_session = True`

---

## WEBTGBOT — Web Chat

### API Endpoints

**User endpoints:**
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/register/` | POST | Register by name (returns session_token) |
| `/api/specializations/` | GET | List specializations |
| `/api/specialists/<id>/` | GET | Specialists by specialization |
| `/api/specialist/random/` | GET | Random specialist |
| `/api/groups/` | GET | Support groups |
| `/api/request/` | POST | Submit query |

**Session endpoints:**
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/session/create/` | POST | Create new chat session |
| `/api/session/stop/` | POST | End active session |
| `/api/session/active/` | GET | Specialist's active sessions |
| `/api/session/client/active/` | GET | Client's active session |
| `/api/session/<id>/messages/` | GET | Session message history |
| `/api/upload/` | POST | Upload media file |

**Specialist profile endpoints:**
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/specialist/login/` | POST | Login (Django auth) |
| `/api/specialist/profile/` | GET | Get profile |
| `/api/specialist/profile/update/` | POST | Update profile |
| `/api/specialist/photo/` | POST | Upload photo |
| `/api/specialist/password/` | POST | Change password |
| `/api/specialist/stats/` | GET | Statistics |
| `/api/specialist/online/` | POST | Toggle online status |

### WebSocket Routes

| URL | Purpose |
|-----|---------|
| `ws/chat/<session_id>/` | Chat room — messages, typing, read receipts, file uploads |
| `ws/notifications/<specialist_id>/` | Specialist notifications — new session alerts, online tracking |

### WebSocket Message Protocol

Client sends:
```json
{"type": "message", "content": "text", "message_type": "text"}
{"type": "typing", "is_typing": true}
{"type": "read", "message_id": 123}
{"type": "upload", "file": "base64...", "message_type": "image"}
```

Server broadcasts:
```json
{"type": "chat_message", "message_id": 1, "sender_type": "specialist", "content": "..."}
{"type": "typing", "is_typing": true}
{"type": "session_expired_notification", "message": "..."}
```

### Session Cleanup (cleanup_sessions.py)

Must run via cron every minute:
```bash
* * * * * cd /home/www && python manage.py cleanup_sessions
```

Actions:
- Ends expired sessions (`expires_at < now`)
- Deletes media files from disk
- Removes ChatMessage records
- Deletes session records older than 1 hour

---

## TGBOT vs WEBTGBOT

| Feature | TGBOT | WEBTGBOT |
|---------|-------|----------|
| Platform | Telegram bot | Web browser |
| Client auth | Automatic (Telegram) | Name only (session token) |
| Specialist auth | Telegram user record | Django User (login/password) |
| Chat protocol | Telegram API (message forwarding) | WebSocket (Django Channels) |
| Session duration | Unlimited | 30 minutes (configurable) |
| Message storage | None (relayed via Telegram) | ChatMessage model (deleted after session) |
| Media handling | Telegram file_id forwarding | Server upload (deleted after session) |
| Real-time features | Telegram built-in | Typing indicator, read receipts |

---

## Setup

```bash
git clone git@github.com:EldorKenjabayev/stuckapp.git
cd stuckapp
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
```

## Running

```bash
# Telegram bot
python manage.py startbot

# Web server with WebSocket support
daphne Fenix.asgi:application

# Session cleanup (add to cron)
* * * * * cd /home/www && python manage.py cleanup_sessions
```

## Configuration

### Bot Token
Set via Django Admin (`/admin/`):
1. Tgbot → Telegram bot tokens → Add

### Session Duration
Edit `SESSION_DURATION_MINUTES` in `webtgbot/models.py` (default: 30)

### Environment Variables (`.env`)
```
SECRET_KEY=your-secret-key
DEBUG=False
WEB_DOMAIN=https://your-domain.com
```

## Tech Stack

- **Backend**: Django, Django Channels, Aiogram 3.x
- **WebSocket**: Django Channels + Redis (channels_redis)
- **Database**: SQLite (default)
- **Frontend**: Vanilla JavaScript SPA, Material Symbols icons
- **Server**: Gunicorn + Daphne, Nginx reverse proxy
- **Libraries**: httpx, loguru, apscheduler
