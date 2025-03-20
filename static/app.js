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
        sidebarClose: document.getElementById('sidebar-close')
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
    setInterval(loadMessages, 1000);
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
            const url = currentGroup 
                ? `/get_group_messages?group_id=${currentGroup}&timestamp=${lastTimestamp}`
                : `/get_messages?timestamp=${lastTimestamp}`;
            
            const res = await fetch(url);
            const data = await res.json();
            
            if(data.messages.length > 0) {
                if(lastTimestamp === 0) {
                    UI.chatBox.innerHTML = ''; // Очищаем только при первой загрузке
                }
                displayMessages(data.messages);
                lastTimestamp = data.timestamp; // Важно обновить timestamp
            }
        } catch (error) {
            console.error("Error loading messages:", error);
        }
    }

    function displayMessages(messages) {
        const chatBox = UI.chatBox;
    
        messages.forEach(msg => {
            // Проверяем, есть ли уже такое сообщение в чате
            const existingMessage = Array.from(chatBox.children).find(
                element => element.dataset.messageId === msg.id
            );
    
            // Если сообщение новое, добавляем его
            if (!existingMessage) {
                const messageElement = document.createElement("div");
                messageElement.classList.add("message");
                messageElement.dataset.messageId = msg.id; // Добавляем уникальный идентификатор
    
                const senderElement = document.createElement("div");
                senderElement.classList.add("sender");
                senderElement.textContent = msg.sender;
    
                const textElement = document.createElement("p");
                textElement.textContent = msg.message_text;
    
                messageElement.appendChild(senderElement);
                messageElement.appendChild(textElement);
    
                chatBox.appendChild(messageElement);
            }
        });
        const isScrolledUp = chatBox.scrollTop + chatBox.clientHeight < chatBox.scrollHeight - 100;
    
        if (!isScrolledUp) {
            chatBox.scrollTop = chatBox.scrollHeight;
        }

        requestAnimationFrame(() => {
            chatBox.scrollTo({
                top: chatBox.scrollHeight,
                behavior: 'smooth'
            });
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
        UI.currentGroupName.textContent = groupName || 'Общий чат';
        
        // Удаляем active class у всех элементов
        document.querySelectorAll('.group-item').forEach(item => {
            item.classList.remove('active');
        });
        
        // Добавляем active class выбранному элементу
        if(element) {
            element.classList.add('active');
        }
        
        // Очищаем чат перед загрузкой новых сообщений
        UI.chatBox.innerHTML = '';
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
            const res = await fetch('/send_message', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    message: message,
                    group_id: currentGroup
                })
            });
            
            if (res.ok) {
                UI.messageInput.value = '';
            }
        } catch (error) {
            console.error("Error sending message:", error);
        }
    }
});