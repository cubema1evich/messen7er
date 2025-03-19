document.addEventListener("DOMContentLoaded", function () {
    // Проверка авторизации
    const username = sessionStorage.getItem('username');
    if (username) {
        document.getElementById('user-info').style.display = 'flex';
        document.getElementById('auth-buttons').style.display = 'none';
        document.getElementById('current-user').textContent = username;
    } else {
        document.getElementById('user-info').style.display = 'none';
        document.getElementById('auth-buttons').style.display = 'flex';
    }

    // Элементы интерфейса
    const UI = {
        chatBox: document.getElementById("chat-box"),
        messageForm: document.getElementById("message-form"),
        messageInput: document.getElementById("message-input"),
        createGroupBtn: document.getElementById("create-group-btn"),
        groupsList: document.getElementById("groups-list"),
        currentGroupName: document.getElementById("current-group-name"),
        newMemberInput: document.getElementById("new-member-input"),
        addMemberBtn: document.getElementById("add-member-btn"),
        leaveGroupBtn: document.getElementById("leave-group-btn"),
        sidebarToggle: document.getElementById("sidebar-toggle"), // Новая кнопка
        sidebar: document.querySelector(".sidebar") // Боковая панель
    };

    // Обработчик для кнопки открытия/закрытия боковой панели
    UI.sidebarToggle.addEventListener("click", function () {
        UI.sidebar.classList.toggle("active");
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
        const messageInput = document.getElementById("message-input");

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

        const emojisPerRow = 10; // Количество эмодзи в строке

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

        // Открытие/закрытие пикера эмодзи
        emojiButton.addEventListener("click", function () {
            emojiPicker.classList.toggle("show");
        });

        // Вставка эмодзи в поле ввода
        emojiPicker.addEventListener("click", function(event) {
            if (event.target.tagName === "SPAN") {
                messageInput.value += event.target.innerText;
            }
            emojiPicker.classList.remove("show");
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
    
        // Прокручиваем чат вниз
        chatBox.scrollTop = chatBox.scrollHeight;
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
            
            // Добавляем общий чат первым элементом
            UI.groupsList.innerHTML = `
                <div class="group-item active" onclick="selectGroup(null, 'Общий чат')">
                    Общий чат
                </div>
                ${groups.map(group => `
                    <div class="group-item" 
                         data-group-id="${group.id}" 
                         onclick="selectGroup(${group.id}, '${group.name}')">
                        ${group.name}
                    </div>
                `).join('')}
            `;
        } catch (error) {
            console.error("Error loading groups:", error);
        }
    }

    async function leaveGroup() {
        if (!currentGroup) {
            alert("Сначала выберите группу!");
            return;
        }
    
        if (!confirm("Вы уверены, что хотите покинуть группу?")) return;
    
        try {
            const res = await fetch('/leave_group', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ group_id: currentGroup })
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
        
    window.selectGroup = (groupId, groupName) => {
        currentGroup = groupId;
        UI.currentGroupName.textContent = groupName || 'Общий чат';
    
        // Очищаем чат перед загрузкой новых сообщений
        UI.chatBox.innerHTML = '';
    
        lastTimestamp = 0; // Сбрасываем временную метку
        loadMessages(); // Загружаем сообщения для новой группы
    };

    async function addMember() {
        if (!currentGroup) {
            alert("Сначала выберите группу!");
            return;
        }
        
        const username = UI.newMemberInput.value.trim();
        if (!username) {
            alert("Введите имя пользователя!");
            return;
        }
    
        try {
            const res = await fetch('/add_to_group', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    group_id: currentGroup,
                    username: username,
                    role: 'member'
                })
            });
            
            if (res.ok) {
                UI.newMemberInput.value = '';
                alert("Пользователь успешно добавлен!");
            }
        } catch (error) {
            console.error("Error adding member:", error);
            alert("Ошибка при добавлении пользователя");
        }
    }

    function setupEventListeners() {
        UI.messageForm.addEventListener("submit", sendMessage);
        UI.addMemberBtn.addEventListener("click", addMember);
        UI.createGroupBtn.addEventListener("click", createGroup);
        UI.leaveGroupBtn.addEventListener("click", leaveGroup);
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