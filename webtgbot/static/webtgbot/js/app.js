/* ============================================
   FENIX WEB CHAT — MAIN APPLICATION v2
   Material Symbols + Fixed Voice + Session Persistence
   ============================================ */

// ─── State ──────────────────────────────────────
const APP = {
    user: null,          // { id, name, token }
    specialist: null,    // { id, name, specialization, photo, django_session }
    role: 'client',      // 'client' | 'specialist'
    session: null,       // { id, specialist_name, specialist_photo, expires_at, remaining_seconds }
    ws: null,            // WebSocket instance
    wsNotify: null,      // Specialist notification WS
    timerInterval: null,
    currentSpecialistId: null, // for tinder
    recording: {
        active: false,
        mediaRecorder: null,
        chunks: [],
        startTime: null,
        timerInterval: null,
        stream: null,
        readyToSend: false, // NEW: flag to track if stop should send
    },
    stickerOpen: false,
    typingTimeout: null,
    fileUploadType: 'image',
    voiceAudio: null,    // for playback
};

const API_BASE = '/chat/api';

// ─── Utility ────────────────────────────────────
function showToast(msg, type = '') {
    const t = document.getElementById('toast');
    t.textContent = msg;
    t.className = 'toast show ' + type;
    setTimeout(() => t.className = 'toast', 3500);
}

function showScreen(id) {
    document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
    const screen = document.getElementById(id);
    if (screen) screen.classList.add('active');
}

async function api(endpoint, options = {}) {
    const url = API_BASE + endpoint;
    const config = {
        headers: { 'Content-Type': 'application/json' },
        ...options,
    };
    const res = await fetch(url, config);
    return res.json();
}

function formatTime(seconds) {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}:${s.toString().padStart(2, '0')}`;
}

// ─── Session Persistence ───────────────────────
function saveSessionState() {
    if (APP.session) {
        localStorage.setItem('fenix_session', JSON.stringify(APP.session));
        localStorage.setItem('fenix_role', APP.role);
    }
}

function clearSessionState() {
    localStorage.removeItem('fenix_session');
    localStorage.removeItem('fenix_role');
}

// ─── Registration ───────────────────────────────
async function registerUser() {
    const name = document.getElementById('registerName').value.trim();
    if (!name || name.length < 2) {
        showToast('Введите имя (минимум 2 символа)', 'error');
        return;
    }

    const btn = document.getElementById('registerBtn');
    btn.disabled = true;
    btn.innerHTML = '<div class="spinner" style="width:20px;height:20px;border-width:2px;margin:0;"></div>';

    try {
        const data = await api('/register/', {
            method: 'POST',
            body: JSON.stringify({ name }),
        });

        if (data.success) {
            APP.user = data.user;
            APP.role = 'client';
            localStorage.setItem('fenix_user', JSON.stringify(APP.user));
            document.getElementById('userName').textContent = name;
            document.getElementById('requestName').value = name;
            showScreen('screenMenu');
            showToast(`Добро пожаловать, ${name}!`, 'success');

            // Request notification permission
            if ('Notification' in window && Notification.permission === 'default') {
                Notification.requestPermission();
            }
        } else {
            showToast(data.error || 'Ошибка регистрации', 'error');
        }
    } catch (e) {
        showToast('Ошибка соединения', 'error');
    }

    btn.disabled = false;
    btn.innerHTML = '<span class="material-symbols-rounded">rocket_launch</span> Начать';
}

// ─── Specialist Login ───────────────────────────
async function specialistLogin() {
    const username = document.getElementById('specUsername').value.trim();
    const password = document.getElementById('specPassword').value.trim();

    if (!username || !password) {
        showToast('Введите логин и пароль', 'error');
        return;
    }

    try {
        const data = await api('/specialist/login/', {
            method: 'POST',
            body: JSON.stringify({ username, password }),
        });

        if (data.success) {
            APP.specialist = data.specialist;
            APP.role = 'specialist';
            localStorage.setItem('fenix_specialist', JSON.stringify(APP.specialist));
            document.getElementById('specName').textContent = APP.specialist.name;
            showScreen('screenDashboard');
            showToast(`Добро пожаловать, ${APP.specialist.name}!`, 'success');
            loadDashboard();
            loadSpecialistStats();
            updateDashboardAvatar();
            connectSpecialistNotifications();
        } else {
            showToast(data.error || 'Ошибка входа', 'error');
        }
    } catch (e) {
        showToast('Ошибка соединения', 'error');
    }
}

function specialistLogout() {
    APP.specialist = null;
    APP.role = 'client';
    localStorage.removeItem('fenix_specialist');
    clearSessionState();
    if (APP.wsNotify) APP.wsNotify.close();
    showScreen('screenRegister');
}

// ─── Main Menu ──────────────────────────────────
function backToMenu() {
    if (APP.role === 'specialist') {
        showScreen('screenDashboard');
        loadDashboard(); // Mutaxassis qaytganda dashboard yangilansin
    } else {
        showScreen('screenMenu');
        // Show active session banner if active
        updateActiveSessionBanner();
    }
    closeStickerPicker();
    document.getElementById('sessionOverlay').classList.remove('show');
}

function updateActiveSessionBanner() {
    const banner = document.getElementById('activeSessionBanner');
    const nameEl = document.getElementById('activeSessionName');
    if (APP.session) {
        nameEl.textContent = APP.session.specialist_name || 'Специалист';
        banner.classList.remove('hidden');
    } else {
        banner.classList.add('hidden');
    }
}

// ─── Specializations ───────────────────────────
async function openSpecializations() {
    showScreen('screenSpecializations');
    const container = document.getElementById('specList');
    container.innerHTML = '<div class="spinner"></div>';

    try {
        const data = await api('/specializations/');
        if (data.specializations && data.specializations.length > 0) {
            container.innerHTML = data.specializations.map(s => `
                <div class="spec-item glass-card" onclick="openSpecialists(${s.id}, '${escapeAttr(s.name)}')">
                    <div class="spec-name">${escapeHtml(s.name)}</div>
                    <div class="spec-count" style="color: #ffffff; background-color:#0088cc;">${s.count} спец.</div>
                </div>
            `).join('');
        } else {
            container.innerHTML = '<p class="text-center text-muted" style="padding:40px;">Нет доступных специализаций</p>';
        }
    } catch (e) {
        container.innerHTML = '<p class="text-center text-muted">Ошибка загрузки</p>';
    }
}

// ─── Specialists ────────────────────────────────
// ─── Specialists ────────────────────────────────
async function openSpecialists(specId, specName) {
    showScreen('screenSpecialists');
    document.getElementById('specTitle').textContent = specName;
    const container = document.getElementById('specialistList');
    container.innerHTML = '<div class="spinner"></div>';

    try {
        const data = await api(`/specialists/${specId}/`);
        if (data.specialists && data.specialists.length > 0) {
            // Render only names, bot style
            container.className = 'specialist-list-simple';
            container.innerHTML = data.specialists.map(sp => `
                <div class="specialist-item-simple" onclick='showSpecialistDetail(${JSON.stringify(sp)})'>
                    ${escapeHtml(sp.name)}
                </div>
            `).join('');
        } else {
            container.innerHTML = '<p class="text-center text-muted" style="padding:40px;">Нет доступных специалистов</p>';
        }
    } catch (e) {
        container.innerHTML = '<p class="text-center text-muted">Ошибка загрузки</p>';
    }
}

// ─── Tinder ─────────────────────────────────────
async function openTinder() {
    showScreen('screenTinder');
    APP.currentSpecialistId = null;
    await loadTinderCard();
}

async function loadTinderCard() {
    const card = document.getElementById('tinderCard');
    card.className = 'tinder-card appear';
    card.innerHTML = '<div class="spinner"></div>';

    try {
        const exclude = APP.currentSpecialistId ? `?exclude=${APP.currentSpecialistId}` : '';
        const data = await api(`/specialist/random/${exclude}`);
        const sp = data.specialist;

        if (!sp) {
            card.innerHTML = '<div style="padding:40px; text-align:center;"><p class="text-muted">Специалисты не найдены</p></div>';
            return;
        }

        APP.currentSpecialistId = sp.id;

        card.innerHTML = `
            ${sp.photo ? `<div class="tinder-photo"><img src="${sp.photo}" alt="${escapeAttr(sp.name)}" onerror="this.parentElement.style.display='none'"></div>` : ''}
            <div class="tinder-details">
                <div class="tinder-desc"><b>Специалист: </b> ${escapeHtml(sp.name)}</div>
                <div class="tinder-desc"><b>Описание:</b> ${escapeHtml((sp.description || 'Профессиональная консультация').trim())}</div>
                <div class="tinder-separator"></div>
                <div class="tinder-stat"><b>Сеанс:</b> ${sp.price} руб.</div>
                <div class="tinder-stat"><b>Рейтинг:</b> ${sp.rating}</div>
            </div>
        `;
    } catch (e) {
        card.innerHTML = '<div style="padding:40px; text-align:center;"><p class="text-muted">Ошибка загрузки</p></div>';
    }
}

function showSpecialistDetail(sp) {
    const overlay = document.getElementById('specialistDetailOverlay');
    const photoWrap = document.getElementById('specDetailPhotoWrap');
    const photoImg = document.getElementById('specDetailPhoto');
    const nameEl = document.getElementById('specDetailName');
    const infoEl = document.getElementById('specDetailInfo');
    const chatBtn = document.getElementById('specDetailChatBtn');

    nameEl.textContent = sp.name;

    // Formatting info EXACTLY like bot/tinder card
    let infoHtml = `<div class="tinder-desc"><b>Специалист: </b> ${escapeHtml(sp.name)}</div>`;
    infoHtml += `<div class="tinder-desc"><b>Описание:</b> ${escapeHtml((sp.description || 'Профессиональная консультация').trim())}</div>`;
    infoHtml += `<b>Сеанс:</b> ${sp.price} руб.<br>`;
    infoHtml += `<b>Рейтинг:</b> ${sp.rating}`;

    infoEl.innerHTML = infoHtml;

    if (sp.photo) {
        photoImg.src = sp.photo;
        photoImg.onerror = () => { photoWrap.style.display = 'none'; };
        photoWrap.style.display = 'block';
    } else {
        photoWrap.style.display = 'none';
    }

    chatBtn.onclick = () => {
        closeSpecialistDetail();
        startSessionWith(sp.id);
    };

    overlay.classList.add('show');
}

function closeSpecialistDetail() {
    document.getElementById('specialistDetailOverlay').classList.remove('show');
}

function tinderSkip() {
    const card = document.getElementById('tinderCard');
    card.classList.add('swipe-left');
    setTimeout(() => loadTinderCard(), 500);
}

function tinderConnect() {
    if (APP.currentSpecialistId) {
        startSessionWith(APP.currentSpecialistId);
    }
}

// ─── Support Groups ─────────────────────────────
async function openGroups() {
    showScreen('screenGroups');
    const container = document.getElementById('groupList');
    container.innerHTML = '<div class="spinner"></div>';

    try {
        const data = await api('/groups/');
        if (data.groups && data.groups.length > 0) {
            container.innerHTML = data.groups.map(g => `
                <a href="${g.url}" target="_blank" rel="noopener" class="group-item glass-card">
                    <div class="group-name">${escapeHtml(g.name)}</div>
                    <span class="material-symbols-rounded" style="color:var(--text-muted);font-size:20px;">open_in_new</span>
                </a>
            `).join('');
        } else {
            container.innerHTML = '<p class="text-center text-muted" style="padding:40px;">Нет доступных групп</p>';
        }
    } catch (e) {
        container.innerHTML = '<p class="text-center text-muted">Ошибка загрузки</p>';
    }
}

// ─── Request ────────────────────────────────────
function openRequest() {
    showScreen('screenRequest');
    document.getElementById('requestForm').style.display = 'flex';
    document.getElementById('requestSuccess').style.display = 'none';
    if (APP.user) {
        document.getElementById('requestName').value = APP.user.name;
    }
}

async function submitRequest() {
    const name = document.getElementById('requestName').value.trim();
    const contact = document.getElementById('requestContact').value.trim();
    const problem = document.getElementById('requestProblem').value.trim();

    if (!name || !problem || !contact) {
        showToast('Заполните все поля, включая контакт', 'error');
        return;
    }

    try {
        const data = await api('/request/', {
            method: 'POST',
            body: JSON.stringify({ name, contact, problem }),
        });

        if (data.success) {
            document.getElementById('requestForm').style.display = 'none';
            document.getElementById('requestSuccess').style.display = 'flex';
            document.getElementById('requestProblem').value = '';
        } else {
            showToast(data.error || 'Ошибка', 'error');
        }
    } catch (e) {
        showToast('Ошибка соединения', 'error');
    }
}

// ─── Start Chat Session ─────────────────────────
async function startSessionWith(specialistId) {
    if (!APP.user) {
        showToast('Сначала зарегистрируйтесь', 'error');
        return;
    }

    try {
        const data = await api('/session/create/', {
            method: 'POST',
            body: JSON.stringify({
                token: APP.user.token,
                specialist_id: specialistId,
            }),
        });

        if (data.success) {
            APP.session = data.session;
            saveSessionState();
            openChat();
            if (data.reconnected) {
                showToast('Вы переподключены к текущей сессии', 'success');
            }
        } else {
            showToast(data.error || 'Ошибка', 'error');
        }
    } catch (e) {
        showToast('Ошибка соединения', 'error');
    }
}

// ─── Chat ───────────────────────────────────────
function openChat() {
    showScreen('screenChat');

    // Set header info
    const name = APP.role === 'specialist'
        ? (APP.session.client_name || 'Клиент')
        : (APP.session.specialist_name || 'Специалист');

    document.getElementById('chatHeaderName').textContent = name;
    document.getElementById('chatAvatarLetter').textContent = name.charAt(0).toUpperCase();

    if (APP.session.specialist_photo && APP.role === 'client') {
        document.getElementById('chatAvatar').innerHTML = `<img src="${APP.session.specialist_photo}" alt="${escapeAttr(name)}">`;
    }

    // Clear messages
    document.getElementById('chatMessages').innerHTML = `
        <div class="system-message">
            <span class="material-symbols-rounded" style="font-size:16px;vertical-align:middle;">local_fire_department</span>
            Сессия начата! У вас 30 минут бесплатного общения
        </div>
    `;

    // Start timer
    startTimer();

    // Connect WebSocket
    connectWebSocket();

    // Load existing messages
    loadMessages();
}

function minimizeChat() {
    if (APP.role === 'specialist') {
        showScreen('screenDashboard');
        loadDashboard();
    } else {
        showScreen('screenMenu');
        updateActiveSessionBanner();
    }
}

function confirmEndSession() {
    document.getElementById('confirmEndSessionOverlay').classList.add('show');
}

function closeConfirmEndSession() {
    document.getElementById('confirmEndSessionOverlay').classList.remove('show');
}

function executeEndSession() {
    closeConfirmEndSession();
    stopSession();
}

async function stopSession() {
    try {
        const body = APP.role === 'client'
            ? { token: APP.user.token, session_id: APP.session.id }
            : { session_id: APP.session.id };

        await api('/session/stop/', {
            method: 'POST',
            body: JSON.stringify(body),
        });
    } catch (e) { /* ignore */ }

    cleanupChat();
    showToast('Сессия завершена. Спасибо за общение! 🙏', 'success');

    if (APP.role === 'specialist') {
        loadDashboard(); // Darhol yangilash
    }

    backToMenu();
}

function cleanupChat() {
    if (APP.ws) {
        APP.ws.close();
        APP.ws = null;
    }
    if (APP.timerInterval) {
        clearInterval(APP.timerInterval);
        APP.timerInterval = null;
    }
    APP.session = null;
    clearSessionState();
    document.getElementById('warningBanner').classList.remove('show');
}

function resumeChat() {
    if (APP.session) {
        openChat();
    }
}

// ─── Timer ──────────────────────────────────────
function getRemainingSeconds() {
    // expires_at dan haqiqiy qolgan soniyani hisoblash
    // Bu sahifa yangilanganida ham to'g'ri ishlaydi
    if (APP.session && APP.session.expires_at) {
        const expireTime = new Date(APP.session.expires_at).getTime();
        const now = Date.now();
        const diff = Math.floor((expireTime - now) / 1000);
        return diff > 0 ? diff : 0;
    }
    // Fallback: remaining_seconds ishlatamiz
    return APP.session ? (APP.session.remaining_seconds || 1800) : 1800;
}

function startTimer() {
    if (APP.timerInterval) clearInterval(APP.timerInterval);

    // expires_at dan haqiqiy qolgan vaqtni hisoblaymiz (yangilanishda ham to'g'ri)
    let remaining = getRemainingSeconds();

    const display = document.getElementById('timerDisplay');
    const timer = document.getElementById('chatTimer');
    const banner = document.getElementById('warningBanner');

    display.textContent = formatTime(remaining);

    APP.timerInterval = setInterval(() => {
        // Har soniyada expires_at dan qayta hisoblaymiz — drift bo'lmaydi
        remaining = getRemainingSeconds();

        if (remaining <= 0) {
            clearInterval(APP.timerInterval);
            display.textContent = '0:00';
            sessionExpired();
            return;
        }

        display.textContent = formatTime(remaining);

        // Warning at 5 minutes
        if (remaining <= 300) {
            timer.classList.add('warning');
            banner.classList.add('show');
        }

        // Critical at 1 minute
        if (remaining <= 60) {
            timer.style.animation = 'timerPulse 0.5s infinite';
        }
    }, 1000);
}

function sessionExpired() {
    document.getElementById('sessionOverlay').classList.add('show');
    cleanupChat();
}

// ─── WebSocket ──────────────────────────────────
function connectWebSocket() {
    if (APP.ws) APP.ws.close();

    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${location.host}/ws/chat/${APP.session.id}/`;

    APP.ws = new WebSocket(wsUrl);

    APP.ws.onopen = () => {
        console.log('WebSocket connected');
    };

    APP.ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleWSMessage(data);
    };

    APP.ws.onclose = () => {
        console.log('WebSocket disconnected');
        // Reconnect after 3 seconds if session is still active
        if (APP.session) {
            setTimeout(() => {
                if (APP.session) connectWebSocket();
            }, 3000);
        }
    };

    APP.ws.onerror = (err) => {
        console.error('WebSocket error:', err);
    };
}

function handleWSMessage(data) {
    switch (data.type) {
        case 'message':
            addMessageToChat(data.message);
            break;
        case 'typing':
            showTyping(data.sender);
            break;
        case 'messages_read':
            markRead(data.message_ids);
            break;
        case 'specialist_status':
            updateSpecialistStatus(data.is_online);
            break;
        case 'session_expired':
            sessionExpired();
            break;
        case 'session_warning':
            document.getElementById('warningBanner').classList.add('show');
            showToast(data.message || 'Сессия скоро завершится', 'warning');
            break;
        case 'session_info':
            if (data.data) {
                APP.session.remaining_seconds = data.data.remaining_seconds;
            }
            break;
    }
}

function sendWSMessage(data) {
    if (APP.ws && APP.ws.readyState === WebSocket.OPEN) {
        APP.ws.send(JSON.stringify(data));
    }
}

// ─── Chat Messages ──────────────────────────────
async function loadMessages() {
    if (!APP.session) return;
    try {
        const data = await api(`/session/${APP.session.id}/messages/`);
        if (data.messages) {
            data.messages.forEach(msg => addMessageToChat(msg, false));
        }
    } catch (e) { /* ignore */ }
}

function addMessageToChat(msg, animate = true) {
    const container = document.getElementById('chatMessages');
    const isSent = msg.sender === APP.role;
    const div = document.createElement('div');

    const msgType = msg.message_type || msg.type;

    if (msgType === 'sticker') {
        div.className = `message ${isSent ? 'sent' : 'received'} sticker-msg`;
        div.innerHTML = `<span style="font-size:64px;">${msg.content}</span>`;
    } else if (msgType === 'image') {
        const blurClass = isSent ? '' : 'blur';
        const downloadOverlay = isSent ? '' : `
                <div class="download-overlay">
                    <span class="material-symbols-rounded">download</span>
                </div>`;
        const clickAction = `onclick="handleImageClick(this, '${msg.file_url}')"`;

        div.className = `message ${isSent ? 'sent' : 'received'} message-media-only`;
        div.innerHTML = `
            <div class="image-wrapper ${blurClass}" ${clickAction}>
                <img src="${msg.file_url}" class="message-image" style="max-width:240px; border-radius: 8px;">
                ${downloadOverlay}
            </div>
            <div class="message-meta">
                <span>${msg.time || ''}</span>
                ${isSent ? `<span class="message-status ${msg.is_read ? 'read' : ''}"><span class="material-symbols-rounded">${msg.is_read ? 'done_all' : 'done'}</span></span>` : ''}
            </div>
        `;
    } else if (msgType === 'video_note') {
        div.className = `message ${isSent ? 'sent' : 'received'} message-media-only`;
        div.innerHTML = `
            <div class="video-note-wrapper" onclick="toggleVideoNote(this)">
                <div class="video-note-play-icon">
                    <span class="material-symbols-rounded" style="font-size: 32px;">play_arrow</span>
                </div>
                <video src="${msg.file_url}" loop playsinline class="video-note-player"></video>
            </div>
            <div class="message-meta">
                <span>${msg.time || ''}</span>
                ${isSent ? `<span class="message-status ${msg.is_read ? 'read' : ''}"><span class="material-symbols-rounded">${msg.is_read ? 'done_all' : 'done'}</span></span>` : ''}
            </div>
        `;
    } else if (msgType === 'video') {
        div.className = `message ${isSent ? 'sent' : 'received'} message-media-only`;
        div.innerHTML = `
            <div class="video-wrapper">
                <video src="${msg.file_url}" controls class="message-video" style="max-width:260px; border-radius: 8px;"></video>
            </div>
            <div class="message-meta">
                <span>${msg.time || ''}</span>
                ${isSent ? `<span class="message-status ${msg.is_read ? 'read' : ''}"><span class="material-symbols-rounded">${msg.is_read ? 'done_all' : 'done'}</span></span>` : ''}
            </div>
        `;
    } else if (msgType === 'voice') {
        div.className = `message ${isSent ? 'sent' : 'received'}`;
        div.innerHTML = `
            <div class="voice-message">
                <button class="voice-play-btn" onclick="playVoice(this, '${msg.file_url}')">
                    <span class="material-symbols-rounded">play_arrow</span>
                </button>
                <div class="voice-waveform" id="waveform_${msg.id}">
                    ${generateWaveformBars()}
                </div>
                <audio src="${msg.file_url}" onloadedmetadata="loadAudioDuration(this, 'dur_${msg.id}')" style="display:none;" preload="metadata"></audio>
                <span class="voice-duration" id="dur_${msg.id}">0:00</span>
            </div>
            <div class="message-meta">
                <span>${msg.time || ''}</span>
                ${isSent ? `<span class="message-status ${msg.is_read ? 'read' : ''}"><span class="material-symbols-rounded">${msg.is_read ? 'done_all' : 'done'}</span></span>` : ''}
            </div>
        `;
    } else if (msgType === 'file') {
        div.className = `message ${isSent ? 'sent' : 'received'}`;
        div.innerHTML = `
            <a href="${msg.file_url}" target="_blank" style="display:flex;align-items:center;gap:8px;color:inherit;text-decoration:none;">
                <span class="material-symbols-rounded" style="font-size:32px;opacity:0.7;">description</span>
                <span style="font-size:13px;">Прикреплённый файл</span>
            </a>
            <div class="message-meta">
                <span>${msg.time || ''}</span>
                ${isSent ? `<span class="message-status ${msg.is_read ? 'read' : ''}"><span class="material-symbols-rounded">${msg.is_read ? 'done_all' : 'done'}</span></span>` : ''}
            </div>
        `;
    } else {
        // Text message
        div.className = `message ${isSent ? 'sent' : 'received'}`;
        div.innerHTML = `
            <div class="message-content">${escapeHtml(msg.content || '')}</div>
            <div class="message-meta">
                <span>${msg.time || ''}</span>
                ${isSent ? `<span class="message-status ${msg.is_read ? 'read' : ''}"><span class="material-symbols-rounded">${msg.is_read ? 'done_all' : 'done'}</span></span>` : ''}
            </div>
        `;
    }

    div.dataset.msgId = msg.id;
    if (!animate) div.style.animation = 'none';
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;

    // Check if we are currently viewing the chat
    const isChatActive = document.getElementById('screenChat').classList.contains('active');

    // Mark as read if we are the receiver
    if (!isSent) {
        if (isChatActive && !document.hidden) {
            if (!msg.is_read) {
                sendWSMessage({
                    type: 'read',
                    message_ids: [msg.id],
                    reader: APP.role,
                });
            }
        } else {
            // Notify if chat is minimized
            showToast('Новое сообщение от собеседника', 'success');
            if (APP.role === 'client') {
                const banner = document.getElementById('activeSessionBanner');
                if (banner) {
                    banner.style.boxShadow = '0 0 15px rgba(var(--green-rgb), 0.5)';
                    setTimeout(() => banner.style.boxShadow = '', 3000);
                }
            }
        }
    }

    // Send browser notification if tab is not focused
    if (!isSent && (!isChatActive || document.hidden) && 'Notification' in window && Notification.permission === 'granted') {
        new Notification('Новое сообщение', {
            body: msg.content || 'Медиа сообщение',
        });
    }

    hideTyping();
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function escapeAttr(text) {
    if (!text) return '';
    return text.replace(/'/g, "\\'").replace(/"/g, '&quot;');
}

function generateWaveformBars() {
    let bars = '';
    for (let i = 0; i < 25; i++) {
        const h = Math.random() * 20 + 4;
        bars += `<div class="bar" style="height:${h}px;"></div>`;
    }
    return bars;
}

// ─── Send Message ───────────────────────────────
function sendMessage() {
    const input = document.getElementById('chatInput');
    const text = input.value.trim();
    if (!text) return;

    sendWSMessage({
        type: 'message',
        content: text,
        sender: APP.role,
        message_type: 'text',
    });

    input.value = '';
    input.style.height = 'auto';
    toggleSendButton();
    closeStickerPicker();
}

function onChatInput(el) {
    // Auto-resize textarea
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 120) + 'px';

    toggleSendButton();

    // Send typing indicator
    if (APP.typingTimeout) clearTimeout(APP.typingTimeout);
    sendWSMessage({ type: 'typing', sender: APP.role });
    APP.typingTimeout = setTimeout(() => { }, 2000);
}

function toggleSendButton() {
    const input = document.getElementById('chatInput');
    const sendBtn = document.getElementById('sendBtn');
    const voiceBtn = document.getElementById('voiceBtn');

    if (input.value.trim()) {
        sendBtn.classList.add('show');
        voiceBtn.style.display = 'none';
    } else {
        sendBtn.classList.remove('show');
        voiceBtn.style.display = 'flex';
    }
}

// Enter to send
document.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        const chatInput = document.getElementById('chatInput');
        if (document.activeElement === chatInput && chatInput.value.trim()) {
            e.preventDefault();
            sendMessage();
        }
    }
});

// ─── Typing Indicator ───────────────────────────
let typingHideTimeout = null;

function showTyping(sender) {
    if (sender === APP.role) return;
    const indicator = document.getElementById('typingIndicator');
    indicator.classList.add('show');
    document.getElementById('chatHeaderStatus').textContent = 'печатает...';

    if (typingHideTimeout) clearTimeout(typingHideTimeout);
    typingHideTimeout = setTimeout(hideTyping, 3000);
}

function hideTyping() {
    document.getElementById('typingIndicator').classList.remove('show');
    const statusText = APP.currentSpecialistIsOnline === false ? 'офлайн' : 'онлайн';
    document.getElementById('chatHeaderStatus').textContent = statusText;
}

function updateSpecialistStatus(isOnline) {
    APP.currentSpecialistIsOnline = isOnline;
    const statusEl = document.getElementById('chatHeaderStatus');
    if (statusEl && statusEl.textContent !== 'печатает...') {
        statusEl.textContent = isOnline ? 'онлайн' : 'офлайн';
    }
}

// ─── Read Status ────────────────────────────────
function markRead(messageIds) {
    if (!messageIds) return;
    messageIds.forEach(id => {
        const el = document.querySelector(`[data-msg-id="${id}"] .message-status`);
        if (el) {
            el.innerHTML = '<span class="material-symbols-rounded">done_all</span>';
            el.classList.add('read');
        }
    });
}

// ─── Voice Recording (FIXED) ────────────────────
async function startRecording() {
    if (APP.recording.active) return;

    document.querySelector('.chat-input-area').classList.add('is-recording');

    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        APP.recording.stream = stream;
        APP.recording.chunks = [];
        APP.recording.readyToSend = true; // Will send on stop

        // Determine mime type (Mac-friendly priority)
        let mimeType = 'audio/webm';
        if (typeof MediaRecorder.isTypeSupported === 'function') {
            if (MediaRecorder.isTypeSupported('audio/mp4')) {
                mimeType = 'audio/mp4';
            } else if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) {
                mimeType = 'audio/webm;codecs=opus';
            } else if (MediaRecorder.isTypeSupported('audio/ogg;codecs=opus')) {
                mimeType = 'audio/ogg;codecs=opus';
            }
        }

        const mediaRecorder = new MediaRecorder(stream, {
            mimeType,
            audioBitsPerSecond: 128000
        });

        mediaRecorder.ondataavailable = (e) => {
            if (e.data && e.data.size > 0) {
                APP.recording.chunks.push(e.data);
                console.log('Voice chunk added:', e.data.size);
            }
        };

        mediaRecorder.onstop = async () => {
            console.log('MediaRecorder stopped. Total chunks:', APP.recording.chunks.length);

            // Allow a small delay for the final chunk to be processed if needed
            if (APP.recording.chunks.length === 0) {
                console.warn('No chunks captured!');
            }

            // Only upload if readyToSend is true (not cancelled)
            if (APP.recording.readyToSend && APP.recording.chunks.length > 0) {
                const blob = new Blob(APP.recording.chunks, { type: mimeType });
                console.log('Created blob size:', blob.size, 'type:', mimeType);
                if (blob.size > 100) { // More than just header
                    await uploadVoice(blob, mimeType);
                } else {
                    console.error('Blob too small, likely failed recording');
                }
            }

            // Stop all tracks
            if (stream) {
                stream.getTracks().forEach(t => t.stop());
            }

            // Reset
            APP.recording.chunks = [];
            APP.recording.readyToSend = false;
        };

        mediaRecorder.start(250); // collect data every 250ms
        APP.recording.mediaRecorder = mediaRecorder;
        APP.recording.active = true;
        APP.recording.startTime = Date.now();

        // Show recording UI
        document.getElementById('inputWrapper').style.display = 'none';
        document.querySelector('.chat-input-right-group').style.display = 'none';
        document.getElementById('moodBtn').style.display = 'none';
        document.getElementById('recordingUI').classList.add('show');
        document.getElementById('voiceBtn').style.display = 'flex'; // Ensure voiceBtn stays visible for stopping
        document.querySelector('.chat-input-area').appendChild(document.getElementById('voiceBtn')); // Temporarily move out of group if needed or just show recording UI over it
        document.getElementById('voiceBtn').classList.add('recording');
        document.getElementById('voiceBtn').querySelector('.material-symbols-rounded').textContent = 'stop';

        // Timer
        APP.recording.timerInterval = setInterval(updateRecordingTime, 100);

        // Waveform animation
        animateRecordingWaveform();

    } catch (e) {
        console.error('Microphone error:', e);
        showToast('Нет доступа к микрофону. Разрешите доступ в настройках браузера.', 'error');
    }
}

function stopRecording() {
    if (!APP.recording.active) return;
    APP.recording.active = false;
    APP.recording.readyToSend = true; // IMPORTANT: Mark as ready to send BEFORE stopping

    if (APP.recording.mediaRecorder && APP.recording.mediaRecorder.state !== 'inactive') {
        // Request any remaining data before stopping
        APP.recording.mediaRecorder.requestData();
        setTimeout(() => {
            if (APP.recording.mediaRecorder.state !== 'inactive') {
                APP.recording.mediaRecorder.stop();
            }
        }, 50);
    }

    clearInterval(APP.recording.timerInterval);
    resetRecordingUI();
}

function cancelRecording() {
    APP.recording.readyToSend = false; // Mark as NOT ready to send
    APP.recording.active = false;

    if (APP.recording.mediaRecorder && APP.recording.mediaRecorder.state === 'recording') {
        APP.recording.mediaRecorder.stop();
    }
    if (APP.recording.stream) {
        APP.recording.stream.getTracks().forEach(t => t.stop());
    }

    APP.recording.chunks = [];
    clearInterval(APP.recording.timerInterval);
    resetRecordingUI();
}

function resetRecordingUI() {
    const rightGroup = document.querySelector('.chat-input-right-group');
    const voiceBtn = document.getElementById('voiceBtn');

    document.getElementById('inputWrapper').style.display = 'flex';
    document.getElementById('moodBtn').style.display = 'flex';
    rightGroup.style.display = 'flex';

    // Move voiceBtn back to rightGroup if it was moved
    if (voiceBtn.parentElement !== rightGroup) {
        const sendBtn = document.getElementById('sendBtn');
        rightGroup.insertBefore(voiceBtn, sendBtn);
    }

    document.getElementById('recordingUI').classList.remove('show');
    voiceBtn.classList.remove('recording');
    document.querySelector('.chat-input-area').classList.remove('is-recording');

    const icon = voiceBtn.querySelector('.material-symbols-rounded');
    if (icon) icon.textContent = 'mic';

    document.getElementById('recordingTime').textContent = '0:00';
}

function updateRecordingTime() {
    const elapsed = Math.floor((Date.now() - APP.recording.startTime) / 1000);
    document.getElementById('recordingTime').textContent = formatTime(elapsed);
}

function animateRecordingWaveform() {
    const container = document.getElementById('recordingWaveform');
    container.innerHTML = '';
    for (let i = 0; i < 30; i++) {
        const bar = document.createElement('div');
        bar.className = 'bar';
        bar.style.height = '4px';
        container.appendChild(bar);
    }

    function animate() {
        if (!APP.recording.active) return;
        container.querySelectorAll('.bar').forEach(bar => {
            const h = Math.random() * 20 + 2;
            bar.style.height = h + 'px';
        });
        requestAnimationFrame(() => setTimeout(animate, 100));
    }
    animate();
}

async function uploadVoice(blob, mimeType) {
    if (!APP.session) return;

    const ext = mimeType.includes('mp4') ? 'mp4' : mimeType.includes('ogg') ? 'ogg' : 'webm';
    const formData = new FormData();
    formData.append('file', blob, `voice.${ext}`);
    formData.append('type', 'voice');
    formData.append('session_id', APP.session.id);

    if (APP.role === 'client' && APP.user) {
        formData.append('token', APP.user.token);
    }

    try {
        const res = await fetch(API_BASE + '/upload/', {
            method: 'POST',
            body: formData,
        });
        const data = await res.json();

        if (data.success) {
            // Notify via WebSocket
            sendWSMessage({
                type: 'file_sent',
                message: {
                    id: data.message.id,
                    content: '',
                    sender: data.message.sender || APP.role,
                    message_type: 'voice',
                    type: 'voice',
                    file_url: data.message.file_url,
                    time: data.message.time,
                    is_read: false,
                }
            });
        } else {
            showToast(data.error || 'Ошибка отправки', 'error');
        }
    } catch (e) {
        console.error('Voice upload error:', e);
        showToast('Ошибка отправки голосового сообщения', 'error');
    }
}

// ─── Voice Playback ─────────────────────────────
function pauseAllMedia() {
    // Pause all audio elements
    if (APP.voiceAudio) {
        APP.voiceAudio.pause();
    }
    // Pause all video elements
    document.querySelectorAll('video').forEach(video => {
        if (!video.paused) {
            video.pause();
        }
    });

    // Reset all video note wrappers
    document.querySelectorAll('.video-note-wrapper').forEach(wrapper => {
        wrapper.classList.remove('playing');
    });

    // Reset all play icons
    document.querySelectorAll('.voice-play-btn .material-symbols-rounded').forEach(icon => {
        icon.textContent = 'play_arrow';
    });
}

function playVoice(btn, url) {
    const iconEl = btn.querySelector('.material-symbols-rounded');
    const isCurrentlyPlaying = iconEl.textContent === 'pause';

    // Pause everything else first
    pauseAllMedia();

    if (isCurrentlyPlaying) {
        // Since pauseAllMedia already paused everything and reset icons, 
        // we just return here
        return;
    }


    // Yaratilgan yangi new Audio(url) o'rniga HTMLdagi audio tegini ishlatamiz
    // bu video/webm (MediaRecorder) xatolarini chetlab o'tadi
    const msgElement = btn.closest('.voice-message') || btn.closest('.message-content');
    let audio = msgElement.querySelector('audio');

    // Agar xatolik bo'lib audio tegi HTML da topilmasa fall-back qaytaramiz
    if (!audio) {
        audio = new Audio(url);
    }

    APP.voiceAudio = audio;
    const durationEl = msgElement.querySelector('.voice-duration');
    const bars = msgElement.querySelectorAll('.bar');

    iconEl.textContent = 'pause';

    audio.play().catch(e => {
        console.error('Audio play error:', e);
        showToast('Не удалось воспроизвести: ' + e.message, 'error');
        iconEl.textContent = 'play_arrow';
    });

    audio.ontimeupdate = () => {
        if (durationEl) {
            durationEl.textContent = formatTime(Math.floor(audio.currentTime));
        }
        if (bars.length && audio.duration) {
            const progress = audio.currentTime / audio.duration;
            bars.forEach((bar, i) => {
                if (i / bars.length <= progress) {
                    bar.classList.add('active');
                } else {
                    bar.classList.remove('active');
                }
            });
        }
    };

    audio.onended = () => {
        iconEl.textContent = 'play_arrow';
        bars.forEach(bar => bar.classList.remove('active'));
        APP.voiceAudio = null;
    };
}

// Global media listener to ensure mutual exclusion
document.addEventListener('play', (e) => {
    if (e.target.tagName === 'VIDEO') {
        // A video started playing, pause audio
        if (APP.voiceAudio) {
            APP.voiceAudio.pause();
            // Reset icons
            document.querySelectorAll('.voice-play-btn .material-symbols-rounded').forEach(icon => {
                icon.textContent = 'play_arrow';
            });
        }

        // Pause other videos
        document.querySelectorAll('video').forEach(video => {
            if (video !== e.target && !video.paused) {
                video.pause();
            }
        });
    }
}, true);

function toggleVideoNote(wrapper) {
    const video = wrapper.querySelector('video');
    const isPlaying = !video.paused;

    if (isPlaying) {
        video.pause();
        wrapper.classList.remove('playing');
    } else {
        // Stop everything else first
        pauseAllMedia();

        video.play().then(() => {
            wrapper.classList.add('playing');
        }).catch(err => {
            console.error('Video play error:', err);
        });
    }
}

// ─── File Upload ────────────────────────────────
function triggerFileUpload(type) {
    APP.fileUploadType = type;
    const input = document.getElementById('fileInput');
    input.accept = type === 'image' ? 'image/*' : '*/*';
    input.click();
}

async function handleFileUpload(event) {
    const file = event.target.files[0];
    if (!file) return;

    if (file.size > 20 * 1024 * 1024) {
        showToast('Файл слишком большой (макс. 20 МБ)', 'error');
        return;
    }

    if (!APP.session) {
        showToast('Нет активной сессии', 'error');
        return;
    }

    const formData = new FormData();
    formData.append('file', file);
    formData.append('type', APP.fileUploadType);
    formData.append('session_id', APP.session.id);

    if (APP.role === 'client' && APP.user) {
        formData.append('token', APP.user.token);
    }

    try {
        const res = await fetch(API_BASE + '/upload/', {
            method: 'POST',
            body: formData,
        });
        const data = await res.json();

        if (data.success) {
            sendWSMessage({
                type: 'file_sent',
                message: {
                    id: data.message.id,
                    content: '',
                    sender: data.message.sender || APP.role,
                    message_type: data.message.type,
                    type: data.message.type,
                    file_url: data.message.file_url,
                    time: data.message.time,
                    is_read: false,
                }
            });
        } else {
            showToast(data.error || 'Ошибка загрузки', 'error');
        }
    } catch (e) {
        showToast('Ошибка загрузки файла', 'error');
    }

    event.target.value = '';
}

// ─── Image Preview ──────────────────────────────
function openPreview(url) {
    document.getElementById('previewImage').src = url;
    document.getElementById('filePreview').classList.add('show');
}

function closePreview() {
    document.getElementById('filePreview').classList.remove('show');
}

// ─── Stickers ───────────────────────────────────
const STICKER_PACKS = {
    'Эмоции': ['😀', '😊', '😄', '🥰', '😍', '🤗', '😢', '😭', '😡', '🤬', '😱', '🥺', '😴', '🤒', '🤕', '🥳'],
    'Жесты': ['👍', '👎', '👏', '🙌', '🤝', '💪', '🙏', '✌️', '🤞', '🫶', '❤️', '💔', '💯', '🔥', '⭐', '✨'],
    'Настроение': ['☀️', '🌈', '🌸', '🎉', '🎊', '🎯', '💡', '🧠', '🦋', '🌺', '🍀', '🌟', '💫', '🌙', '☁️', '🌊'],
    'Реакции': ['✅', '❌', '⚠️', '❓', '💬', '👀', '🎵', '📌', '🔔', '⏰', '📎', '🔗', '🏆', '🎁', '💎', '🪄'],
};

function initStickerPicker() {
    const picker = document.getElementById('stickerPicker');
    let html = '';
    for (const [category, stickers] of Object.entries(STICKER_PACKS)) {
        html += `<div class="sticker-category-title">${category}</div>`;
        html += '<div class="sticker-grid">';
        stickers.forEach(s => {
            html += `<div class="sticker-item" onclick="sendSticker('${s}')">${s}</div>`;
        });
        html += '</div>';
    }
    picker.innerHTML = html;
}

function toggleStickerPicker() {
    const picker = document.getElementById('stickerPicker');
    APP.stickerOpen = !APP.stickerOpen;
    picker.classList.toggle('show', APP.stickerOpen);
}

function closeStickerPicker() {
    APP.stickerOpen = false;
    const picker = document.getElementById('stickerPicker');
    if (picker) picker.classList.remove('show');
}

function sendSticker(emoji) {
    const input = document.getElementById('chatInput');

    // Вставить эмодзи в позицию курсора
    const startPos = input.selectionStart || 0;
    const endPos = input.selectionEnd || 0;
    const text = input.value;

    input.value = text.substring(0, startPos) + emoji + text.substring(endPos, text.length);

    // Переместить курсор после эмодзи
    const focusPos = startPos + emoji.length;
    setTimeout(() => {
        input.focus();
        if (input.setSelectionRange) {
            input.setSelectionRange(focusPos, focusPos);
        }
    }, 0);

    onChatInput(input);
}

// ─── Specialist Dashboard ───────────────────────
async function loadDashboard() {
    const container = document.getElementById('dashboardSessions');

    try {
        const data = await api('/session/active/');
        if (data.sessions && data.sessions.length > 0) {
            container.innerHTML = data.sessions.map(s => `
                <div class="session-card glass-card" onclick="joinSessionAsSpecialist(${s.id}, '${escapeAttr(s.client_name)}', ${s.remaining_seconds})">
                    <div class="session-card-avatar">${escapeHtml(s.client_name.charAt(0).toUpperCase())}</div>
                    <div class="session-card-info">
                        <div class="session-card-name">${escapeHtml(s.client_name)}</div>
                        <div class="session-card-time">
                            <span class="material-symbols-rounded" style="font-size:14px;">timer</span>
                            Осталось: ${formatTime(s.remaining_seconds)}
                        </div>
                    </div>
                    <span class="material-symbols-rounded" style="color:var(--green);">arrow_forward</span>
                </div>
            `).join('');
        } else {
            container.innerHTML = `
                <div class="no-sessions">
                    <span class="material-symbols-rounded" style="font-size:64px; opacity:0.15;">forum</span>
                    <p>Нет активных сессий</p>
                    <p class="text-muted mt-8">Ожидайте, когда клиент начнёт общение</p>
                </div>
            `;
        }
    } catch (e) {
        container.innerHTML = '<p class="text-center text-muted">Ошибка загрузки</p>';
    }

    // Statistika va avatar ham yangilansin
    if (APP.role === 'specialist') {
        loadSpecialistStats();
        updateDashboardAvatar();
    }
}

function joinSessionAsSpecialist(sessionId, clientName, remainingSeconds) {
    APP.session = {
        id: sessionId,
        client_name: clientName,
        remaining_seconds: remainingSeconds,
    };
    saveSessionState();
    openChat();
}

// ─── Specialist Notifications ───────────────────
function connectSpecialistNotifications() {
    if (!APP.specialist) return;

    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${location.host}/ws/notifications/${APP.specialist.id}/`;

    APP.wsNotify = new WebSocket(wsUrl);

    APP.wsNotify.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === 'new_session') {
            showToast(`Новая сессия от ${data.session.client_name}!`, 'success');
            loadDashboard();

            // Browser notification
            if ('Notification' in window && Notification.permission === 'granted') {
                new Notification('Новая сессия!', {
                    body: `Клиент ${data.session.client_name} начал общение`,
                });
            }
        } else if (data.type === 'session_ended') {
            loadDashboard();
        }
    };

    APP.wsNotify.onclose = () => {
        if (APP.specialist) {
            setTimeout(connectSpecialistNotifications, 5000);
        }
    };

    // Refresh dashboard periodically
    setInterval(() => {
        if (APP.role === 'specialist' && document.getElementById('screenDashboard').classList.contains('active')) {
            loadDashboard();
        }
    }, 15000);
}

// ─── Voice Button Event ─────────────────────────
function setupVoiceButton() {
    const voiceBtn = document.getElementById('voiceBtn');
    if (!voiceBtn) return;

    // Use click instead of mousedown/up for reliability
    voiceBtn.addEventListener('click', (e) => {
        e.preventDefault();
        if (APP.recording.active) {
            stopRecording();
        } else {
            startRecording();
        }
    });
}

// ─── Init ───────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
    // ─── Asset Preloading & Preloader ────────────────
    const preloadAssets = async () => {
        const images = [
            '/staticfiles/webtgbot/img/wallpaperflare.com_wallpaper.jpg',
            '/staticfiles/webtgbot/img/white-bacgroud.jpg',
            '/staticfiles/webtgbot/img/logo.jpg'
        ];

        // Preload Images
        const imgPromises = images.map(src => {
            return new Promise((resolve) => {
                const img = new Image();
                img.onload = resolve;
                img.onerror = resolve; // Continue even if one fails
                img.src = src;
            });
        });

        // Preload Fonts
        const fontPromise = document.fonts ? document.fonts.ready : Promise.resolve();

        // Wait for all critical assets (max 5s timeout)
        await Promise.race([
            Promise.all([...imgPromises, fontPromise]),
            new Promise(resolve => setTimeout(resolve, 5000))
        ]);

        // Smoothly hide preloader
        const preloader = document.getElementById('preloader');
        if (preloader) {
            preloader.classList.add('fade-out');
            document.body.classList.remove('loading');
            setTimeout(() => preloader.style.display = 'none', 600);
        }
    };

    // Run preloading
    preloadAssets();

    initStickerPicker();
    setupVoiceButton();

    // Check saved session
    const savedUser = localStorage.getItem('fenix_user');
    const savedSpecialist = localStorage.getItem('fenix_specialist');
    const savedSession = localStorage.getItem('fenix_session');

    if (savedSpecialist) {
        try {
            APP.specialist = JSON.parse(savedSpecialist);
            APP.role = 'specialist';
            document.getElementById('specName').textContent = APP.specialist.name;
            showScreen('screenDashboard');
            loadDashboard();
            loadSpecialistStats();
            updateDashboardAvatar();
            connectSpecialistNotifications();

            // Restore session if exists
            if (savedSession) {
                try {
                    APP.session = JSON.parse(savedSession);
                    APP.role = 'specialist';
                } catch (e) { clearSessionState(); }
            }
        } catch (e) {
            localStorage.removeItem('fenix_specialist');
        }
    } else if (savedUser) {
        try {
            APP.user = JSON.parse(savedUser);
            APP.role = 'client';
            document.getElementById('userName').textContent = APP.user.name;
            document.getElementById('requestName').value = APP.user.name;

            // Restore active session
            if (savedSession) {
                try {
                    APP.session = JSON.parse(savedSession);
                    showScreen('screenMenu');
                    updateActiveSessionBanner();
                    // Auto-reconnect to chat
                    openChat();
                } catch (e) {
                    clearSessionState();
                    showScreen('screenMenu');
                }
            } else {
                showScreen('screenMenu');
                // Check if backend has active session anyway
                api('/session/client/active/', {
                    method: 'POST',
                    body: JSON.stringify({ token: APP.user.token })
                }).then(data => {
                    if (data.session) {
                        APP.session = data.session;
                        saveSessionState();
                        updateActiveSessionBanner();
                    }
                }).catch(() => { });
            }
        } catch (e) {
            localStorage.removeItem('fenix_user');
        }
    }

    // Request notification permission
    if ('Notification' in window && Notification.permission === 'default') {
        // Will ask on first interaction
    }
});

// ─── Visibility Change (for notifications) ──────
document.addEventListener('visibilitychange', () => {
    if (!document.hidden && APP.session) {
        // Mark visible messages as read
        const unread = document.querySelectorAll('.message.received .message-status:not(.read)');
        const ids = [];
        unread.forEach(el => {
            const msgDiv = el.closest('.message');
            if (msgDiv && msgDiv.dataset.msgId) {
                ids.push(parseInt(msgDiv.dataset.msgId));
            }
        });
        if (ids.length > 0) {
            sendWSMessage({ type: 'read', message_ids: ids, reader: APP.role });
        }
    }
});

function handleImageClick(el, url) {
    if (el.classList.contains('blur')) {
        el.classList.remove('blur');
    } else {
        openPreview(url);
    }
}

// WebM Duration bug workaround for Chromium
function loadAudioDuration(audioEl, durationId) {
    if (audioEl.duration && audioEl.duration !== Infinity && !isNaN(audioEl.duration)) {
        document.getElementById(durationId).textContent = formatTime(Math.floor(audioEl.duration));
    } else {
        audioEl.currentTime = 1e10; // Seek to trigger read to EOF
        audioEl.ontimeupdate = function () {
            this.ontimeupdate = null;
            if (this.duration && this.duration !== Infinity && !isNaN(this.duration)) {
                const el = document.getElementById(durationId);
                if (el) el.textContent = formatTime(Math.floor(this.duration));
            }
            this.currentTime = 0;
        };
    }
}

// ─── Theme & Menu Logic ────────────────────────
function toggleChatMenu(e) {
    if (e) e.stopPropagation();
    const menu = document.getElementById('chatMoreMenu');
    if (menu) menu.classList.toggle('show');
}

function toggleGlobalMenu(e) {
    if (e) e.stopPropagation();
    const menu = document.getElementById('globalMenu');
    if (menu) menu.classList.toggle('show');
}

function toggleTheme() {
    const isLight = document.body.classList.toggle('light-mode');
    localStorage.setItem('theme', isLight ? 'light' : 'dark');
    updateThemeUI(isLight);

    // Close menus after selection
    const menus = document.querySelectorAll('.dropdown-menu');
    menus.forEach(m => m.classList.remove('show'));
}

function updateThemeUI(isLight) {
    const icons = [document.getElementById('themeIcon'), document.getElementById('themeIconGlobal')];
    const texts = [document.getElementById('themeText'), document.getElementById('themeTextGlobal')];

    icons.forEach(icon => {
        if (icon) icon.textContent = isLight ? 'light_mode' : 'dark_mode';
    });

    texts.forEach(text => {
        if (text) {
            // Agar hozir yorug' bo'lsa, tugma "Tungi rejim"ni taklif qilishi kerak
            text.textContent = isLight ? 'Ночной режим' : 'Дневной режим';
        }
    });
}

// Close dropdown when clicking outside
document.addEventListener('click', (e) => {
    const menus = document.querySelectorAll('.dropdown-menu');
    const isActionBtn = e.target.closest('.header-action-btn');
    if (!isActionBtn) {
        menus.forEach(m => m.classList.remove('show'));
    }
});

// Initialize theme on load
(function initTheme() {
    const savedTheme = localStorage.getItem('theme');
    const isLight = savedTheme === 'light';
    if (isLight) {
        document.body.classList.add('light-mode');
    }
    // Update UI after a short delay to ensure elements exist
    setTimeout(() => updateThemeUI(isLight), 100);
})();


// ═══════════════════════════════════════════════════
// SPECIALIST PROFILE MANAGEMENT
// ═══════════════════════════════════════════════════

// Profil ma'lumotlarini yuklash
async function loadProfile() {
    try {
        const data = await api('/specialist/profile/');
        if (data.profile) {
            const p = data.profile;
            APP._profileData = p;

            // Profile screen
            document.getElementById('profileName').textContent = p.name || '—';
            document.getElementById('profileSpec').textContent = p.specialization || '';
            document.getElementById('profileDesc').textContent = p.description || 'Не указано';
            document.getElementById('profilePrice').textContent = `${p.price} руб.`;
            document.getElementById('profileRating').textContent = p.rating;
            document.getElementById('profileUsername').textContent = p.username || '—';

            // Online status
            const dot = document.getElementById('profileOnlineDot');
            const txt = document.getElementById('profileOnlineText');
            if (p.is_online) {
                dot.style.background = 'var(--green)';
                txt.textContent = 'Онлайн';
            } else {
                dot.style.background = 'var(--text-muted)';
                txt.textContent = 'Офлайн';
            }

            // Profile photo
            const photoEl = document.getElementById('profilePhoto');
            const letterEl = document.getElementById('profilePhotoLetter');
            if (p.photo) {
                photoEl.innerHTML = `<img src="${p.photo}" alt="${escapeAttr(p.name)}" style="width:100%;height:100%;object-fit:cover;border-radius:50%;">`;
            } else {
                photoEl.innerHTML = `<span style="font-size:48px;">${escapeHtml((p.name || 'S').charAt(0).toUpperCase())}</span>`;
            }
        }
    } catch (e) {
        showToast('Ошибка загрузки профиля', 'error');
    }
}

// Profil ekranini ochish
function openProfile() {
    showScreen('screenProfile');
    loadProfile();
}

// Profil tahrirlash ekranini ochish
function openProfileEdit() {
    showScreen('screenProfileEdit');
    // Agar profileData bor bo'lsa formaga to'ldir
    const p = APP._profileData;
    if (p) {
        document.getElementById('editName').value = p.name || '';
        document.getElementById('editDesc').value = p.description || '';
        document.getElementById('editPrice').value = p.price || 0;

        // Foto preview
        const editPreview = document.getElementById('editPhotoPreview');
        if (p.photo) {
            editPreview.innerHTML = `<img src="${p.photo}" alt="photo" style="width:100%;height:100%;object-fit:cover;border-radius:50%;">`;
        } else {
            editPreview.innerHTML = `<span id="editPhotoLetter" style="font-size:40px;">${(p.name || 'S').charAt(0).toUpperCase()}</span>`;
        }
    }
    // Parol maydonlarini tozalash
    document.getElementById('editOldPassword').value = '';
    document.getElementById('editNewPassword').value = '';
    document.getElementById('editConfirmPassword').value = '';
}

// Profil ma'lumotlarini saqlash (ism, bio, narx)
async function saveProfileInfo() {
    const name = document.getElementById('editName').value.trim();
    const description = document.getElementById('editDesc').value.trim();
    const price = document.getElementById('editPrice').value;

    if (!name) {
        showToast('Введите имя', 'error');
        return;
    }

    const btn = document.getElementById('saveInfoBtn');
    btn.disabled = true;
    btn.innerHTML = '<div class="spinner" style="width:20px;height:20px;border-width:2px;margin:0 auto;"></div>';

    try {
        const data = await api('/specialist/profile/update/', {
            method: 'POST',
            body: JSON.stringify({ name, description, price: parseFloat(price) || 0 }),
        });

        if (data.success) {
            // APP.specialist nomini yangilaymiz
            if (APP.specialist) {
                APP.specialist.name = data.profile.name;
                localStorage.setItem('fenix_specialist', JSON.stringify(APP.specialist));
            }
            document.getElementById('specName').textContent = data.profile.name;
            APP._profileData = { ...APP._profileData, ...data.profile };
            updateDashboardAvatar();
            showToast('Профиль сохранён!', 'success');
        } else {
            showToast(data.error || 'Ошибка сохранения', 'error');
        }
    } catch (e) {
        showToast('Ошибка соединения', 'error');
    }

    btn.disabled = false;
    btn.innerHTML = '<span class="material-symbols-rounded">save</span> Сохранить данные';
}

// Profil rasmi yuklash (aynan botdagi foto yuborish kabi)
async function uploadProfilePhoto(event) {
    const file = event.target.files[0];
    if (!file) return;

    const allowed = ['image/jpeg', 'image/png', 'image/webp', 'image/gif'];
    if (!allowed.includes(file.type)) {
        showToast('Формат танланмади. JPG, PNG или WebP используйте', 'error');
        return;
    }
    if (file.size > 5 * 1024 * 1024) {
        showToast('Файл слишком большой (макс. 5 МБ)', 'error');
        return;
    }

    // Preview ko'rsatish
    const reader = new FileReader();
    reader.onload = (e) => {
        const editPreview = document.getElementById('editPhotoPreview');
        editPreview.innerHTML = `<img src="${e.target.result}" alt="preview" style="width:100%;height:100%;object-fit:cover;border-radius:50%;">`;
    };
    reader.readAsDataURL(file);

    showToast('Фото загружается...', '');

    const formData = new FormData();
    formData.append('photo', file);

    try {
        const res = await fetch(API_BASE + '/specialist/photo/', {
            method: 'POST',
            body: formData,
        });
        const data = await res.json();

        if (data.success) {
            if (APP._profileData) APP._profileData.photo = data.photo_url;
            if (APP.specialist) {
                APP.specialist.photo = data.photo_url;
                localStorage.setItem('fenix_specialist', JSON.stringify(APP.specialist));
            }
            updateDashboardAvatar();
            showToast('Фото успешно обновлено!', 'success');
        } else {
            showToast(data.error || 'Ошибка загрузки', 'error');
        }
    } catch (e) {
        showToast('Ошибка загрузки фото', 'error');
    }

    event.target.value = '';
}

// Parolni o'zgartirish
async function changePassword() {
    const oldPwd = document.getElementById('editOldPassword').value;
    const newPwd = document.getElementById('editNewPassword').value;
    const confirmPwd = document.getElementById('editConfirmPassword').value;

    if (!oldPwd || !newPwd || !confirmPwd) {
        showToast('Заполните все поля', 'error');
        return;
    }
    if (newPwd !== confirmPwd) {
        showToast('Новые пароли не совпадают', 'error');
        return;
    }
    if (newPwd.length < 6) {
        showToast('Пароль должен быть не менее 6 символов', 'error');
        return;
    }

    const btn = document.getElementById('savePasswordBtn');
    btn.disabled = true;
    btn.innerHTML = '<div class="spinner" style="width:20px;height:20px;border-width:2px;margin:0 auto;"></div>';

    try {
        const data = await api('/specialist/password/', {
            method: 'POST',
            body: JSON.stringify({
                old_password: oldPwd,
                new_password: newPwd,
                confirm_password: confirmPwd,
            }),
        });

        if (data.success) {
            showToast('Пароль успешно изменён!', 'success');
            document.getElementById('editOldPassword').value = '';
            document.getElementById('editNewPassword').value = '';
            document.getElementById('editConfirmPassword').value = '';
        } else {
            showToast(data.error || 'Ошибка', 'error');
        }
    } catch (e) {
        showToast('Ошибка соединения', 'error');
    }

    btn.disabled = false;
    btn.innerHTML = '<span class="material-symbols-rounded">key</span> Сменить пароль';
}

// Statistikani yuklash
async function loadSpecialistStats() {
    try {
        const data = await api('/specialist/stats/');
        if (data.stats) {
            const s = data.stats;
            const totalEl = document.getElementById('statTotal');
            const completedEl = document.getElementById('statCompleted');
            const ratingEl = document.getElementById('statRating');
            if (totalEl) totalEl.textContent = s.total_sessions;
            if (completedEl) completedEl.textContent = s.completed_sessions;
            if (ratingEl) ratingEl.textContent = s.rating > 0 ? `★ ${s.rating}` : '—';
        }
    } catch (e) { /* ignore */ }
}

// Online/Offline holat almashtirish (aynan bot: specialist online bo'lsa ko'rinadi)
async function toggleOnlineStatus() {
    try {
        const data = await api('/specialist/online/', {
            method: 'POST',
            body: JSON.stringify({}),
        });

        if (data.success) {
            const btn = document.getElementById('onlineToggleBtn');
            if (data.is_online) {
                btn.classList.add('is-online');
                btn.title = 'Вы онлайн — нажмите чтобы стать офлайн';
                showToast('Вы теперь онлайн 🟢', 'success');
            } else {
                btn.classList.remove('is-online');
                btn.title = 'Вы офлайн — нажмите чтобы стать онлайн';
                showToast('Вы перешли в офлайн', '');
            }
            if (APP._profileData) APP._profileData.is_online = data.is_online;
        } else {
            showToast(data.error || 'Ошибка', 'error');
        }
    } catch (e) {
        showToast('Ошибка соединения', 'error');
    }
}

// Dashboard avatar va nomini yangilash
function updateDashboardAvatar() {
    const specialist = APP.specialist;
    const profileData = APP._profileData;
    const photo = (profileData && profileData.photo) || (specialist && specialist.photo);
    const name = (profileData && profileData.name) || (specialist && specialist.name) || 'S';
    const letter = name.charAt(0).toUpperCase();

    const avatarEl = document.getElementById('dashAvatarImg');
    if (!avatarEl) return;

    if (photo) {
        avatarEl.innerHTML = `<img src="${photo}" alt="${escapeAttr(name)}" style="width:100%;height:100%;object-fit:cover;border-radius:50%;">`;
    } else {
        avatarEl.innerHTML = `<span id="dashAvatarLetter" style="font-size:22px; font-weight:700; color:white;">${letter}</span>`;
    }

    // Online toggle bo'yicha holat
    const onlineBtn = document.getElementById('onlineToggleBtn');
    const isOnline = profileData && profileData.is_online;
    if (onlineBtn) {
        if (isOnline) {
            onlineBtn.classList.add('is-online');
            onlineBtn.title = 'Вы онлайн';
        } else {
            onlineBtn.classList.remove('is-online');
            onlineBtn.title = 'Вы офлайн';
        }
    }
}
