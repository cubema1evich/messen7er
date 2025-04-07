document.addEventListener("DOMContentLoaded", function () {
    // Проверка авторизации
    const username = sessionStorage.getItem('username');
    if (username) {
        document.getElementById('auth-buttons').style.display = 'none';
        document.getElementById('user-info').classList.add('active');
        document.getElementById('current-user').textContent = username;
        setTimeout(() => selectGroup(null, 'Общий чат'), 100);
    } else {
        document.getElementById('auth-buttons').style.display = 'flex';
        document.getElementById('user-info').classList.remove('active');
    }

        
    let currentGroup = null;
    let currentPrivateChat = null; 
    let lastTimestamp = 0;

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
        clearFilesBtn: document.querySelector('.clear-files-btn')
        //newMemberInput: document.getElementById("new-member-input"),
        //addMemberBtn: document.getElementById("add-member-btn"),
        //leaveGroupBtn: document.getElementById("leave-group-btn"),
    };

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
});

    // Обработчик закрытия сайдбара через крестик
    UI.sidebarClose.addEventListener('click', function(e) {
        e.stopPropagation();
        UI.sidebar.classList.remove('active');
        UI.sidebarToggle.style.display = 'block'; // Показываем кнопку "Группы"
    });

    // Инициализация
    initEmojiPicker();
    loadGroups();
    loadPrivateChats();
    setInterval(() => {
        if (!currentGroup && !currentPrivateChat) { // Для общего чата
            loadMessages();
        }
        if (currentGroup) loadMessages();
        if (currentPrivateChat) loadPrivateMessages();
    }, 500);
    setupEventListeners();

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
                url = `/get_private_messages?user=${currentPrivateChat}&${params}`;
            } else {
                url = `/get_messages?${params}`;
            }
    
            const res = await fetch(url);
            
            if (res.status === 404) {
                window.location.href = '/404';
                return;
            }
            if (res.status === 403) {
                window.location.href = '/403';
                return;
            }
            if (res.status === 500) {
                window.location.href = '/500';
                return;
            }
            
            if (!res.ok) {
                const errorData = await res.json().catch(() => ({}));
                throw new Error(errorData.error || `HTTP error! status: ${res.status}`);
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
            if (error.message.includes('404')) {
                window.location.href = '/404';
            } else if (error.message.includes('403')) {
                window.location.href = '/403';
            } else {
                window.location.href = '/500';
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
    
        sortedMessages.forEach(msg => {
            const messageId = msg.id || msg.timestamp;
            const existingMessage = chatBox.querySelector(`[data-id="${messageId}"]`);
    
            if (!existingMessage) {
                const messageElement = document.createElement("div");
                messageElement.className = "message" + (msg.temp ? " temp" : "");
                messageElement.dataset.id = messageId;
                messageElement.dataset.timestamp = msg.timestamp;
    
                const timeOptions = { hour: '2-digit', minute: '2-digit', hour12: false };
                const date = new Date(msg.timestamp * 1000);
                const time = isNaN(date) ? '--:--' : date.toLocaleTimeString([], timeOptions);
    
                // HTML структура сообщения
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
    
                chatBox.appendChild(messageElement);
            }
        });
    
        // Прокрутка после обновления
        requestAnimationFrame(() => {
            if (wasScrolledToBottom) {
                chatBox.scrollTo({
                    top: chatBox.scrollHeight,
                    behavior: 'smooth'
                });
            }
        });
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
            const res = await fetch('/get_groups');
            const groups = await res.json();
            
            UI.groupsList.innerHTML = `
                <div class="group-item ${!currentGroup ? 'active' : ''}" 
                     onclick="selectGroup(null, 'Общий чат', this)">
                    Общий чат
                </div>
                ${groups.map(group => `
                    <div class="group-item" 
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
                    alert("Пользователь успешно добавлен!");
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
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ group_id: groupId })
                });
        
                if (res.ok) {
                    currentGroup = null;
                    UI.currentGroupName.textContent = '';
                    loadGroups();
                    loadMessages();
                    alert("Вы успешно покинули группу");
                }
            } catch (error) {
                console.error("Error leaving group:", error);
            }
        }
    }

        
    window.selectGroup = (groupId, groupName, element) => {
        currentGroup = groupId;
        currentPrivateChat = null; 
        UI.currentGroupName.textContent = groupName || 'Общий чат';
        UI.chatBox.innerHTML = '';
        lastTimestamp = 0;
        document.querySelector('.attachment-container')?.remove();
        loadGroups(); 
        loadMessages();
    };



    function setupEventListeners() {
        UI.createGroupBtn.addEventListener("click", createGroup);
        
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
            // Создаем временное сообщение только если есть что показать
            if (message || files.length > 0) {
                const tempMessage = {
                    id: tempId,
                    sender: username,
                    message_text: message,
                    timestamp: Math.floor(Date.now()/1000),
                    temp: true,
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
            
            // Добавляем файлы только если они есть
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
                formData.append('group_id', currentGroup.toString());
            }
            else if (currentPrivateChat) {
                formData.append('receiver', currentPrivateChat);
            }
    
            const res = await fetch('/send_message', {
                method: 'POST',
                body: formData
            });
            
            if (!res.ok) throw new Error(await res.text());
    
            const tempElement = UI.chatBox.querySelector(`[data-id="${tempId}"]`);
            if (tempElement) tempElement.remove();
    
            if (currentPrivateChat) {
                await loadPrivateChats();
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

    // Новые функции
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
            const res = await fetch('/get_private_chats');
            if (!res.ok) throw new Error('Network error');
            const data = await res.json();
            console.log('Private chats data:', data);
            renderPrivateChats(data.chats || []); 
        } catch (error) {
            console.error("Error loading private chats:", error);
        }
    }

    function renderPrivateChats(chats) {
        UI.privateChatsList.innerHTML = chats.map(chat => `
            <div class="chat-item" onclick="selectPrivateChat('${chat.username}')">
                <span>${chat.username}</span>
                <small>${new Date(chat.last_activity * 1000).toLocaleTimeString([], { 
                    hour: '2-digit', 
                    minute: '2-digit',
                    day: 'numeric',
                    month: 'short'
                })}</small>
            </div>
        `).join('');
    }

    window.selectPrivateChat = selectPrivateChat;

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


});
