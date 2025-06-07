document.addEventListener("DOMContentLoaded", async function () {

    const updateAuthButtons = () => {
        const authButtons = document.getElementById('auth-buttons');
        const username = sessionStorage.getItem('username');
        
        if (username) {
            authButtons.innerHTML = `
                <span class="username-display">Вы вошли: ${username}</span>
                <button onclick="logout()" class="logout-btn">Выход</button>
            `;
        } else {
            authButtons.innerHTML = `
                <button onclick="window.location.href='/register'" class="auth-btn">Регистрация 📝</button>
                <button onclick="window.location.href='/login'" class="auth-btn">Вход 🔑</button>
            `;
        }
    };

    updateAuthButtons();
    // Глобальные функции выбора чатов
    window.selectGroup = function(groupId, groupName, element) {
        currentGroup = groupId;
        currentPrivateChat = null;
        sessionStorage.setItem('currentChat', JSON.stringify({
            type: groupId ? 'group' : 'general',
            id: groupId,
            name: groupName
        }));
        UI.currentGroupName.textContent = groupName || 'Общий чат';
        UI.chatBox.innerHTML = '';
        lastTimestamp = 0;
        loadGroups();
        loadMessages();
    };

    window.selectPrivateChat = async function(username) {
        UI.membersSidebar.classList.remove('active');
        currentPrivateChat = username;
        currentGroup = null;
        sessionStorage.setItem('currentChat', JSON.stringify({
            type: 'private',
            name: username
        }));
        UI.currentGroupName.textContent = `Личный чат с ${username}`;
        UI.chatBox.innerHTML = '';
        lastTimestamp = 0;
        await loadPrivateMessages();
        await loadPrivateChats();
        loadMessages();
    };

    // Инициализация переменных состояния
    let participantsNeedUpdate = false;
    let currentGroup = null;
    let currentPrivateChat = null;
    let lastTimestamp = 0;
    const username = sessionStorage.getItem('username');
    let currentSearch = {
        type: '',
        chatId: null,
        query: '',
        page: 1,
        perPage: 20,
        sort: 'date'
    };
    let sessionKey = null;
    let serverPublicKey = null;

    async function fetchServerPublicKey() {
        const res = await fetch('/public_key');
        serverPublicKey = await res.text();
    }
    

    // Элементы интерфейса
    const UI = {
        chatBox: document.getElementById("chat-box"),
        messageForm: document.getElementById("message-form"),
        messageInput: document.getElementById("message-input"),
        createGroupBtn: document.getElementById("create-group-btn"),
        groupsList: document.getElementById("groups-list"),
        currentGroupName: document.getElementById("current-group-name"),
        sidebar: document.querySelector(".sidebar"),
        sidebarToggle: document.getElementById("sidebar-toggle"), 
        sidebarClose: document.getElementById('sidebar-close'),
        searchUserInput: document.getElementById('search-user-input'),
        startChatBtn: document.getElementById('start-chat-btn'),
        currentChatInfo: document.getElementById('current-chat-info'),
        sendBtn: document.getElementById('send-btn'),
        privateChatsList: document.getElementById('private-chats-list'),
        fileInput: document.getElementById('file-input'),
        fileBtn: document.getElementById('file-btn'),
        fileIndicator: document.getElementById('file-indicator'),
        fileCount: document.querySelector('.file-count'),
        clearFilesBtn: document.querySelector('.clear-files-btn'),
        membersToggle: document.getElementById("members-toggle"),
        membersSidebar: document.querySelector(".sidebar-right"),
        membersClose: document.getElementById('members-close'),
        membersList: document.getElementById('members-list')
    };

    // Инициализация модальных оконо
    const createGroupModal = document.getElementById('create-group-modal');
    const addMemberModal = document.getElementById('add-member-modal');
    const confirmationModal = document.getElementById('confirmation-modal');
    const renameGroupModal = document.getElementById('rename-group-modal');

    // Закрытие модалных окон при клике вне 
    window.addEventListener('click', (e) => {
    if (e.target === createGroupModal) createGroupModal.style.display = 'none';
    if (e.target === addMemberModal) addMemberModal.style.display = 'none';
    if (e.target === confirmationModal) confirmationModal.style.display = 'none';
    if (e.target === renameGroupModal) renameGroupModal.style.display = 'none';
    });

    // Закрытие модальныз окок по Escape
    document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        createGroupModal.style.display = 'none';
        addMemberModal.style.display = 'none';
        confirmationModal.style.display = 'none';
        renameGroupModal.style.display = 'none';
    }
    });
    
    // Восстановление состояния чата
    const savedChat = JSON.parse(sessionStorage.getItem('currentChat') || 'null');
    if (savedChat) {
        if (savedChat.type === 'group') {
            selectGroup(savedChat.id, savedChat.name);
        } else if (savedChat.type === 'private') {
            selectPrivateChat(savedChat.name);
        }
    } else {
        // Явно открываем общий чат, если ничего не сохранено
        selectGroup(null, 'Общий чат');
        // Сохраняем состояние общего чата 1
        sessionStorage.setItem('currentChat', JSON.stringify({
            type: 'general',
            id: null,
            name: 'Общий чат'
        }));
    }

    // Обработчики для правого сайдбара
    UI.membersToggle.addEventListener('click', function(e) {
        e.stopPropagation();
        UI.membersSidebar.classList.toggle('active');
        markParticipantsForUpdate();
    });

    //Обработчик для кнопки файла
    UI.fileBtn.addEventListener('click', () => UI.fileInput.click());

    //обраюотчик работы с файлами
    UI.fileInput.addEventListener('change', updateFileIndicator);
    UI.clearFilesBtn.addEventListener('click', clearFiles);
    
    // Обработчик открытия/закрытия
    UI.sidebarToggle.addEventListener('click', function(e) {
        e.stopPropagation();
        UI.sidebar.classList.toggle('active');
        this.style.display = 'none'; // Скрываем кнопку при открытии
    });

    // Закрытие при клике вне сайдбара
    document.addEventListener('click', function(e) {
    if (!UI.sidebar.contains(e.target) && 
        !UI.sidebarToggle.contains(e.target) &&
        UI.sidebar.classList.contains('active')) {
        UI.sidebar.classList.remove('active');
        UI.sidebarToggle.style.display = 'block'; // Показываем кнопку
    }
    if (!UI.membersSidebar.contains(e.target) && 
        !UI.membersToggle.contains(e.target) &&
        UI.membersSidebar.classList.contains('active')) {
        UI.membersSidebar.classList.remove('active');
    }

    window.logout = function() {
        sessionStorage.clear();
        document.cookie = 'user_id=; Path=/; Expires=Thu, 01 Jan 1970 00:00:01 GMT;';
        updateAuthButtons();
        window.location.href = '/login';
    };
});

    // Обработчик закрытия сайдбара через крестик
    UI.sidebarClose.addEventListener('click', function(e) {
        e.stopPropagation();
        UI.sidebar.classList.remove('active');
        UI.sidebarToggle.style.display = 'block'; 
    });

    UI.membersClose.addEventListener('click', function(e) {
        e.stopPropagation();
        UI.membersSidebar.classList.remove('active');
    });

    // Инициализация
    initEmojiPicker();
    loadGroups();
    loadPrivateChats();
    setupEventListeners();
    generateSessionKey();
    await restoreSessionKey();
    if (!sessionKey) await generateSessionKey();
    await fetchServerPublicKey();

    console.log("Original key:", serverPublicKey);
        const pemContents = serverPublicKey
            .replace('-----BEGIN PUBLIC KEY-----', '')
            .replace('-----END PUBLIC KEY-----', '')
            .replace(/\s+/g, '');
        console.log("Cleaned key:", pemContents);

    let isTabActive = true;

    window.addEventListener('focus', () => {
        isTabActive = true;
        checkForUpdates();
    });

    window.addEventListener('blur', () => {
        isTabActive = false;
    });

    async function checkForUpdates() {
        if (!isTabActive) return;
    
        try {
            // 1. Проверяем обновления интерфейса (группы, чаты)
            await checkInterfaceUpdates();
            
            // 2. Проверяем новые сообщения в текущем чате
            if (currentGroup) {
                await loadMessages();
            } else if (currentPrivateChat) {
                await loadPrivateMessages();
            } else {
                await loadMessages(); // Общий чат
            }
            
            // 3. Всегда обновляем список личных чатов при проверке обновлений
            await loadPrivateChats();
            
            // 4. Проверяем измененные/удаленные сообщения
            await checkDeletedMessages();
            await checkEditedMessages();
            
        } catch (e) {
            console.error('Update error:', e);
        } finally {
            debouncedUpdate();
        }
    }
    
    let updateTimeout;
    
    function debouncedUpdate() {
        clearTimeout(updateTimeout);
        updateTimeout = setTimeout(() => {
            checkForUpdates();
        }, 1000);
    }

    let participantsUpdateTimeout;

    function debouncedLoadParticipants() {
        clearTimeout(participantsUpdateTimeout);
        participantsUpdateTimeout = setTimeout(() => {
            loadParticipants();
        }, 2000); // Обновлять не чаще чем раз в 2 секунды
    }

    // Функции
    function initEmojiPicker() {

        const emojiPicker = document.getElementById("emoji-picker");
        const emojiButton = document.getElementById("emoji-btn");
        const messageInput = document.getElementById("message-input")
  
        // Закрытие при клике вне области
        document.addEventListener('click', (e) => {
            if(!emojiButton.contains(e.target) && !emojiPicker.contains(e.target)) {
                emojiPicker.classList.remove('show');
            }
        });

        // Список эмодзи
        const emojiList = [
            '😁', '😂', '😃', '😄', '😅', '😆', '😇', '😈', '😉', '😊',
            '😋', '😌', '😍', '😎', '😏', '😐', '😒', '😓', '😔', '😖',
            '😘', '😚', '😜', '😝', '😞', '😠', '😡', '😢', '😣', '😤',
            '😥', '😨', '😩', '😪', '😫', '😭', '😰', '😱', '👍', '🎉',
            '❤️', '😸', '😹', '😺', '😻', '😼', '😽', '😾', '😿', '🙀',
            '💩', '👴', '🙅', '🙆', '🙇', '🙈', '🙉', '🙊', '🙋', '🙌',
            '🙍', '🙎', '🙏', '🐌', '🐍', '🐎', '🐑', '🐒', '🐔', '🐗'
        ];

        const emojisPerRow = 6; // Количество эмодзи в строке

        // Инициализация пикера эмодзи
        emojiList.forEach((emoji, index) => {
            const emojiSpan = document.createElement('span');
            emojiSpan.innerText = emoji;
            emojiPicker.appendChild(emojiSpan);

            if ((index + 1) % emojisPerRow === 0) {
                const breakElement = document.createElement('br');
                emojiPicker.appendChild(breakElement);
            }
        });

        // Обработчик для кнопки эмодзи
        emojiButton.addEventListener("click", function(e) {
            e.stopPropagation();
            emojiPicker.classList.toggle("show");
        });

        // Обработчик выбора эмодзи
        emojiPicker.addEventListener("click", function(e) {
            if(e.target.tagName === "SPAN") {
                // Заменяем прямой доступ на использование UI
                UI.messageInput.value += e.target.innerText;
                emojiPicker.classList.remove("show");
                
                // Триггерим событие input для авто-высоты
                const event = new Event('input');
                UI.messageInput.dispatchEvent(event);
            }
        
        });

    }
    
    async function loadMessages() {
        try {
            let url;
            if (currentGroup) {
                // Проверяем доступ к группе перед загрузкой сообщений
                const accessRes = await fetch(`/check_group_access?group_id=${currentGroup}`);
                if (!accessRes.ok) {
                    currentGroup = null;
                    sessionStorage.removeItem('currentChat');
                    UI.currentGroupName.textContent = 'Общий чат';
                    return loadMessages();
                }
                url = `/get_group_messages?group_id=${currentGroup}&timestamp=${lastTimestamp}`;
            } else {
                url = `/get_messages?timestamp=${lastTimestamp}`;
            }
    
            const res = await fetch(url);
            const data = await res.json();
            
            if (data.messages?.length > 0) {
                // Расшифровываем сообщения если есть ключ
                if (sessionKey) {
                    for (const msg of data.messages) {
                        if (
                            typeof msg.message_text === 'string' &&
                            msg.message_text.startsWith('{') &&
                            msg.message_text.includes('"iv":') &&
                            msg.message_text.includes('"data":')
                        ) {
                            msg.message_text = await decryptMessage(msg.message_text);
                        }
                    }
                }
            }
            if (res.status === 401) {
                window.location.href = '/login';
                return;
            }
            
            if (res.status === 403) {
                currentGroup = null;
                sessionStorage.removeItem('currentChat');
                UI.currentGroupName.textContent = 'Общий чат';
                return loadMessages();
            }
    
            if (res.status === 500) {
                window.location.href = '/500';
                return;
            }
    
            if (!res.ok) {
                const error = await res.json();
                throw new Error(error.message || `HTTP error! status: ${res.status}`);
            }
            
            if (lastTimestamp === 0) {
                UI.chatBox.innerHTML = '';
            }
            
            if(data.messages.length > 0) {
                displayMessages(data.messages);
                lastTimestamp = data.timestamp;
            }
        }
        catch (error) {
            console.error("Error loading messages:", error);
            
            if (error.message.includes('403') && currentGroup) {
                currentGroup = null;
                sessionStorage.removeItem('currentChat');
                UI.currentGroupName.textContent = 'Общий чат';
                loadMessages();
            } else if (error.message.includes('401')) {
                window.location.href = '/login';
            } else {
                UI.chatBox.innerHTML = '<div class="error">Ошибка загрузки сообщений</div>';
            }
        }
    }

    function displayMessages(messages) {
        const chatBox = UI.chatBox;
        const wasScrolledToBottom = chatBox.scrollHeight - chatBox.clientHeight <= chatBox.scrollTop + 50;
    
        // Удаление временных сообщений
        const tempMessages = Array.from(chatBox.children).filter(el => el.classList.contains('temp'));
        tempMessages.forEach(el => el.remove());
    
        // Сортировка сообщений
        const sortedMessages = [...messages].sort((a, b) => a.timestamp - b.timestamp);
    
        // Создаем Set для отслеживания уже отображенных сообщений
        const displayedIds = new Set();
        Array.from(chatBox.children).forEach(el => displayedIds.add(el.dataset.id));
    
        sortedMessages.forEach(msg => {
            // Пропускаем уже отображенные сообщения
            if (displayedIds.has(msg.id.toString())) return;
    
            const messageElement = document.createElement("div");
            messageElement.className = "message" + (msg.temp ? " temp" : "");
            
            if (msg.user_id === 0 || msg.sender === 'System') {
                messageElement.classList.add('system-message');
            }
            
            messageElement.dataset.id = msg.id;
            messageElement.dataset.timestamp = msg.timestamp;
    
            const timeOptions = { hour: '2-digit', minute: '2-digit', hour12: false };
            const date = new Date(msg.timestamp * 1000);
            const time = isNaN(date) ? '--:--' : date.toLocaleTimeString([], timeOptions);
    
            if (msg.user_id === 0 || msg.sender === 'System') {
                messageElement.innerHTML = `
                    <div class="message-header system-header">
                        <span class="time">${time}</span>
                    </div>
                    <p class="message-text system-text">${msg.message_text}</p>
                `;
            } else {
                messageElement.innerHTML = `
                    <div class="message-header">
                        <span class="sender">${msg.sender}</span>
                        <span class="time">${time}</span>
                    </div>
                    ${msg.message_text ? `<p class="message-text">${msg.message_text}</p>` : ''}
                    ${msg.attachments?.length > 0 ? `
                    <div class="attachments">
                        ${msg.attachments.map(att => `
                            ${att.mime_type.startsWith('image/') ? `
                                <div class="attachment-image">
                                    <img src="${att.path}" alt="${att.filename}">
                                    <span class="file-name">${att.filename}</span>
                                </div>
                            ` : `
                                <div class="attachment-file">
                                    <div class="file-icon">📄</div>
                                    <a href="${att.path}" download class="file-link">
                                        ${att.filename}
                                    </a>
                                </div>
                            `}
                        `).join('')}
                    </div>
                    ` : ''}
                `;
            }
    
            chatBox.appendChild(messageElement);
        });
    
        requestAnimationFrame(() => {
            if (wasScrolledToBottom) {
                chatBox.scrollTo({
                    top: chatBox.scrollHeight,
                    behavior: 'smooth'
                });
            }
        });
    }
    
    // Функции для контекстного меню
    let longPressTimer;
    let isLongPress = false;
    
    function handleTouchStart(e) {
        longPressTimer = setTimeout(() => {
            isLongPress = true;
            showContextMenu(e);
        }, 500);
    }
    
    function handleTouchEnd(e) {
        clearTimeout(longPressTimer);
        if (isLongPress) {
            e.preventDefault();
            isLongPress = false;
        }
    }
    
    function showContextMenu(e) {
        e.preventDefault();
        const messageElement = e.target.closest('.message');
        if (!messageElement) return;
    
        const messageId = messageElement.dataset.id;
        const messageType = currentGroup ? 'group' : 
                           currentPrivateChat ? 'private' : 'general';
        
        messageElement.dataset.type = messageType;
    
        const rect = messageElement.getBoundingClientRect();
        const hasAttachments = messageElement.querySelector('.attachments') !== null;
    
        const existingMenu = document.querySelector('.context-menu');
        if (existingMenu) existingMenu.remove();
    
        const contextMenu = document.createElement('div');
        contextMenu.className = 'context-menu';
        contextMenu.style.left = `${rect.left}px`;
        contextMenu.style.top = `${rect.bottom}px`;
        
        // Базовые пункты меню
        let menuHTML = `
            <div class="context-menu-item" data-action="delete">
                <span class="menu-icon">🗑️</span>
                Удалить
            </div>
        `;
    
        // Добавляем пункт редактирования только для текстовых сообщений
        if (!hasAttachments) {
            menuHTML += `
                <div class="context-menu-item" data-action="edit">
                    <span class="menu-icon">✏️</span>
                    Редактировать
                </div>
            `;
        }
    
        // Добавляем пункты для работы с вложениями
        if (hasAttachments) {
            menuHTML += `
                <div class="context-menu-item" data-action="view-attachments">
                    <span class="menu-icon">👁️</span>
                    Просмотреть вложения
                </div>
                <div class="context-menu-item" data-action="download-attachments">
                    <span class="menu-icon">📥</span>
                    Скачать все
                </div>
            `;
        }
    
        contextMenu.innerHTML = menuHTML;
    
        document.body.appendChild(contextMenu);
        contextMenu.style.display = 'block';
    
        contextMenu.querySelectorAll('.context-menu-item').forEach(item => {
            item.addEventListener('click', (e) => {
                handleContextMenuAction(e, messageId, messageType, hasAttachments);
                contextMenu.remove();
            });
        });
    
        const closeMenu = (e) => {
            if (!contextMenu.contains(e.target)) {
                contextMenu.remove();
                document.removeEventListener('click', closeMenu);
            }
        };
        document.addEventListener('click', closeMenu);
    }    
    
    async function handleContextMenuAction(e, messageId, messageType, hasAttachments) {
        const action = e.target.closest('.context-menu-item').dataset.action;
        const messageElement = document.querySelector(`[data-id="${messageId}"]`);
        
        if (!messageElement) {
            console.error('Message element not found');
            return;
        }
    
        if (action === 'delete') {
            await deleteMessageById(messageId, messageType);
        } else if (action === 'edit') {
            enableMessageEditing(messageElement, messageId, messageType);
        } else if (action === 'view-attachments') {
            viewAttachments(messageElement);
        } else if (action === 'download-attachments') {
            downloadAllAttachments(messageElement);
        }
    }
    
    async function deleteMessageById(messageId, messageType) {
        try {
            const result = await showConfirmModal();
            if (!result) return;
    
            const res = await fetch(`/delete_message/${messageId}?type=${messageType}`, {
                method: 'DELETE',
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('token')}`
                }
            });
            
            if (res.ok) {
                const messageElement = document.querySelector(`[data-id="${messageId}"]`);
                if (messageElement) messageElement.remove();
            } else {
                const error = await res.json();
                throw new Error(error.error || 'Ошибка удаления');
            }
        } catch (error) {
            console.error("Ошибка удаления:", error);
            showToast('Ошибка при удалении: ' + error.message, 'error');
        }
    }

    // Функция для показа модалки подтверждения
    function showConfirmation(title, message) {
    return new Promise((resolve) => {
        document.getElementById('confirmation-title').textContent = title;
        document.getElementById('confirmation-message').textContent = message;
        confirmationModal.style.display = 'block';
        
        const confirmBtn = document.getElementById('confirmation-confirm');
        const cancelBtn = document.getElementById('confirmation-cancel');
        const closeBtn = confirmationModal.querySelector('.close-modal');
        
        const cleanup = () => {
        confirmBtn.removeEventListener('click', confirmHandler);
        cancelBtn.removeEventListener('click', cancelHandler);
        closeBtn.removeEventListener('click', cancelHandler);
        confirmationModal.style.display = 'none';
        };
        
        const confirmHandler = () => {
        cleanup();
        resolve(true);
        };
        
        const cancelHandler = () => {
        cleanup();
        resolve(false);
        };
        
        confirmBtn.addEventListener('click', confirmHandler);
        cancelBtn.addEventListener('click', cancelHandler);
        closeBtn.addEventListener('click', cancelHandler);
    });
    }

function viewAttachments(messageElement) {
    const attachments = messageElement.querySelector('.attachments');
    if (!attachments) return;

    // Создаем модальное окно для просмотра
    const modal = document.createElement('div');
    modal.className = 'attachments-modal';
    
    let modalContent = '<div class="attachments-modal-content">';
    modalContent += '<button class="close-modal-btn">&times;</button>';
    modalContent += '<h3>Вложения</h3>';
    modalContent += '<div class="attachments-container">';
    
    // Добавляем все вложения в модальное окно
    attachments.querySelectorAll('.attachment-image, .attachment-file').forEach(att => {
        if (att.classList.contains('attachment-image')) {
            const imgSrc = att.querySelector('img').src;
            const fileName = att.querySelector('.file-name').textContent;
            modalContent += `
                <div class="modal-attachment">
                    <img src="${imgSrc}" alt="${fileName}">
                    <span class="file-name">${fileName}</span>
                    <a href="${imgSrc}" download="${fileName}" class="download-btn">Скачать</a>
                </div>
            `;
        } else {
            const fileLink = att.querySelector('a').href;
            const fileName = att.querySelector('a').textContent;
            modalContent += `
                <div class="modal-attachment">
                    <div class="file-icon">📄</div>
                    <span class="file-name">${fileName}</span>
                    <a href="${fileLink}" download="${fileName}" class="download-btn">Скачать</a>
                </div>
            `;
        }
    });
    
    modalContent += '</div></div>';
    modal.innerHTML = modalContent;
    
    // Закрытие модального окна
    modal.querySelector('.close-modal-btn').addEventListener('click', () => {
        modal.classList.remove('show');
        setTimeout(() => {
            modal.remove();
        }, 300);
    });
    
    document.body.appendChild(modal);
    
    // Показываем модальное окно с анимацией
    setTimeout(() => {
        modal.classList.add('show');
    }, 10);
    
    // Закрытие при клике на фон
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.classList.remove('show');
            setTimeout(() => {
                modal.remove();
            }, 300);
        }
    });
}
    
    function downloadAllAttachments(messageElement) {
        const attachments = messageElement.querySelectorAll('.attachment-image img, .attachment-file a');
        if (!attachments.length) return;
    
        // Для каждого вложения создаем скрытую ссылку и кликаем по ней
        attachments.forEach(att => {
            const link = document.createElement('a');
            link.href = att.tagName === 'IMG' ? att.src : att.href;
            link.download = att.tagName === 'IMG' ? 
                att.parentElement.querySelector('.file-name').textContent : 
                att.textContent;
            link.style.display = 'none';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        });
        
        showToast('Загрузка началась', 'success');
    }

    let lastToast = {
        message: null,
        type: null,
        timestamp: 0
    };

    function showToast(message, type = 'info', onClick = null) {
        const now = Date.now();
        const toastCooldown = 3000; // 3 секунды между одинаковыми уведомлениями
        
        // Проверяем, не показывали ли мы уже такое же уведомление недавно
        if (lastToast.message === message && 
            lastToast.type === type && 
            (now - lastToast.timestamp) < toastCooldown) {
            return;
        }
        
        // Обновляем информацию о последнем toast
        lastToast = {
            message,
            type,
            timestamp: now
        };
        
        // Удаляем все существующие toast перед созданием нового
        document.querySelectorAll('.toast').forEach(toast => toast.remove());
        
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        
        // Добавляем иконки в зависимости от типа
        const icons = {
            'error': '❌',
            'success': '✅',
            'info': 'ℹ️'
        };
        
        toast.innerHTML = `
            <span class="toast-icon">${icons[type] || ''}</span>
            <span class="toast-message">${message}</span>
        `;
        
        if (onClick) {
            toast.style.cursor = 'pointer';
            toast.addEventListener('click', onClick);
        }
        
        document.body.appendChild(toast);
        
        setTimeout(() => {
            toast.classList.add('fade-out');
            setTimeout(() => {
                toast.remove();
                // Сбрасываем lastToast, если это было последнее уведомление
                if (lastToast.message === message && lastToast.type === type) {
                    lastToast = {
                        message: null,
                        type: null,
                        timestamp: 0
                    };
                }
            }, 500);
        }, 3000);
    }

    function showConfirmModal() {
        return new Promise((resolve) => {
            const modal = document.getElementById('confirm-modal');
            const closeBtn = modal.querySelector('.confirm-close');
            const cancelBtn = document.getElementById('confirm-cancel');
            const deleteBtn = document.getElementById('confirm-delete');
    
            modal.classList.add('show');
    
            const cleanup = () => {
                modal.classList.remove('show');
                deleteBtn.removeEventListener('click', deleteHandler);
                cancelBtn.removeEventListener('click', cancelHandler);
                closeBtn.removeEventListener('click', cancelHandler);
                modal.removeEventListener('click', backdropHandler);
            };
    
            const deleteHandler = () => {
                cleanup();
                resolve(true);
            };
    
            const cancelHandler = () => {
                cleanup();
                resolve(false);
            };
    
            const backdropHandler = (e) => {
                if (e.target === modal) cancelHandler();
            };
    
            deleteBtn.addEventListener('click', deleteHandler);
            cancelBtn.addEventListener('click', cancelHandler);
            closeBtn.addEventListener('click', cancelHandler);
            modal.addEventListener('click', backdropHandler);
        });
    }
    
    async function enableMessageEditing(messageElement, messageId, messageType) {
        const textElement = messageElement.querySelector('.message-text');
        if (!textElement) return;
        
        const originalText = textElement.textContent;
        const originalTimestamp = messageElement.dataset.timestamp;
        
        const editContainer = document.createElement('div');
        editContainer.className = 'editable-message';
        editContainer.innerHTML = `
            <textarea class="edit-message-input">${originalText}</textarea>
            <div class="edit-buttons">
                <button class="save-edit-btn">Сохранить</button>
                <button class="cancel-edit-btn">Отмена</button>
            </div>
        `;
        
        textElement.replaceWith(editContainer);
        
        const textarea = editContainer.querySelector('textarea');
        const saveBtn = editContainer.querySelector('.save-edit-btn');
        const cancelBtn = editContainer.querySelector('.cancel-edit-btn');
        
        textarea.focus();
        textarea.setSelectionRange(textarea.value.length, textarea.value.length);
        
        saveBtn.addEventListener('click', async () => {
            const newText = textarea.value.trim();
            if (newText && newText !== originalText) {
                try {
                    const res = await fetch(`/edit_message/${messageId}?type=${messageType}`, {
                        method: 'PATCH',
                        headers: {
                            'Content-Type': 'application/json',
                            'Authorization': `Bearer ${localStorage.getItem('token')}`
                        },
                        body: JSON.stringify({ 
                            message: newText,
                            timestamp: Math.floor(Date.now()/1000) 
                        })
                    });
                    
                    if (res.ok) {
                        textElement.textContent = newText;
                        messageElement.dataset.timestamp = Math.floor(Date.now()/1000); 
                        editContainer.replaceWith(textElement);
                    } else {
                        const error = await res.json();
                        throw new Error(error.error || 'Ошибка редактирования');
                    }
                } catch (error) {
                    console.error("Ошибка редактирования:", error);
                    alert(`Ошибка: ${error.message}`);
                }
            } else {
                editContainer.replaceWith(textElement);
            }
        });
        
        cancelBtn.addEventListener('click', () => {
            editContainer.replaceWith(textElement);
        });
    }

    async function checkInterfaceUpdates() {
        try {
            // Проверяем обновления групп с передачей последнего времени проверки
            const lastCheck = parseInt(sessionStorage.getItem('groupsLastCheck') || '0');
            const groupsRes = await fetch(`/check_groups_updates?last_check=${lastCheck}`);
            
            if (groupsRes.ok) {
                const data = await groupsRes.json();
                if (data.updated) {
                    sessionStorage.setItem('groupsLastCheck', data.new_timestamp || Date.now());
                    await loadGroups();
                }
            }
            
            // Проверяем обновления приватных чатов
            const chatsRes = await fetch('/check_private_chats_updates');
            if (chatsRes.ok) {
                const chatsData = await chatsRes.json();
                if (chatsData.updated) {
                    await loadPrivateChats();
                }
            }
            
            // Если открыт сайдбар участников - обновляем его
            if (UI.membersSidebar.classList.contains('active')) {
                markParticipantsForUpdate();
            }
        } catch (e) {
            console.error('Interface update error:', e);
        }
    }

    async function checkDeletedMessages() {
        // Получаем все ID сообщений, которые есть в DOM
        const messageElements = Array.from(document.querySelectorAll('.message[data-id]'));
        const messageIds = messageElements.map(el => el.dataset.id);
        
        if (messageIds.length === 0) return;
        
        try {
            let url;
            if (currentGroup) {
                url = `/check_messages?type=group&chat_id=${currentGroup}&ids=${messageIds.join(',')}`;
            } else if (currentPrivateChat) {
                url = `/check_messages?type=private&chat_id=${currentPrivateChat}&ids=${messageIds.join(',')}`;
            } else {
                url = `/check_messages?type=general&ids=${messageIds.join(',')}`;
            }
            
            const res = await fetch(url);
            if (res.ok) {
                const data = await res.json();
                data.existingIds = data.existingIds || [];
                messageElements.forEach(el => {
                    if (!data.existingIds.includes(el.dataset.id)) {
                        el.remove();
                    }
                });
            }
        } catch (e) {
            console.error('Error checking deleted messages:', e);
        }
    }

    async function checkEditedMessages() {
        const messageElements = Array.from(document.querySelectorAll('.message[data-id]'));
        if (messageElements.length === 0) return;
    
        try {
            let url;
            if (currentGroup) {
                url = `/check_edited_messages?type=group&chat_id=${currentGroup}`;
            } else if (currentPrivateChat) {
                url = `/check_edited_messages?type=private&chat_id=${currentPrivateChat}`;
            } else {
                url = `/check_edited_messages?type=general`;
            }
    
            // Добавляем timestamp последнего сообщения
            const lastMessage = messageElements[messageElements.length - 1];
            url += `&last_timestamp=${lastMessage.dataset.timestamp}`;
    
            const res = await fetch(url);
            if (res.ok) {
                const data = await res.json();
                data.editedMessages = data.editedMessages || [];
                
                // Обновляем измененные сообщения
                data.editedMessages.forEach(msg => {
                    const messageElement = document.querySelector(`[data-id="${msg.id}"]`);
                    if (messageElement) {
                        const textElement = messageElement.querySelector('.message-text');
                        if (textElement && textElement.textContent !== msg.text) {
                            textElement.textContent = msg.text;
                            messageElement.classList.add('highlight');
                            setTimeout(() => {
                                messageElement.classList.remove('highlight');
                            }, 2000);
                        }
                    }
                });
            }
        } catch (e) {
            console.error('Error checking edited messages:', e);
        }
    }

    async function createGroup() {
    createGroupModal.style.display = 'block';
    
    const nameInput = document.getElementById('group-name-input');
    nameInput.focus();
    
    return new Promise((resolve) => {
        const confirmBtn = document.getElementById('create-group-confirm');
        const cancelBtn = document.getElementById('create-group-cancel');
        const closeBtn = createGroupModal.querySelector('.close-modal');
        
        const cleanup = () => {
        confirmBtn.removeEventListener('click', confirmHandler);
        cancelBtn.removeEventListener('click', cancelHandler);
        closeBtn.removeEventListener('click', cancelHandler);
        createGroupModal.style.display = 'none';
        nameInput.value = '';
        };
        
        const confirmHandler = () => {
        const groupName = nameInput.value.trim();
        if (groupName) {
            cleanup();
            resolve(groupName);
        } else {
            nameInput.focus();
        }
        };
        
        const cancelHandler = () => {
        cleanup();
        resolve(null);
        };
        
        confirmBtn.addEventListener('click', confirmHandler);
        cancelBtn.addEventListener('click', cancelHandler);
        closeBtn.addEventListener('click', cancelHandler);
    }).then(async (groupName) => {
        if (!groupName) return;
        
        try {
        const res = await fetch('/create_group', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ name: groupName })
        });
        
        if (res.ok) {
            await loadGroups();
            showToast("Группа создана успешно!", 'success');
        } else {
            const error = await res.json();
            showToast(error.error || "Ошибка при создании группы", 'error');
        }
        } catch (error) {
        console.error("Error creating group:", error);
        showToast("Ошибка соединения с сервером", 'error');
        }
    });
    }

    async function loadGroups() {
        try {
            const res = await fetch('/get_groups', {
                headers: {
                    'Cache-Control': 'no-cache',
                    'Authorization': `Bearer ${localStorage.getItem('token')}`
                }
            });
            
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            
            const groups = await res.json();
            const activeGroupId = currentGroup;
            
            // Сохраняем текущую позицию прокрутки
            const scrollPosition = UI.groupsList.scrollTop;
            
            UI.groupsList.innerHTML = `
                <div class="group-item ${!currentGroup ? 'active' : ''}" 
                    onclick="selectGroup(null, 'Общий чат', this)">
                    Общий чат
                </div>
                ${groups.map(group => `
                    <div class="group-item ${group.id === activeGroupId ? 'active' : ''}" 
                        data-group-id="${group.id}" 
                        onclick="selectGroup(${group.id}, '${group.name}', this)">
                        <span>${group.name}</span>
                        <div class="group-menu">
                            <button class="group-actions-btn" onclick="event.stopPropagation(); toggleGroupMenu(event, ${group.id}, '${group.role}')">⋮</button>
                            <div class="group-actions-menu" id="group-menu-${group.id}">
                                ${group.role === 'owner' || group.role === 'admin' ? `
                                    <button class="group-action" onclick="addMemberPrompt(${group.id})">➕ Добавить участника</button>
                                    <button class="group-action" onclick="renameGroupPrompt(${group.id}, '${group.name}')">✏️ Изменить название</button>
                                ` : ''}
                                <button class="group-action" onclick="leaveGroupPrompt(${group.id})">🚪 Покинуть группу</button>
                            </div>
                        </div>
                    </div>
                `).join('')}
            `;
            
            // Восстанавливаем позицию прокрутки
            UI.groupsList.scrollTop = scrollPosition;
            
        } catch (error) {
            console.error("Error loading groups:", error);
            UI.groupsList.innerHTML = '<div class="error">Ошибка загрузки групп</div>';
        }
    }
    
    window.renameGroupPrompt = function(groupId, currentName) {
    const modal = document.getElementById('rename-group-modal');
    const input = document.getElementById('rename-group-input');
    
    // Устанавливаем текущее название группы
    input.value = currentName;
    modal.style.display = 'block';
    input.focus();
    
    return new Promise((resolve) => {
        const confirmBtn = document.getElementById('rename-group-confirm');
        const cancelBtn = document.getElementById('rename-group-cancel');
        const closeBtn = modal.querySelector('.close-modal');
        
        const cleanup = () => {
        confirmBtn.removeEventListener('click', confirmHandler);
        cancelBtn.removeEventListener('click', cancelHandler);
        closeBtn.removeEventListener('click', cancelHandler);
        modal.style.display = 'none';
        input.value = '';
        };
        
        const confirmHandler = () => {
        const newName = input.value.trim();
        if (newName) {
            cleanup();
            resolve(newName);
        } else {
            input.focus();
        }
        };
        
        const cancelHandler = () => {
        cleanup();
        resolve(null);
        };
        
        confirmBtn.addEventListener('click', confirmHandler);
        cancelBtn.addEventListener('click', cancelHandler);
        closeBtn.addEventListener('click', cancelHandler);
    }).then(async (newName) => {
        if (!newName) return;
        
        try {
        await renameGroup(groupId, newName);
        } catch (error) {
        console.error("Rename group error:", error);
        showToast(error.message, 'error');
        }
    });
    };

    // Новые функции управления группами
    window.toggleGroupMenu = function(event, groupId, userRole) {
        event.stopPropagation();
        const menu = document.getElementById(`group-menu-${groupId}`);
        
        // Закрываем все другие открытые меню
        document.querySelectorAll('.group-actions-menu').forEach(m => {
            if (m !== menu) m.classList.remove('show');
        });
        
        // Показываем/скрываем текущее меню
        menu.classList.toggle('show');
        
        // Обработчик закрытия при клике вне меню
        const closeHandler = (e) => {
            if (!menu.contains(e.target)) {
                menu.classList.remove('show');
                document.removeEventListener('click', closeHandler);
            }
        };
        
        document.addEventListener('click', closeHandler);
    };
    
    window.addMemberPrompt = function(groupId) {
    addMemberModal.style.display = 'block';
    const usernameInput = document.getElementById('member-username-input');
    usernameInput.focus();
    
    return new Promise((resolve) => {
        const confirmBtn = document.getElementById('add-member-confirm');
        const cancelBtn = document.getElementById('add-member-cancel');
        const closeBtn = addMemberModal.querySelector('.close-modal');
        
        const cleanup = () => {
        confirmBtn.removeEventListener('click', confirmHandler);
        cancelBtn.removeEventListener('click', cancelHandler);
        closeBtn.removeEventListener('click', cancelHandler);
        addMemberModal.style.display = 'none';
        usernameInput.value = '';
        };
        
        const confirmHandler = () => {
        const username = usernameInput.value.trim();
        if (username) {
            cleanup();
            resolve(username);
        } else {
            usernameInput.focus();
        }
        };
        
        const cancelHandler = () => {
        cleanup();
        resolve(null);
        };
        
        confirmBtn.addEventListener('click', confirmHandler);
        cancelBtn.addEventListener('click', cancelHandler);
        closeBtn.addEventListener('click', cancelHandler);
    }).then(async (username) => {
        if (!username) return;
        
        try {
        const res = await fetch('/add_to_group', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
            group_id: groupId,
            username: username,
            role: 'member'
            })
        });
        
        if (res.ok) {
            showToast("Пользователь успешно добавлен!", 'success');
            await loadGroups();
            
            if (currentGroup === groupId) {
            await loadParticipants();
            }
        } else {
            const error = await res.json();
            showToast(error.error || "Ошибка добавления пользователя", 'error');
        }
        } catch (error) {
        console.error("Error adding member:", error);
        showToast("Ошибка соединения с сервером", 'error');
        }
    });
    };
        
    window.leaveGroupPrompt = async function(groupId) {
    const confirmed = await showConfirmation(
        "Покинуть группу", 
        "Вы уверены, что хотите покинуть группу? Это действие нельзя отменить."
    );
    
    if (confirmed) {
        try {
        const res = await fetch('/leave_group', {
            method: 'POST',
            headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${localStorage.getItem('token')}`
            },
            body: JSON.stringify({ group_id: groupId })
        });
        
        if (res.ok) {
            if (currentGroup === groupId) {
            currentGroup = null;
            sessionStorage.removeItem('currentChat');
            UI.currentGroupName.textContent = 'Общий чат';
            UI.chatBox.innerHTML = '';
            lastTimestamp = 0;
            loadMessages();
            }
            await loadGroups();
            showToast("Вы покинули группу", 'success');
        } else {
            const error = await res.json();
            throw new Error(error.error || 'Ошибка при выходе из группы');
        }
        } catch (error) {
        console.error("Ошибка выхода:", error);
        showToast(error.message || 'Ошибка соединения с сервером', 'error');
        }
    }
    };


        
    window.selectGroup = async function(groupId, groupName, element) {
        if (groupId) {
            // Проверяем доступ к группе
            const res = await fetch(`/check_group_access?group_id=${groupId}`);
            if (!res.ok) {
                alert('У вас нет доступа к этой группе');
                return;
            }
        }
        
        currentGroup = groupId;
        currentPrivateChat = null;
        sessionStorage.setItem('currentChat', JSON.stringify({
            type: groupId ? 'group' : 'general',
            id: groupId,
            name: groupName
        }));
        
        UI.currentGroupName.textContent = groupName || 'Общий чат';
        UI.chatBox.innerHTML = '';
        lastTimestamp = 0;
        await loadGroups();
        await loadMessages();
        await loadParticipants(); 
    };



    function setupEventListeners() {
        document.getElementById('search-btn').addEventListener('click', openSearchModal);
        document.getElementById('execute-search').addEventListener('click', executeSearch);
        document.querySelector('.close-modal').addEventListener('click', closeSearchModal);

        UI.createGroupBtn.addEventListener("click", createGroup);

        UI.chatBox.addEventListener('contextmenu', showContextMenu);
        UI.chatBox.addEventListener('touchstart', handleTouchStart);
        UI.chatBox.addEventListener('touchend', handleTouchEnd);
        
        document.addEventListener('click', function(e) {
            document.querySelectorAll('.group-actions-menu').forEach(menu    => {
                if (!menu.contains(e.target)) {
                    menu.classList.remove('show');
                }
            });
        });

        UI.messageForm.addEventListener("submit", function(e) {
            e.preventDefault();
            sendMessage(e);
        });

        UI.messageInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage(e);
            }
        });
    }

    async function encryptFile(file) {
        if (!sessionKey) return file;
        
        try {
            const iv = window.crypto.getRandomValues(new Uint8Array(12));
            const fileData = await file.arrayBuffer();
            
            const encrypted = await window.crypto.subtle.encrypt(
                { name: "AES-GCM", iv },
                sessionKey,
                fileData
            );
            
            // Создаем новый файл с зашифрованными данными
            return new File([encrypted], file.name, {
                type: 'application/octet-stream',
                lastModified: file.lastModified
            });
        } catch (error) {
            console.error("File encryption error:", error);
            return file;
        }
    }

    async function generateSessionKey() {
        try {
            // Генерация случайного сессионного ключа (256 бит)
            sessionKey = await window.crypto.subtle.generateKey(
                { name: "AES-GCM", length: 256 },
                true,
                ["encrypt", "decrypt"]
            );
                // Сохраняем ключ в sessionStorage
            const exported = await window.crypto.subtle.exportKey("raw", sessionKey);
            sessionStorage.setItem('sessionKey', arrayBufferToBase64(exported));
            console.log("Сессионный ключ сгенерирован");
            sendSessionKeyToServer();
        } catch (error) {
            console.error("Ошибка генерации ключа:", error);
        }
    }
        
    // При загрузке страницы пробуем восстановить ключ
    async function restoreSessionKey() {
        const keyB64 = sessionStorage.getItem('sessionKey');
        if (keyB64) {
            const keyBuf = base64ToArrayBuffer(keyB64);
            sessionKey = await window.crypto.subtle.importKey(
                "raw",
                keyBuf,
                { name: "AES-GCM" },
                true,
                ["encrypt", "decrypt"]
            );
        }
    }


    async function sendSessionKeyToServer() {
        try {
            const exportedKey = await window.crypto.subtle.exportKey("raw", sessionKey);
            const exportedKeyBuffer = new Uint8Array(exportedKey);
            
            if (!serverPublicKey) {
            throw new Error("Публичный ключ сервера не загружен");
            }
            const pemHeader = "-----BEGIN PUBLIC KEY-----";
            const pemFooter = "-----END PUBLIC KEY-----";
            
            let pemContents = serverPublicKey
                .split(pemHeader)[1]  // Берем часть после заголовка
                .split(pemFooter)[0]  // Берем часть перед футером
                .replace(/\s+/g, ''); // Удаляем ВСЕ пробелы и переносы

            console.log("Cleaned PEM contents:", pemContents);
            console.log("PEM length:", pemContents.length);

            const binaryDer = base64ToArrayBuffer(pemContents);
            
            const importedPublicKey = await window.crypto.subtle.importKey(
                "spki",
                binaryDer,
                { name: "RSA-OAEP", hash: "SHA-256" },
                false,
                ["encrypt"]
            );
            
            const encryptedKey = await window.crypto.subtle.encrypt(
                { name: "RSA-OAEP" },
                importedPublicKey,
                exportedKeyBuffer
            );
            
            const encryptedKeyBase64 = arrayBufferToBase64(encryptedKey);
            
            const response = await fetch('/set_session_key', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    key: encryptedKeyBase64 
                })
            });
            
            if (!response.ok) {
                throw new Error(`Server responded with status ${response.status}`);
            }
            
            console.log("Сессионный ключ успешно отправлен на сервер");
        } catch (error) {
            console.error("Ошибка отправки ключа:", error);
            throw error;
        }
    }

    function base64ToArrayBuffer(base64) {
        try {
            const binaryString = atob(base64);
            const bytes = new Uint8Array(binaryString.length);
            for (let i = 0; i < binaryString.length; i++) {
                bytes[i] = binaryString.charCodeAt(i);
            }
            return bytes;
        } catch (e) {
            console.error("Error in base64 decoding:", e);
            throw new Error("Invalid base64 string");
        }
    }

    function arrayBufferToBase64(buffer) {
        let binary = '';
        const bytes = new Uint8Array(buffer);
        for (let i = 0; i < bytes.byteLength; i++) {
            binary += String.fromCharCode(bytes[i]);
        }
        return btoa(binary);
    }

    async function encryptMessage(message) {
        if (!sessionKey) {
            console.error("Сессионный ключ не установлен");
            return message;
        }
        
        try {
            const iv = window.crypto.getRandomValues(new Uint8Array(12));
            const encoded = new TextEncoder().encode(message);
            
            const encrypted = await window.crypto.subtle.encrypt(
                { name: "AES-GCM", iv },
                sessionKey,
                encoded
            );
            
            return JSON.stringify({
                iv: arrayBufferToBase64(iv),
                data: arrayBufferToBase64(encrypted)
            });
        } catch (error) {
            console.error("Ошибка шифрования:", error);
            return message;
        }
    }

    async function decryptMessage(encryptedData) {
        if (!sessionKey || typeof encryptedData !== 'string') {
            return encryptedData;
        }
        
        try {
            const { iv, data } = JSON.parse(encryptedData);
            const ivBuffer = base64ToArrayBuffer(iv);
            const dataBuffer = base64ToArrayBuffer(data);
            
            const decrypted = await window.crypto.subtle.decrypt(
                { name: "AES-GCM", iv: ivBuffer },
                sessionKey,
                dataBuffer
            );
            
            return new TextDecoder().decode(decrypted);
        } catch (error) {
            console.error("Ошибка расшифровки:", error);
            return encryptedData;
        }
    }
    
    async function sendMessage(e) {
        e.preventDefault();
        const message = UI.messageInput.value.trim();
        const files = UI.fileInput.files;
        
        if (!message && files.length === 0) {
            clearFiles(); 
            return;
        }

        if (message.toLowerCase() === 'immamake') {
            playSoundEffect();
            UI.messageInput.value = '';
            return;
        }

        const tempId = Date.now();
        
        try {
            let encryptedMsg = message;
            if (sessionKey && message) {
                encryptedMsg = await encryptMessage(message);
            }
            
            // Показываем временное сообщение
            const tempMessage = {
                id: tempId,
                sender: username,
                message_text: message, // Показываем исходный текст локально
                timestamp: Math.floor(Date.now()/1000),
                temp: true,
                type: currentPrivateChat ? 'private' : (currentGroup ? 'group' : 'general'),
                attachments: []
            };

            // Добавляем файлы во временное сообщение
            if (files.length > 0) {
                const uniqueFiles = new Set();
                Array.from(files).forEach(file => {
                    const key = `${file.name}-${file.size}`;
                    if (!uniqueFiles.has(key)) {
                        tempMessage.attachments.push({
                            filename: file.name,
                            mime_type: file.type,
                            path: URL.createObjectURL(file)
                        });
                        uniqueFiles.add(key);
                    }
                });
            }
            
            // Показываем сообщение сразу
            displayMessages([tempMessage]);
            
            // Формируем FormData для отправки
            const formData = new FormData();
            if (encryptedMsg) formData.append('message', encryptedMsg);

            // Добавляем файлы в FormData
            if (files.length > 0) {
                const uniqueFiles = new Set();
                Array.from(files).forEach(file => {
                    const key = `${file.name}-${file.size}`;
                    if (!uniqueFiles.has(key)) {
                        formData.append('files', file, file.name);
                        uniqueFiles.add(key);
                    }
                });
            }

            if (currentGroup) {
                // Проверка доступа к группе
                const accessRes = await fetch(`/check_group_access?group_id=${currentGroup}`);
                if (!accessRes.ok) {
                    alert('У вас больше нет доступа к этой группе');
                    currentGroup = null;
                    sessionStorage.removeItem('currentChat');
                    UI.currentGroupName.textContent = 'Общий чат';
                    return loadMessages();
                }
                formData.append('group_id', currentGroup.toString());
            } else if (currentPrivateChat) {
                formData.append('receiver', currentPrivateChat);
            }

            // Отправка сообщения
            const res = await fetch('/send_message', {
                method: 'POST',
                body: formData
            });
            
            if (!res.ok) throw new Error(await res.text());

            // Удаляем временное сообщение
            const tempElement = UI.chatBox.querySelector(`[data-id="${tempId}"]`);
            if (tempElement) tempElement.remove();

            // Обновляем список чатов после успешной отправки
            await loadPrivateChats();
            
            // Если это новый чат, добавляем его в список
            if (currentPrivateChat) {
                const chats = await fetchPrivateChats();
                const chatExists = chats.chats.some(c => c.username === currentPrivateChat);
                if (!chatExists) {
                    // Принудительно добавляем новый чат в список
                    const newChat = {
                        username: currentPrivateChat,
                        last_activity: Math.floor(Date.now()/1000)
                    };
                    renderPrivateChats([newChat, ...chats.chats]);
                }
            }

        } catch (error) {
            const tempElement = UI.chatBox.querySelector(`[data-id="${tempId}"]`);
            if (tempElement) tempElement.remove();
            
            console.error('Ошибка:', error);
            alert(`Ошибка отправки: ${error.message}`);
        }
        finally {
            UI.messageInput.value = '';
            UI.fileInput.value = '';
            UI.fileIndicator.style.display = 'none';
            document.querySelector('.attachment-container')?.remove();
        }
    }

    UI.messageInput.addEventListener('input', function () {
        this.style.height = 'auto';
        this.style.height = (this.scrollHeight) + 'px';
    });

    UI.messageInput.addEventListener('focus', () => {
        if (window.innerWidth < 768) {
            setTimeout(() => {
                UI.chatBox.scrollTo({
                    top: UI.chatBox.scrollHeight,
                    behavior: 'smooth'
                });
            }, 300);
        }
    });
    
    UI.messageForm.addEventListener('submit', () => {
        if (window.innerWidth < 768) {
            UI.messageInput.blur();
        }
    });
    // Инициализация высоты при загрузке страницы
    window.addEventListener('load', function () {
        UI.messageInput.style.height = 'auto';
        UI.messageInput.style.height = (UI.messageInput.scrollHeight) + 'px';
    });

    // Добавим обработчики
    UI.startChatBtn.addEventListener('click', startPrivateChat);
    UI.searchUserInput.addEventListener('input', searchUsers);


    async function fetchPrivateChats() {
        try {
            const res = await fetch('/get_private_chats');
            return await res.json();
        } catch (error) {
            console.error("Error fetching private chats:", error);
            return { chats: [] };
        }
    }

    async function searchUsers() {
        const searchTerm = UI.searchUserInput.value;
        if (searchTerm.length < 2) return;
        
        try {
            const res = await fetch(`/search_users?q=${encodeURIComponent(searchTerm)}`);
            const data = await res.json();
            renderUserSearchResults(data.users);
        } catch (error) {
            console.error("Search error:", error);
        }
    }

    function renderUserSearchResults(users) {
        UI.privateChatsList.innerHTML = users.map(user => `
            <div class="user-item" onclick="selectPrivateChat('${user}')">
                ${user}
            </div>
        `).join('');
    }

    async function selectPrivateChat(username) {
        currentPrivateChat = username;
        currentGroup = null;
        sessionStorage.setItem('currentChat', JSON.stringify({
            type: 'private',
            name: username
        }));
        UI.currentGroupName.textContent = `Личный чат с ${username}`;
        UI.chatBox.innerHTML = '';
        lastTimestamp = 0;
        await loadPrivateMessages();
        await loadPrivateChats();
        const response = await fetch('/get_private_chats');
        const data = await response.json();
        renderPrivateChats(data);
            
        await loadPrivateMessages();
        requestAnimationFrame(() => {    
            UI.chatBox.scrollTo({
                top: UI.chatBox.scrollHeight,
                behavior: 'auto'
            });
        });

        // Добавьте выделение активного чата
        document.querySelectorAll('.chat-item').forEach(item => {
            item.classList.remove('active');
            if (item.querySelector('span').textContent === username) {
                item.classList.add('active');
            }
        });
    }

    async function loadPrivateMessages() {
        if (!currentPrivateChat) return;
        
        try {
            const res = await fetch(`/get_private_messages?user=${currentPrivateChat}&timestamp=${lastTimestamp}`);
            const data = await res.json();
            
            if (data.messages?.length > 0) {
                if (sessionKey) {
                for (const msg of data.messages) {
                    if (
                        typeof msg.message_text === 'string' &&
                        msg.message_text.startsWith('{') &&
                        msg.message_text.includes('"iv":') &&
                        msg.message_text.includes('"data":')
                    ) {
                        msg.message_text = await decryptMessage(msg.message_text);
                    }
                }
            }
                displayMessages(data.messages);
                lastTimestamp = data.timestamp;
            }
        } catch (error) {
            console.error("Error loading private messages:", error);
        }
    }

    function playSoundEffect() {
        const audio = document.getElementById('sound-effect');
        audio.currentTime = 0; // Перематываем на начало
        audio.play().catch(e => {
            console.error("Ошибка воспроизведения звука:", e);
            // Некоторые браузеры блокируют автовоспроизведение, можно показать кнопку
            showToast("Нажмите для воспроизведения звука", 'info', () => {
                audio.play();
            });
        });
    }

    async function startPrivateChat() {
        const username = UI.searchUserInput.value.trim();
        if (!username) return;

        try {
            const res = await fetch(`/search_users?q=${encodeURIComponent(username)}`);
            const data = await res.json();
            const userExists = data.users.some(user => user === username);
            if (userExists) {
                selectPrivateChat(username);
                UI.searchUserInput.value = '';
            } else {
                alert('Пользователь не найден!');
            }
        } catch (error) {
            console.error("Ошибка при проверке пользователя:", error);
            alert('Ошибка при поиске пользователя');
        }
    }

    async function loadPrivateChats() {
        try {
            const res = await fetch('/get_private_chats', {
                headers: {
                    'Cache-Control': 'no-cache'
                }
            });
            
            if (!res.ok) {
                throw new Error(`HTTP ${res.status}`);
            }
            
            const data = await res.json();
            renderPrivateChats(data.chats || []); 
            
            // Если у нас есть активный приватный чат, но его нет в списке,
            // добавляем его вручную (это может быть новый чат)
            if (currentPrivateChat) {
                const chatExists = data.chats.some(c => c.username === currentPrivateChat);
                if (!chatExists) {
                    // Добавляем текущий чат в начало списка
                    const newChat = {
                        username: currentPrivateChat,
                        last_activity: Math.floor(Date.now()/1000)
                    };
                    renderPrivateChats([newChat, ...data.chats]);
                }
            }
            
        } catch (error) {
            console.error("Error loading private chats:", error);
            showToast('Ошибка загрузки чатов', 'error');
        }
    }

    
    function renderPrivateChats(response) {
        try {
            let chats = [];
            if (response && typeof response === 'object') {
                if (Array.isArray(response.chats)) {
                    chats = response.chats;
                } else if (Array.isArray(response)) {
                    chats = response;
                }
            }
            
            // Всегда добавляем текущий чат, если он активен и его еще нет в списке
            if (currentPrivateChat && !chats.some(c => c.username === currentPrivateChat)) {
                chats.unshift({
                    username: currentPrivateChat,
                    last_activity: Math.floor(Date.now()/1000)
                });
            }
            
            // Сортируем чаты по времени последней активности
            chats.sort((a, b) => b.last_activity - a.last_activity);
            
            UI.privateChatsList.innerHTML = chats.map(chat => `
                <div class="chat-item ${currentPrivateChat === chat.username ? 'active' : ''}" 
                    onclick="selectPrivateChat('${chat.username}')">
                    <span>${chat.username}</span>
                    <small>${new Date(chat.last_activity * 1000).toLocaleDateString('ru-RU', {
                        hour: '2-digit',
                        minute: '2-digit',
                        day: 'numeric',
                        month: 'short'
                    })}</small>
                </div>
            `).join('');
            
            if (chats.length === 0) {
                UI.privateChatsList.innerHTML = '<div class="no-chats">Нет активных чатов</div>';
            }
        } catch (e) {
            console.error('Render chats error:', e);
            UI.privateChatsList.innerHTML = '<div class="error">Ошибка загрузки чатов</div>';
        }
    }

    window.selectPrivateChat = async function(username) {
        currentPrivateChat = username;
        currentGroup = null;
        sessionStorage.setItem('currentChat', JSON.stringify({
            type: 'private',
            name: username
        }));
        UI.currentGroupName.textContent = `Личный чат с ${username}`;
        UI.chatBox.innerHTML = '';
        lastTimestamp = 0;
        await loadPrivateMessages();
        await loadPrivateChats();
        
        await loadPrivateMessages();
        requestAnimationFrame(() => {    
            UI.chatBox.scrollTo({
                top: UI.chatBox.scrollHeight,
                behavior: 'auto'
            });
        });

        document.querySelectorAll('.chat-item').forEach(item => {
            item.classList.remove('active');
            if (item.querySelector('span').textContent === username) {
                item.classList.add('active');
            }
        });
    };

    function updateFileIndicator() {
        const files = UI.fileInput.files;
        if (files.length > 0) {
          UI.fileIndicator.style.display = 'flex';
          UI.fileCount.textContent = `${files.length} файл(ов)`;
          showPreviews(files);
        } else {
          UI.fileIndicator.style.display = 'none';
        }
      }
      
      function showPreviews(files) {
        const container = document.createElement('div');
        container.className = 'attachment-container';
        
        Array.from(files).forEach(file => {
          if (file.type.startsWith('image/')) {
            const reader = new FileReader();
            reader.onload = (e) => {
              const img = document.createElement('img');
              img.className = 'attachment-preview';
              img.src = e.target.result;
              container.appendChild(img);
            }
            reader.readAsDataURL(file);
          } else {
            const div = document.createElement('div');
            div.className = 'attachment-preview';
            div.textContent = file.name;
            container.appendChild(div);
          }
        });
      
        UI.chatBox.appendChild(container);
      }
      
      function clearFiles() {
        UI.fileInput.value = '';
        UI.fileIndicator.style.display = 'none';
        document.querySelector('.attachment-container')?.remove();
      }


      function openSearchModal() {
        const modal = document.getElementById('search-modal');
        modal.style.display = 'block';

        if (currentPrivateChat) {
            // Для личных сообщений используем username собеседника
            currentSearch.type = 'private';
            currentSearch.chatId = currentPrivateChat;  // Сохраняем username, а не ID
            document.querySelector('.search-context').textContent = 
                `Поиск в переписке с ${currentPrivateChat}`;
        }
        
        // Сбрасываем предыдущий поиск
        document.getElementById('search-input').value = '';
        document.getElementById('search-results').innerHTML = '';
        document.getElementById('search-pagination').innerHTML = '';
        
        // Определяем текущий контекст поиска
        fetch('/get_user_id')
            .then(response => {
                if (!response.ok) throw new Error('Failed to get user info');
                return response.json();
            })
            .then(data => {
                if (!data.user_id) {
                    throw new Error('User not authenticated');
                }
                
                if (currentGroup) {
                    currentSearch.type = 'group';
                    currentSearch.chatId = currentGroup;
                    document.querySelector('.search-context').textContent = 
                        `Поиск в группе "${document.getElementById('current-group-name').textContent}"`;
                } 
                else if (currentPrivateChat) {
                    currentSearch.type = 'private';
                    // Используем username из ответа сервера
                    currentSearch.chatId = currentPrivateChat;
                    document.querySelector('.search-context').textContent = 
                        `Поиск в личной переписке с ${currentPrivateChat}`;
                } 
                else {
                    currentSearch.type = 'general';
                    currentSearch.chatId = null;
                    document.querySelector('.search-context').textContent = 'Поиск в общем чате';
                }
            })
            .catch(error => {
                console.error('Error getting user info:', error);
                alert('Ошибка при определении контекста поиска');
                closeSearchModal();
            });
    }
    
    function closeSearchModal() {
        document.getElementById('search-modal').style.display = 'none';
    }
    
    function executeSearch() {
        const searchInput = document.getElementById('search-input');
        const sortSelect = document.getElementById('search-sort');
        
        currentSearch.query = searchInput.value.trim();
        currentSearch.sort = sortSelect.value;
        currentSearch.page = 1;
        
        if (!currentSearch.query) {
            alert('Введите текст для поиска');
            return;
        }
        
        performSearch();
    }
    
    function performSearch() {
        const resultsContainer = document.getElementById('search-results');
        resultsContainer.innerHTML = '<div class="spinner"></div>';
        
        // Создаем URL с параметрами поиска
        const url = new URL('/search_messages', window.location.origin);
        url.searchParams.set('q', currentSearch.query);
        url.searchParams.set('type', currentSearch.type);
        
        // Для личных сообщений используем username собеседника
        if (currentSearch.type === 'private' && currentPrivateChat) {
            url.searchParams.set('chat_id', currentPrivateChat);
        } 
        // Для групп используем ID группы
        else if (currentSearch.type === 'group' && currentGroup) {
            url.searchParams.set('chat_id', currentGroup);
        }
        
        // Общие параметры
        url.searchParams.set('page', currentSearch.page);
        url.searchParams.set('per_page', currentSearch.perPage);
        url.searchParams.set('sort', currentSearch.sort);
    
        fetch(url)
            .then(response => {
                if (!response.ok) {
                    return response.json().then(err => {
                        throw new Error(err.error || 'Search failed');
                    });
                }
                return response.json();
            })
            .then(async data => {
                 if (sessionKey) {
                    for (const msg of data.messages) {
                        if (
                            typeof msg.text === 'string' &&
                            msg.text.startsWith('{') &&
                            msg.text.includes('"iv":') &&
                            msg.text.includes('"data":')
                        ) {
                            msg.text = await decryptMessage(msg.text);
                        }
                    }
                }

                if (data.messages.length === 0) {
                    resultsContainer.innerHTML = `
                        <p>Сообщений не найдено</p>
                        <p class="search-context">
                            Поиск в ${getSearchContextString()}
                        </p>
                    `;
                    document.getElementById('search-pagination').innerHTML = '';
                    return;
                }
                
                resultsContainer.innerHTML = `
                    <p class="search-context">
                        Найдено ${data.total} сообщений в ${getSearchContextString()}
                    </p>
                    ${data.messages.map(msg => `
                        <div class="search-result-item" data-id="${msg.id}">
                            <div class="search-result-header">
                                <span class="sender">${msg.sender}</span>
                                <span class="time">${new Date(msg.timestamp * 1000).toLocaleString()}</span>
                            </div>
                            <div class="search-result-text">${msg.text}</div>
                        </div>
                    `).join('')}
                `;
                
                renderPagination(data.total, data.per_page, data.page);
            })
            .catch(error => {
                console.error('Search error:', error);
                resultsContainer.innerHTML = `
                    <p class="error">Ошибка поиска: ${error.message}</p>
                    <p class="search-context">${getSearchContextString()}</p>
                    <button onclick="performSearch()">Повторить</button>
                `;
            });
    
        // Вспомогательная функция для отображения контекста поиска
        function getSearchContextString() {
            if (currentSearch.type === 'private' && currentPrivateChat) {
                return `переписке с ${currentPrivateChat}`;
            } else if (currentSearch.type === 'group' && currentGroup) {
                return `группе "${document.getElementById('current-group-name').textContent}"`;
            }
            return 'общем чате';
        }
    }
    
    function renderPagination(total, perPage, currentPage) {
        const paginationContainer = document.getElementById('search-pagination');
        const totalPages = Math.ceil(total / perPage);
        
        if (totalPages <= 1) {
            paginationContainer.innerHTML = '';
            return;
        }
        
        let html = '';
        const maxVisiblePages = 5;
        let startPage = Math.max(1, currentPage - Math.floor(maxVisiblePages / 2));
        let endPage = Math.min(totalPages, startPage + maxVisiblePages - 1);
        
        if (endPage - startPage + 1 < maxVisiblePages) {
            startPage = Math.max(1, endPage - maxVisiblePages + 1);
        }
        
        // Кнопка "Назад"
        if (currentPage > 1) {
            html += `<button class="page-btn" onclick="changeSearchPage(${currentPage - 1})">&lt;</button>`;
        }
        
        // Первая страница
        if (startPage > 1) {
            html += `<button class="page-btn" onclick="changeSearchPage(1)">1</button>`;
            if (startPage > 2) {
                html += `<span class="page-dots">...</span>`;
            }
        }
        
        // Основные страницы
        for (let i = startPage; i <= endPage; i++) {
            html += `<button class="page-btn ${i === currentPage ? 'active' : ''}" onclick="changeSearchPage(${i})">${i}</button>`;
        }
        
        // Последняя страница
        if (endPage < totalPages) {
            if (endPage < totalPages - 1) {
                html += `<span class="page-dots">...</span>`;
            }
            html += `<button class="page-btn" onclick="changeSearchPage(${totalPages})">${totalPages}</button>`;
        }
        
        // Кнопка "Вперед"
        if (currentPage < totalPages) {
            html += `<button class="page-btn" onclick="changeSearchPage(${currentPage + 1})">&gt;</button>`;
        }
        
        paginationContainer.innerHTML = html;
    }
    
    function changeSearchPage(newPage) {
        currentSearch.page = newPage;
        performSearch();
        document.getElementById('search-results').scrollTop = 0;
    }
    
    function scrollToMessage(messageId) {
        const messageElement = document.querySelector(`.message[data-id="${messageId}"]`);
        if (messageElement) {
            messageElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
            messageElement.classList.add('highlight');
            setTimeout(() => messageElement.classList.remove('highlight'), 2000);
        }
    }

    async function loadParticipants() {
        if (!participantsNeedUpdate) return;
        participantsNeedUpdate = false;
        
        try {
            if (!currentGroup) {
                // Для общего чата
                const res = await fetch('/get_general_members');
                const data = await res.json();
                
                UI.membersList.innerHTML = '';
                const currentUsername = sessionStorage.getItem('username');
                
                data.members.forEach(member => {
                    const isMe = member === currentUsername;
                    
                    const memberElement = document.createElement('div');
                    memberElement.className = 'member-item';
                    
                    memberElement.innerHTML = `
                        <div class="member-avatar">${member[0].toUpperCase()}</div>
                        <span class="member-name">${member}</span>
                        <span class="member-role">👤 Участник</span>
                        <div class="member-status ${isMe ? 'online' : 'offline'}"></div>
                    `;
                    
                    memberElement.addEventListener('click', () => {
                        if (member !== currentUsername) {
                            selectPrivateChat(member);
                        }
                    });
                    
                    UI.membersList.appendChild(memberElement);
                });
                return;
            }
            
            const res = await fetch(`/get_group_members?group_id=${currentGroup}`);
            const data = await res.json();
            
            const currentUsername = sessionStorage.getItem('username');
            const currentUser = data.members.find(m => m.username === currentUsername);
            if (!currentUser) return;
            
            UI.membersList.innerHTML = '';
            
            data.members.forEach(member => {
                const isMe = member.username === currentUsername;
                const isOnline = isMe;
                
                const canManage = (currentUser.role === 'owner' || 
                                 (currentUser.role === 'admin' && member.role === 'member')) && 
                                 !isMe;
                
                const memberElement = document.createElement('div');
                memberElement.className = 'member-item';
                
                memberElement.innerHTML = `
                    <div class="member-avatar">${member.username[0].toUpperCase()}</div>
                    <span class="member-name">${member.username}</span>
                    <span class="member-role ${member.role}">${GroupRoles.getRoleName(member.role)}</span>
                    ${canManage ? `<button class="member-actions-btn" onclick="event.stopPropagation(); GroupRoles.showMemberMenu(event, ${currentGroup}, '${member.username}', '${member.role}', true, true)">⋮</button>` : ''}
                    <div class="member-status ${isOnline ? 'online' : 'offline'}"></div>
                `;
                
                memberElement.addEventListener('click', () => {
                    if (member.username !== currentUsername) {
                        selectPrivateChat(member.username);
                    }
                });
                
                UI.membersList.appendChild(memberElement);
            });
            
        } catch (error) {
            console.error("Error loading participants:", error);
            UI.membersList.innerHTML = '<div class="error">Ошибка загрузки участников</div>';
        }
    }

    function markParticipantsForUpdate() {
        participantsNeedUpdate = true;
        debouncedLoadParticipants();
    }
    
    window.handleMemberClick = function(username) {
        // Закрываем сайдбар участников
        UI.membersSidebar.classList.remove('active');
        
        // Если это текущий пользователь - не открываем чат
        const currentUser = sessionStorage.getItem('username');
        if (username === currentUser) return;
        
        // Открываем личный чат
        selectPrivateChat(username);
        
        // Обновляем список чатов
        loadPrivateChats();
    };
    window.changeSearchPage = changeSearchPage;

    // Глобальные функции для работы с ролями
    window.GroupRoles = {
        init: function() {
            this.templates = {
                roleMenu: document.getElementById('role-menu-template'),
                memberItem: document.getElementById('group-member-template')
            };
        },
        
        getRoleName: function(role) {
            const roles = {
                'owner': '👑 Владелец',
                'admin': '🛡️ Админ',
                'member': '👤 Участник'
            };
            return roles[role] || role;
        },
        
        showRoleMenu: function(e, groupId, username) {
            e.stopPropagation();
            
            // Удаляем предыдущее меню ролей
            const existingRoleMenu = document.querySelector('.role-menu');
            if (existingRoleMenu) existingRoleMenu.remove();
            
            // Создаем меню ролей из шаблона
            const roleMenu = this.templates.roleMenu.content.cloneNode(true);
            const roleMenuElement = roleMenu.querySelector('.role-menu');
            
            // Вставляем имя пользователя в заголовок
            const usernamePlaceholder = roleMenuElement.querySelector('.username-placeholder');
            usernamePlaceholder.textContent = username;
            
            // Позиционируем меню
            const buttonRect = e.target.getBoundingClientRect();
            const viewportWidth = window.innerWidth;
            
            // Вычисляем позицию
            let leftPosition = buttonRect.left;
            let topPosition = buttonRect.bottom + window.scrollY;
            
            // Проверяем, чтобы не выйти за правый край экрана
            if (leftPosition + 240 > viewportWidth) {
                leftPosition = viewportWidth - 240 - 10;
            }
            
            // Применяем позиционирование
            roleMenuElement.style.position = 'absolute';
            roleMenuElement.style.top = `${topPosition}px`;
            roleMenuElement.style.left = `${leftPosition}px`;
            roleMenuElement.style.zIndex = '1200';
            
            document.body.appendChild(roleMenuElement);
            
            // Обработчики для пунктов меню
            roleMenuElement.querySelectorAll('.role-option').forEach(option => {
                option.addEventListener('click', () => {
                    this.changeMemberRole(groupId, username, option.dataset.role);
                    roleMenuElement.remove();
                });
            });
            
            // Закрытие при клике вне меню
            const closeHandler = (e) => {
                if (!roleMenuElement.contains(e.target)) {
                    roleMenuElement.remove();
                    document.removeEventListener('click', closeHandler);
                }
            };
            
            setTimeout(() => {
                document.addEventListener('click', closeHandler);
            }, 10);
        },
        
        changeMemberRole: async function(groupId, username, newRole) {
            try {
                const res = await fetch('/change_member_role', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        group_id: groupId,
                        username: username,
                        role: newRole
                    })
                });
                
                if (res.ok) {
                    await loadParticipants();
                    showToast(`Роль пользователя ${username} изменена`, 'success');
                    debouncedUpdate(); // Запускаем проверку обновлений
                }
                
                // Обновляем список участников
                await loadParticipants();
                showToast(`Роль пользователя ${username} изменена на "${this.getRoleName(newRole)}"`, 'success');
                
            } catch (error) {
                console.error('Role change error:', error);
                showToast(error.message, 'error');
            }
        },
        
        createMemberElement: function(member, currentUser) {
            const isMe = member.username === currentUser.username;
            const canEdit = (currentUser.role === 'owner' || 
                        (currentUser.role === 'admin' && member.role === 'member')) && 
                        !isMe;
            const canRemove = (currentUser.role === 'owner' || 
                          (currentUser.role === 'admin' && member.role === 'member')) && 
                          !isMe;
            
            // Клонируем шаблон
            const memberElement = this.templates.memberItem.content.cloneNode(true).querySelector('.member-item');
            
            // Заполняем данные
            memberElement.querySelector('.member-avatar').textContent = member.username[0].toUpperCase();
            memberElement.querySelector('.member-name').textContent = member.username;
            
            const roleElement = memberElement.querySelector('.member-role');
            roleElement.textContent = this.getRoleName(member.role);
            roleElement.classList.add(member.role);
            
            if (isMe) {
                roleElement.textContent += ' (Вы)';
            }
            
            // Настраиваем кнопку действий (показываем только если есть какие-то действия)
            const actionsBtn = memberElement.querySelector('.member-actions-btn');
            if (canEdit || canRemove) {
                actionsBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    this.showMemberMenu(e, currentUser.groupId, member.username, member.role, canEdit, canRemove);
                });
            } else {
                actionsBtn.style.display = 'none';
            }
            
            // Статус (онлайн/оффлайн)
            memberElement.querySelector('.member-status').classList.add(
                Math.random() > 0.3 ? 'online' : 'offline'
            );
            
            return memberElement;
        },
        
        showMemberMenu: function(e, groupId, username, role, canEdit, canRemove) {
            e.stopPropagation();
            
            // Удаляем предыдущее меню, если есть
            const existingMenu = document.querySelector('.member-menu');
            if (existingMenu) existingMenu.remove();
            
            // Создаем меню
            const menu = document.createElement('div');
            menu.className = 'member-menu';
            
            // Позиционируем меню рядом с кнопкой
            const buttonRect = e.target.getBoundingClientRect();
            const viewportWidth = window.innerWidth;
            
            // Рассчитываем позицию меню
            let leftPosition = buttonRect.left;
            let topPosition = buttonRect.bottom + 5;
            
            // Проверяем, чтобы меню не выходило за правый край экрана
            const menuWidth = 220;
            if (leftPosition + menuWidth > viewportWidth) {
                leftPosition = viewportWidth - menuWidth - 10;
            }
            
            menu.style.left = `${leftPosition}px`;
            menu.style.top = `${topPosition}px`;
            
            // Добавляем пункт изменения роли, если есть права
            if (canEdit) {
                const editRoleItem = document.createElement('div');
                editRoleItem.className = 'menu-item';
                editRoleItem.innerHTML = '<span class="menu-icon">🛡️</span> Изменить роль';
                editRoleItem.addEventListener('click', () => {
                    this.showRoleMenu(e, groupId, username);
                    menu.remove();
                });
                menu.appendChild(editRoleItem);
            }
            
            // Добавляем пункт исключения, если есть права
            if (canRemove) {
                const removeItem = document.createElement('div');
                removeItem.className = 'menu-item remove-item';
                removeItem.innerHTML = '<span class="menu-icon">🚪</span> Исключить';
                removeItem.addEventListener('click', (e) => {
                    e.stopPropagation();
                    removeMemberFromGroup(groupId, username);
                    menu.remove();
                });
                menu.appendChild(removeItem);
            }
            
            // Если нет ни одного пункта меню, не показываем его
            if (menu.children.length === 0) {
                return;
            }
            
            document.body.appendChild(menu);
            
            // Закрытие при клике вне меню
            const closeHandler = (e) => {
                if (!menu.contains(e.target) && !e.target.classList.contains('member-actions-btn')) {
                    menu.remove();
                    document.removeEventListener('click', closeHandler);
                }
            };
            
            document.addEventListener('click', closeHandler);
        },
    };

    GroupRoles.init();

    async function renameGroup(groupId, newName) {
    try {
        const res = await fetch('/rename_group', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify({
            group_id: groupId,
            new_name: newName
        })
        });

        if (!res.ok) {
        const error = await res.json();
        throw new Error(error.error || 'Ошибка при изменении названия');
        }

        // Обновляем интерфейс
        if (currentGroup === groupId) {
        UI.currentGroupName.textContent = newName;
        }
        
        // Обновляем список групп
        await loadGroups();
        showToast('Название группы успешно изменено', 'success');

    } catch (error) {
        console.error("Rename group error:", error);
        showToast(error.message, 'error');
    }
    }

    window.removeMemberFromGroup = async function(groupId, username) {
    const confirmed = await showConfirmation(
        "Исключить участника", 
        `Вы уверены, что хотите исключить ${username} из группы? Это действие нельзя отменить.`
    );
    
    if (confirmed) {
        try {
        const res = await fetch('/remove_from_group', {
            method: 'POST',
            headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${localStorage.getItem('token')}`
            },
            body: JSON.stringify({
            group_id: groupId,
            username: username
            })
        });
        
        const data = await res.json();
        if (!res.ok) {
            throw new Error(data.error || 'Ошибка при исключении');
        }
        
        await loadParticipants();
        showToast(`Пользователь ${username} исключен из группы`, 'success');
        
        if (data.is_current_user) {
            currentGroup = null;
            sessionStorage.removeItem('currentChat');
            UI.currentGroupName.textContent = 'Общий чат';
            UI.chatBox.innerHTML = '';
            lastTimestamp = 0;
            loadMessages();
            await loadGroups();
        }
        } catch (error) {
        console.error("Remove member error:", error);
        showToast(error.message, 'error');
        }
    }
    };

    let lastGroupsCount = 0;

    async function checkGroupsUpdates() {
        try {
            const res = await fetch('/get_groups');
            const data = await res.json();
            
            if (data.length > lastGroupsCount && lastGroupsCount > 0) {
                // Новая группа появилась
                playSoundEffect();
                showToast('У вас новая группа!', 'success');
            }
            
            lastGroupsCount = data.length;
        } catch (e) {
            console.error('Groups count check error:', e);
        }
    }

});

