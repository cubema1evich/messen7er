document.addEventListener("DOMContentLoaded", function () {

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
        //newMemberInput: document.getElementById("new-member-input"),
        //addMemberBtn: document.getElementById("add-member-btn"),
        //leaveGroupBtn: document.getElementById("leave-group-btn"),
    };
    
    // Восстановление состояния чата
    const savedChat = JSON.parse(sessionStorage.getItem('currentChat') || 'null');
    if (savedChat) {
        if (savedChat.type === 'group') {
            selectGroup(savedChat.id, savedChat.name);
        } else if (savedChat.type === 'private') {
            selectPrivateChat(savedChat.name);
        }
    } else {
        selectGroup(null, 'Общий чат');
    }

    // Обработчики для правого сайдбара
    UI.membersToggle.addEventListener('click', function(e) {
        e.stopPropagation();
        UI.membersSidebar.classList.toggle('active');
        loadParticipants();
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
        UI.sidebarToggle.style.display = 'block'; // Показываем кнопку "Группы"
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
    // В app.js замените setInterval на это:
    let isTabActive = true;

    window.addEventListener('focus', () => {
        isTabActive = true;
        checkForUpdates();
    });

    window.addEventListener('blur', () => {
        isTabActive = false;
    });

    function checkForUpdates() {
        if (!isTabActive) return;
        
        try {
            // Всегда проверяем обновления интерфейса
            checkInterfaceUpdates();
            
            // Для всех случаев проверяем приватные чаты
            loadPrivateChats();
            
            // Загружаем соответствующие сообщения
            if (currentGroup) {
                loadMessages();
                loadParticipants();
            } else if (currentPrivateChat) {
                loadPrivateMessages();
            } else {
                loadMessages();
            }
            
            // Проверяем измененные/удаленные сообщения
            checkDeletedMessages();
            checkEditedMessages();
            
        } catch (e) {
            console.error('Interval error:', e);
        }
        
        setTimeout(checkForUpdates, 2000);
    }

    checkForUpdates();

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
            let params = `timestamp=${lastTimestamp}`;
            
            if (currentGroup) {
                url = `/get_group_messages?group_id=${currentGroup}&${params}`;
            } else if (currentPrivateChat) {
                url = `/get_private_messages?user=${encodeURIComponent(currentPrivateChat)}&${params}`;
            } else {
                url = `/get_messages?${params}`;
            }
    
            const res = await fetch(url, {
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('token')}`
                }
            });
            
            if (res.status === 401) {
                window.location.href = '/login';
                return;
            }
            
            if (res.status === 403) {
                // Если доступ запрещен, переключаем на общий чат
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
            
            const data = await res.json();
            
            if (lastTimestamp === 0) {
                UI.chatBox.innerHTML = '';
            }
            
            if(data.messages.length > 0) {
                displayMessages(data.messages);
                lastTimestamp = data.timestamp;
            }
        } catch (error) {
            console.error("Error loading messages:", error);
            
            if (error.message.includes('403') && currentGroup) {
                // Если доступ к группе запрещён, переключаем на общий чат
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
    
        const existingMenu = document.querySelector('.context-menu');
        if (existingMenu) existingMenu.remove();
    
        const contextMenu = document.createElement('div');
        contextMenu.className = 'context-menu';
        contextMenu.style.left = `${rect.left}px`;
        contextMenu.style.top = `${rect.bottom}px`;
        contextMenu.innerHTML = `
        <div class="context-menu-item" data-action="edit">
            <span class="menu-icon">✏️</span>
            Редактировать
        </div>
        <div class="context-menu-item" data-action="delete">
            <span class="menu-icon">🗑️</span>
            Удалить
        </div>
    `;
    
        document.body.appendChild(contextMenu);
        contextMenu.style.display = 'block';
    
        contextMenu.querySelectorAll('.context-menu-item').forEach(item => {
            item.addEventListener('click', (e) => {
                handleContextMenuAction(e, messageId, messageType);
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
    
    async function handleContextMenuAction(e, messageId, messageType) {
        const action = e.target.dataset.action;
        const messageElement = document.querySelector(`[data-id="${messageId}"]`);
        
        if (!messageElement) {
            console.error('Message element not found');
            return;
        }
    
        if (action === 'delete') {
            await deleteMessageById(messageId, messageType);
        } else if (action === 'edit') {
            enableMessageEditing(messageElement, messageId, messageType);
        }
    }
    
    async function deleteMessageById(messageId, messageType) {
        if (!confirm("Удалить сообщение?")) return;
        
        try {
            const res = await fetch(`/delete_message/${messageId}?type=${messageType}`, {
                method: 'DELETE',
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('token')}`
                }
            });
            
            if (res.ok) {
                const messageElement = document.querySelector(`[data-id="${messageId}"]`);
                if (messageElement) {
                    messageElement.remove();
                }
            } else {
                const error = await res.json();
                throw new Error(error.error || 'Ошибка удаления');
            }
        } catch (error) {
            console.error("Ошибка удаления:", error);
            alert('Ошибка при удалении сообщения: ' + error.message);
        }
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
                            timestamp: Math.floor(Date.now()/1000) // Добавляем текущий timestamp
                        })
                    });
                    
                    if (res.ok) {
                        textElement.textContent = newText;
                        messageElement.dataset.timestamp = Math.floor(Date.now()/1000); // Обновляем timestamp
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
            // Проверяем обновления групп
            const lastCheck = parseInt(sessionStorage.getItem('groupsLastCheck') || '0');
        
            // Проверяем обновления групп с передачей последнего времени проверки
            const groupsRes = await fetch(`/check_groups_updates?last_check=${lastCheck}`);
            if (groupsRes.ok) {
                const data = await groupsRes.json();
                if (data.updated) {
                    // Сохраняем новое время проверки
                    sessionStorage.setItem('groupsLastCheck', data.new_timestamp || Date.now());
                    
                    // Принудительно обновляем список групп
                    await loadGroups();
                    
                    if (currentGroup) {
                        await loadParticipants();
                        await loadMessages();  // Также обновляем сообщения
                    }
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
                // Удаляем сообщения, которых нет в ответе сервера
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
        const groupName = prompt("Введите название группы:");
        if (!groupName) return;
    
        try {
            const res = await fetch('/create_group', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ name: groupName })
            });
            
            if (res.status === 400) {
                const error = await res.json();
                alert(error.error);
                return;
            }
            
            if (res.ok) {
                loadGroups();
                alert("Группа создана успешно!");
            }
        } catch (error) {
            console.error("Error creating group:", error);
            alert("Ошибка при создании группы");
        }
    }

    async function loadGroups() {
        try {
            const res = await fetch('/get_groups', {
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('token')}`,
                    'Cache-Control': 'no-cache'
                }
            });
            
            if (res.status === 401) {
                window.location.href = '/login';
                return;
            }
            
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            
            const groups = await res.json();
            
            // Сохраняем текущую активную группу
            const activeGroupId = currentGroup;
            
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
                            <button class="group-actions-btn" onclick="toggleGroupMenu(event, ${group.id})">⋮</button>
                            <div class="group-actions-menu" id="group-menu-${group.id}">
                                <button class="group-action" onclick="addMemberPrompt(${group.id})">Добавить участника</button>
                                <button class="group-action" onclick="leaveGroupPrompt(${group.id})">Покинуть группу</button>
                            </div>
                        </div>
                    </div>
                `).join('')}
            `;
        } catch (error) {
            console.error("Error loading groups:", error);
            if (error.message.includes('401')) {
                window.location.href = '/login';
            } else {
                UI.groupsList.innerHTML = '<div class="error">Ошибка загрузки групп</div>';
            }
        }
    }
    
    // Новые функции управления группами
    window.toggleGroupMenu = function(event, groupId) {
        event.stopPropagation();
        const menu = document.getElementById(`group-menu-${groupId}`);
        menu.classList.toggle('show');
    }
    
    window.addMemberPrompt = async function(groupId) {
        const username = prompt("Введите имя пользователя для добавления:");
        if (username) {
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
                    const data = await res.json();
                    alert("Пользователь успешно добавлен!");
                    
                    // Принудительно обновляем интерфейс
                    await loadGroups();
                    await loadParticipants();
                    
                    // Если мы в этой группе, обновляем сообщения
                    if (currentGroup === groupId) {
                        await loadMessages();
                    }
                }
            } catch (error) {
                console.error("Error adding member:", error);
                alert("Ошибка при добавлении пользователя");
            }
        }
    }
    
    window.leaveGroupPrompt = async function(groupId) {
        if (confirm("Вы уверены, что хотите покинуть группу?")) {
            try {
                const res = await fetch('/leave_group', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${localStorage.getItem('token')}`
                    },
                    body: JSON.stringify({ group_id: groupId })
                });
                
                if (!res.ok) {
                    const error = await res.json().catch(() => ({}));
                    throw new Error(error.error || 'Ошибка при выходе из группы');
                }
    
                // Если мы находимся в этой группе, переключаем на общий чат
                if (currentGroup === groupId) {
                    currentGroup = null;
                    sessionStorage.removeItem('currentChat');
                    UI.currentGroupName.textContent = 'Общий чат';
                    UI.chatBox.innerHTML = '';
                    lastTimestamp = 0;
                }
                
                // Обновляем список групп
                await loadGroups();
                
                // Загружаем сообщения (либо общий чат, либо текущий чат)
                if (currentGroup === null) {
                    await loadMessages();
                }
    
            } catch (error) {
                console.error("Ошибка выхода:", error);
                alert(error.message || 'Ошибка соединения с сервером');
                
                // В любом случае переключаем на общий чат
                currentGroup = null;
                sessionStorage.removeItem('currentChat');
                UI.currentGroupName.textContent = 'Общий чат';
                loadGroups();
                loadMessages();
            }
        }
    }

        
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
        loadGroups();
        loadMessages();
        loadPrivateChats();
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
    
    async function sendMessage(e) {
        e.preventDefault();
        const message = UI.messageInput.value.trim();
        const files = UI.fileInput.files;
        
        if (!message && files.length === 0) {
            clearFiles(); 
            return;
        }
    
        const tempId = Date.now();
        
        try {
            // Показываем временное сообщение
            if (message || files.length > 0) {
                const tempMessage = {
                    id: tempId,
                    sender: username,
                    message_text: message,
                    timestamp: Math.floor(Date.now()/1000),
                    temp: true,
                    type: currentPrivateChat ? 'private' : (currentGroup ? 'group' : 'general'),
                    attachments: Array.from(files).map(file => ({
                        filename: file.name,
                        mime_type: file.type,
                        path: URL.createObjectURL(file)
                    }))
                };
                
                displayMessages([tempMessage]);
            }
    
            const formData = new FormData();
            if (message) formData.append('message', message);
            
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
    
            // ОБНОВЛЯЕМ СПИСОК ЧАТОВ ПОСЛЕ УСПЕШНОЙ ОТПРАВКИ
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
            
            if(data.messages?.length > 0) {
                // Сохраняем позицию прокрутки
                const prevScrollHeight = UI.chatBox.scrollHeight;
                
                displayMessages(data.messages);
                
                // Плавная прокрутка только для новых сообщений
                if(data.messages.some(msg => msg.timestamp > lastTimestamp)) {
                    UI.chatBox.scrollTo({
                        top: UI.chatBox.scrollHeight,
                        behavior: 'smooth'
                    });
                }
                
                lastTimestamp = data.timestamp;
            }
        } catch (error) {
            console.error("Error loading private messages:", error);
        }
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
            
            if (currentPrivateChat) {
                const chatExists = data.chats.some(c => c.username === currentPrivateChat);
                if (!chatExists) {
                    selectGroup(null, 'Общий чат');
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
            
            // Всегда добавляем текущий чат, если он активен
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
            .then(data => {
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
        try {
            let url;
            if (currentGroup) {
                url = `/get_group_members?group_id=${currentGroup}`;
            } else {
                url = '/get_general_chat_members';
            }
            
            const res = await fetch(url);
            const data = await res.json();
            
            UI.membersList.innerHTML = data.members
            .map(m => `
                <div class="member-item" onclick="handleMemberClick('${m}')">
                    <div class="member-avatar">${m[0].toUpperCase()}</div>
                    <span class="member-name">${m}</span>
                    <div class="member-status ${Math.random() > 0.3 ? 'online' : 'offline'}"></div>
                </div>
            `).join('');
                
        } catch (error) {
            console.error("Error loading participants:", error);
        }
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
});
