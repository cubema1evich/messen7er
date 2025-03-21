document.addEventListener("DOMContentLoaded", function () {
    // Проверка авторизации
    const username = sessionStorage.getItem('username');
    if (username) {
        document.getElementById('auth-buttons').style.display = 'none';
        document.getElementById('user-info').classList.add('active');
        document.getElementById('current-user').textContent = username;
    } else {
        document.getElementById('auth-buttons').style.display = 'flex';
        document.getElementById('user-info').classList.remove('active');
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
        privateChatList: document.getElementById('private-chat-list'),
        searchUserInput: document.getElementById('search-user-input'),
        startChatBtn: document.getElementById('start-chat-btn'),
        currentChatInfo: document.getElementById('current-chat-info')
        //newMemberInput: document.getElementById("new-member-input"),
        //addMemberBtn: document.getElementById("add-member-btn"),
        //leaveGroupBtn: document.getElementById("leave-group-btn"),
    };

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


    let currentGroup = null;
    let lastTimestamp = 0;

    // Инициализация
    initEmojiPicker();
    loadGroups();
    setInterval(() => {
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
                messageInput.value += e.target.innerText;
                emojiPicker.classList.remove("show");
            }
        });

    }
    
    async function loadMessages() {
        try {
            let url;
            let params = `timestamp=${lastTimestamp}`;
            
            if (currentGroup) {
                // Групповой чат
                url = `/get_group_messages?group_id=${currentGroup}&${params}`;
            } else if (currentPrivateChat) {
                // Личный чат
                url = `/get_private_messages?user=${currentPrivateChat}&${params}`;
            } else {
                // Общий чат
                url = `/get_messages?${params}`;
            }
    
            const res = await fetch(url);
            const data = await res.json();
            
            if(data.messages.length > 0) {
                if(lastTimestamp === 0) {
                    UI.chatBox.innerHTML = '';
                }
                displayMessages(data.messages);
                lastTimestamp = data.timestamp;
            }
        } catch (error) {
            console.error("Error loading messages:", error);
        }
    }
    function displayMessages(messages) {
        const chatBox = UI.chatBox;
        
        messages.forEach(msg => {
            const existingMessage = Array.from(chatBox.children).find(
                element => element.dataset.timestamp === msg.timestamp.toString()
            );
    
            if (!existingMessage) {
                const messageElement = document.createElement("div");
                messageElement.classList.add("message");
                messageElement.dataset.timestamp = msg.timestamp;
    
                const senderElement = document.createElement("div");
                senderElement.classList.add("sender");
                senderElement.textContent = msg.sender;
    
                const textElement = document.createElement("p");
                textElement.textContent = msg.message_text;  // Используем правильное поле
    
                messageElement.appendChild(senderElement);
                messageElement.appendChild(textElement);
                chatBox.appendChild(messageElement);
            }
        });
    
        if (messages.length > 0) {
            chatBox.scrollTo({
                top: chatBox.scrollHeight,
                behavior: 'smooth'
            });
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
        currentPrivateChat = null; // Сбрасываем личный чат
        UI.currentGroupName.textContent = groupName || 'Общий чат';
        UI.chatBox.innerHTML = ''; // Очищаем чат
        lastTimestamp = 0;
        loadMessages();
    };



    function setupEventListeners() {
        UI.messageForm.addEventListener("submit", sendMessage);
        UI.createGroupBtn.addEventListener("click", createGroup);
        
        document.addEventListener('click', function(e) {
            document.querySelectorAll('.group-actions-menu').forEach(menu    => {
                if (!menu.contains(e.target)) {
                    menu.classList.remove('show');
                }
            });
        });
    }

    async function sendMessage(e) {
        e.preventDefault();
        const message = UI.messageInput.value.trim();
        if (!message) return;
    
        try {
            let url, body = {};
            
            if (currentGroup) {
                url = '/send_message';
                body = { message, group_id: currentGroup };
            } else if (currentPrivateChat) {
                url = '/send_private_message';
                body = { 
                    message: message,
                    receiver: currentPrivateChat 
                };
            } else {
                url = '/send_message';
                body = { message };
            }
    
            const res = await fetch(url, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(body)
            });
            
            if (!res.ok) {
                const error = await res.json();
                throw new Error(error.error || 'Ошибка отправки');
            }
            
            UI.messageInput.value = '';
            
            // Добавляем мгновенное отображение сообщения
            const username = sessionStorage.getItem('username');
            const tempMessage = {
                sender: username,
                message_text: message, // Исправлено с message на message_text
                timestamp: Math.floor(Date.now()/1000)
            };
            
            displayMessages([tempMessage]);
            
        } catch (error) {
            console.error('Ошибка:', error);
            alert(error.message);
        }
    }


    const messageInput = document.getElementById('message-input');

    messageInput.addEventListener('input', function () {
        this.style.height = 'auto'; // Сбрасываем высоту
        this.style.height = (this.scrollHeight) + 'px'; // Устанавливаем новую высоту
    });

    // Инициализация высоты при загрузке страницы
    window.addEventListener('load', function () {
        messageInput.style.height = 'auto';
        messageInput.style.height = (messageInput.scrollHeight) + 'px';
    });


        let currentPrivateChat = null;

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
        UI.privateChatList.innerHTML = users.map(user => `
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
    }

    async function loadPrivateMessages() {
        if (!currentPrivateChat) return;
        
        try {
            const res = await fetch(`/get_private_messages?user=${currentPrivateChat}&timestamp=${lastTimestamp}`);
            const data = await res.json();
            
            if(data.messages.length > 0) {
                displayMessages(data.messages);
                lastTimestamp = data.timestamp;
            }
        } catch (error) {
            console.error("Error loading private messages:", error);
        }
    }

    async function startPrivateChat() {
        const username = UI.searchUserInput.value.trim();
        if (!username) return;
        
        selectPrivateChat(username);
        UI.searchUserInput.value = '';
    }
});