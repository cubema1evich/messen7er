document.addEventListener("DOMContentLoaded", function () {
    // Проверка авторизации
    const username = sessionStorage.getItem('username');
    if (username) {
        document.getElementById('current-user').textContent = sessionStorage.getItem('username');
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
        addMemberBtn: document.getElementById("add-member-btn")
    };

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
        emojiPicker.addEventListener("click", function (event) {
            if (event.target.tagName === "SPAN") {
                const emoji = event.target.innerText;
                messageInput.value += emoji;
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
                displayMessages(data.messages);
                lastTimestamp = data.timestamp;
            }
        } catch (error) {
            console.error("Error loading messages:", error);
        }
    }

    function displayMessages(messages) {
        UI.chatBox.innerHTML = messages.map(msg => `
            <div class="message">
                <div class="sender">${msg.sender}</div>
                <p>${msg.message_text}</p>
            </div>
        `).join('');
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
            
            UI.groupsList.innerHTML = groups.map(group => `
                <div class="group-item" data-group-id="${group.id}" 
                     onclick="selectGroup(${group.id}, '${group.name}')">
                    ${group.name}
                </div>
            `).join('');
        } catch (error) {
            console.error("Error loading groups:", error);
        }
    }

    window.selectGroup = (groupId, groupName) => {
    currentGroup = groupId;
    UI.currentGroupName.textContent = groupName;
    UI.chatBox.innerHTML = ''; // Очищаем чат
    lastTimestamp = 0; // Сбрасываем таймстамп
    loadMessages(); // Загружаем сообщения для группы
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