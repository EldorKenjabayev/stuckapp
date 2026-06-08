# Project Documentation: STUCK - Telegram & Web Chat Platform

## Overview
This is a Django-based platform consisting of two main applications:
1. **tgbot** - Telegram bot for connecting clients with specialists
2. **webtgbot** - Web-based chat application with real-time messaging

---

## 1. TGBOT Application

### Purpose
Telegram bot that allows users (clients) to find and connect with specialists for consultation via Telegram messaging.

### Directory Structure

```
tgbot/
├── __init__.py              # Empty module file
├── apps.py                 # Django app configuration (TgbotConfig)
├── admin.py                # Admin panel for managing Telegram users and specialists
├── dispatcher.py           # Aiogram bot instance initialization
├── models.py               # Database models (TelegramUser, Specialist, Client, etc.)
├── urls.py                # URL routes (main page with user list)
├── views.py               # View for displaying Telegram users
├── handlers/              # Bot message and command handlers
│   ├── __init__.py
│   ├── commands.py        # Command handlers (/start, /list, /stop, /tinder, etc.)
│   ├── states.py          # FSM state definitions (Form, Query)
│   ├── utils.py          # Callback handlers and message forwarding
│   ├── test.md           # Test documentation
│   └── stop.txt          # Text template for session stop message
├── logics/               # Business logic functions
│   ├── __init__.py
│   ├── user.py           # User management (CRUD operations for users/clients/specialists)
│   └── order.py          # Order/session management (specialist-client relations)
├── management/           # Django management commands
│   └── commands/
│       ├── __init__.py
│       └── startbot.py   # Command to start the Telegram bot
└── migrations/           # Database migrations
```

### Models (tgbot/models.py)

| Model | Description | Key Fields |
|-------|-------------|------------|
| **TelegramUser** | Stores Telegram user data | telegram_id, first_name, last_name, username, is_admin, avatar_url, token |
| **TelegramBotToken** | Stores bot token | token |
| **Specialization** | Categories of specialists | name |
| **Specialist** | Specialist profile | telegram_user (OneToOne), name, specialization (FK), description, photo_id, price, rating, is_active, client (OneToOne) |
| **Client** | Client profile | telegram_user (OneToOne), name, phone_number, photo_id, specialist (OneToOne) |

### Key Files & Their Responsibilities

#### **tgbot/dispatcher.py**
- Initializes the Aiogram bot instance
- Bot token is fetched from `TelegramBotToken` model
- Sets HTML parse mode for messages

#### **tgbot/management/commands/startbot.py**
- Django management command to start the bot
- Initializes Aiogram dispatcher
- Includes command and utility routers
- Sends startup notification to admin users

#### **tgbot/handlers/commands.py**
Main command handlers for the bot:

| Command | Description |
|---------|-------------|
| `/start` | Creates user, shows welcome message, displays specialist/menu options |
| `/list` | Shows list of specializations to choose from |
| `/tinder` | Shows random specialist (swipe interface) |
| `/groups` | Displays support group links |
| `/request` | Allows user to leave a query/problem |
| `/stop` | Ends active specialist-client session |
| `/help` | Shows available commands |
| `/id` | Returns user's Telegram ID |

#### **tgbot/handlers/states.py**
FSM (Finite State Machine) state definitions:

- **Form**: For selecting specialist
  - `name`, `specialization`, `specialist_dict` states
- **Query**: For leaving a request
  - `name`, `desc` states

#### **tgbot/handlers/utils.py**
Callback handlers and message forwarding logic:

| Callback | Description |
|----------|-------------|
| `list` | Show specializations list |
| `special_{id}` | Show specialists for given specialization |
| `specialist_{id}` | Show specialist details with contact button |
| `contact_{spec_id}_{user_id}` | Create session between client and specialist |
| `tinder` | Show random specialist |
| `supgroups` | Show support groups |
| `leave_query` | Start query submission flow |

**Message Handlers:**
- Text messages: Forwarded between client and specialist in active session
- Photo messages: Forwarded or saved as specialist profile photo
- Video notes: Forwarded in active session
- Voice messages: Forwarded in active session

#### **tgbot/logics/user.py**
User management functions:

| Function | Description |
|-----------|-------------|
| `create_telegram_user()` | Create or update Telegram user, auto-create Client |
| `get_client_by_telegram_id()` | Get client by Telegram ID |
| `get_specialist_by_telegram_id()` | Get specialist by Telegram ID |
| `get_client_by_id()` | Get client by user ID |
| `get_specialist_by_id()` | Get specialist by ID |
| `change_photo_id()` | Update user's profile photo |
| `create_relation()` | Create client-specialist relation |
| `end_active_relation()` | End active session for user |

#### **tgbot/logics/order.py**
Session and specialist management:

| Function | Description |
|-----------|-------------|
| `get_specializations()` | Get all specializations |
| `get_specialist_dict()` | Get specialists by specialization ID |
| `get_specialists_dict()` | Get random specialist for tinder |
| `create_relation()` | Create client-specialist connection |
| `end_relation()` | End client-specialist connection |
| `find_active_relation()` | Find active session by Telegram ID |
| `end_active_relation()` | End active session by Telegram ID |

---

## 2. WEBTGBOT Application

### Purpose
Web-based real-time chat application where clients can chat with specialists via browser using WebSocket.

### Directory Structure

```
webtgbot/
├── __init__.py              # Empty module file
├── apps.py                 # Django app configuration (WebtgbotConfig)
├── admin.py                # Admin panel for managing web specialists, sessions
├── consumers.py            # WebSocket consumers for real-time chat
├── models.py              # Database models for web chat
├── urls.py                # URL routes for API and pages
├── views.py               # API view functions
├── routing.py             # WebSocket URL patterns
├── management/            # Django management commands
│   └── commands/
│       ├── __init__.py
│       └── cleanup_sessions.py  # Clean expired sessions and files
├── static/               # Static files
│   └── webtgbot/
│       ├── css/
│       │   ├── style.css
│       │   └── style_backup.css
│       ├── js/
│       │   └── app.js           # Frontend JavaScript application
│       └── img/
│           ├── logo.jpg
│           ├── wallpaperflare.com_wallpaper.jpg
│           └── white-bacgroud.jpg
└── templates/
    └── webtgbot/
        └── index.html          # Main web application page
```

### Models (webtgbot/models.py)

| Model | Description | Key Fields |
|-------|-------------|------------|
| **WebSpecialization** | Specialist categories for web chat | name, order |
| **WebSpecialist** | Specialist profile (auth via Django User) | user (OneToOne to User), name, specialization (FK), description, photo, price, rating, is_active, is_online |
| **WebUser** | Web chat user (auth via name only) | name, session_token (auto-generated) |
| **ChatSession** | Chat session (30 min free) | client (FK), specialist (FK), started_at, expires_at, is_active, ended_at |
| **ChatMessage** | Message in chat (deleted after session ends) | session (FK), sender_type, message_type, content, file, is_read |
| **SupportGroup** | Support group links | name, url, order |
| **UserRequest** | User request/problem submission | name, problem, is_processed |

### Key Files & Their Responsibilities

#### **webtgbot/consumers.py**
WebSocket consumers for real-time messaging:

**ChatConsumer**
- Connects clients and specialists via WebSocket
- Handles: messages, typing indicators, read receipts, file uploads
- Validates session expiration
- Broadcasts messages to chat room
- Methods: `connect()`, `disconnect()`, `receive()`, `handle_message()`, `handle_typing()`, etc.

**NotificationConsumer**
- Sends notifications to specialists about new sessions
- Tracks specialist online status
- Methods: `connect()`, `disconnect()`, `new_session_notification()`, etc.

#### **webtgbot/views.py**
API endpoints (all return JSON):

**User Endpoints:**
| Endpoint | Description |
|----------|-------------|
| `/api/register/` | Register new user (by name) |
| `/api/specializations/` | Get list of specializations |
| `/api/specialists/<spec_id>/` | Get specialists by specialization |
| `/api/specialist/random/` | Get random specialist (tinder) |
| `/api/groups/` | Get support groups |
| `/api/request/` | Submit user request |

**Session Endpoints:**
| Endpoint | Description |
|----------|-------------|
| `/api/session/create/` | Create new chat session |
| `/api/session/stop/` | End active session |
| `/api/session/active/` | Get specialist's active sessions |
| `/api/session/client/active/` | Get client's active session |
| `/api/session/<id>/messages/` | Get session message history |
| `/api/upload/` | Upload media file |

**Specialist Profile Endpoints:**
| Endpoint | Description |
|----------|-------------|
| `/api/specialist/login/` | Specialist login (Django auth) |
| `/api/specialist/profile/` | Get specialist profile |
| `/api/specialist/profile/update/` | Update specialist profile |
| `/api/specialist/photo/` | Upload specialist photo |
| `/api/specialist/password/` | Change specialist password |
| `/api/specialist/stats/` | Get specialist statistics |
| `/api/specialist/online/` | Toggle online status |

#### **webtgbot/routing.py**
WebSocket URL patterns:
- `ws/chat/<session_id>/` - Chat room WebSocket
- `ws/notifications/<specialist_id>/` - Specialist notification WebSocket

#### **webtgbot/management/commands/cleanup_sessions.py**
Django command to clean expired sessions:
- Ends expired sessions
- Deletes media files from disk
- Removes message records
- Deletes old session records (>1 hour)
- Should run via cron every minute

#### **webtgbot/static/webtgbot/js/app.js**
Frontend JavaScript application:
- State management (user, specialist, session, WebSocket)
- User registration flow
- Specialist login flow
- Chat interface with real-time messaging
- Media upload (images, audio, voice)
- Session timer (30-minute countdown)
- Theme switching (dark/light)
- Support for Material Symbols icons

#### **webtgbot/templates/webtgbot/index.html**
Main web application HTML template:
- Multi-screen SPA (Single Page Application)
- Screens: Register, Menu, Specialist List, Tinder, Chat, Dashboard
- Responsive design for mobile/desktop
- Material Symbols icons
- WebSocket integration
- File upload interface

---

## Main Differences Between TGBOT and WEBTGBOT

| Feature | TGBOT | WEBTGBOT |
|---------|---------|-----------|
| Platform | Telegram bot | Web browser |
| Client Auth | Automatic via Telegram | By name only (session token) |
| Specialist Auth | Via Telegram user | Via Django User (username/password) |
| Chat Protocol | Telegram API | WebSocket |
| Session Duration | Unlimited | 30 minutes (configurable) |
| Message Storage | Forwarded via Telegram | Stored in ChatMessage model, deleted after session |
| Media Handling | Forwarded via Telegram file IDs | Uploaded to server, deleted after session |
| Real-time Features | Telegram's built-in | WebSocket-based (typing, read receipts) |
| Admin Management | Django admin | Django admin |

---

## How the System Works

### Telegram Bot Flow (tgbot)
1. User sends `/start` to bot
2. Bot creates `TelegramUser` and `Client` records
3. User can:
   - Browse specializations (`/list`)
   - Use Tinder to find specialist (`/tinder`)
   - Join support groups (`/groups`)
   - Submit a query (`/request`)
4. User selects specialist → Bot creates relation
5. All messages are forwarded between client and specialist
6. Either party can end session with `/stop`

### Web Chat Flow (webtgbot)
1. Client registers by name → Gets session token
2. Specialist logs in with username/password
3. Client selects specialist → `ChatSession` created (30 min)
4. Both parties connect via WebSocket
5. Messages sent/received in real-time
6. Timer counts down; session auto-ends on expiry
7. Messages and media deleted after session ends
8. Specialist can toggle online status

---

## Dependencies

### tgbot
- aiogram - Telegram bot framework
- loguru - Logging
- apscheduler - Scheduled tasks (for media groups)

### webtgbot
- channels - WebSocket support (Django Channels)
- channels_redis - Redis backend for Channels
- Django auth for specialists

---

## Running the Application

### Start Telegram Bot
```bash
python manage.py startbot
```

### Start Web Application
```bash
python manage.py runserver
# or with daphne for WebSocket support
daphne project_name.asgi:application
```

### Run Session Cleanup
```bash
python manage.py cleanup_sessions
# Add to cron: * * * * * cd /path/to/project && python manage.py cleanup_sessions
```

---

## Database

Both apps share the same SQLite database (db.sqlite3) but use separate models:
- `tgbot` uses Telegram-specific models
- `webtgbot` uses web-specific models

Run migrations:
```bash
python manage.py makemigrations
python manage.py migrate
```

---

## Configuration

### Bot Token
Set via Django Admin:
1. Login to `/admin/`
2. Go to Tgbot → Telegram bot tokens
3. Add the bot token (only one allowed)

### Session Duration (webtgbot)
Edit `SESSION_DURATION_MINUTES` in `webtgbot/models.py` (default: 30)

### Support Groups
Add via Django Admin:
1. Login to `/admin/`
2. Go to Webtgbot → Groups support (Web)

### Specialists
- **Telegram**: Add via admin (create TelegramUser → create Specialist)
- **Web**: Add via admin (special form creates User and Specialist together)

---

## Admin Panels

### tgbot Admin
- Telegram users (searchable by ID, name, username)
- Specialists (with specialization, price, rating)
- Clients (with phone, assigned specialist)
- Specializations

### webtgbot Admin
- Web users (with session tokens)
- Web specialists (with Django User credentials)
- Chat sessions (with message history inline)
- Support groups
- User requests
