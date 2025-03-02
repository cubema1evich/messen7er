document.addEventListener("DOMContentLoaded", function () {
    const chatBox = document.getElementById("chat-box");
    const messageForm = document.getElementById("message-form");
    const messageInput = document.getElementById("message-input");
    const emojiButton = document.getElementById("emoji-button");
    const emojiPicker = document.getElementById("emoji-picker");

    const emojiList = [
        '😁', '😂', '😃', '😄', '😅', '😆', '😇', '😈', '😉', '😊',
        '😋', '😌', '😍', '😎', '😏', '😐', '😒', '😓', '😔', '😖',
        '😘', '😚', '😜', '😝', '😞', '😠', '😡', '😢', '😣', '😤',
        '😥', '😨', '😩', '😪', '😫', '😭', '😰', '😱', '👍', '🎉',
        '❤️', '😸', '😹', '😺', '😻', '😼', '😽', '😾', '😿', '🙀',
        '💩', '👴', '🙅', '🙆', '🙇', '🙈', '🙉', '🙊', '🙋', '🙌',
        '🙍', '🙎', '🙏', '🐌', '🐍', '🐎', '🐑', '🐒', '🐔', '🐗'
    ];

    const emojisPerRow = 10;

    emojiList.forEach((emoji, index) => {
        const emojiSpan = document.createElement('span');
        emojiSpan.innerText = emoji;
        emojiPicker.appendChild(emojiSpan);

        if ((index + 1) % emojisPerRow === 0) {
            const breakElement = document.createElement('br');
            emojiPicker.appendChild(breakElement);
        }
    });

    emojiButton.addEventListener("click", function () {
        emojiPicker.classList.toggle("show");
    });

    emojiPicker.addEventListener("click", function (event) {
        if (event.target.tagName === "SPAN") {
            const emoji = event.target.innerText;
            messageInput.value += emoji;
        }
        emojiPicker.classList.remove("show");
    });

    let lastTimestamp = 0;

    function getMessages() {
        fetch(`/get_messages?timestamp=${lastTimestamp}`)
            .then((response) => response.json())
            .then((data) => {
                console.log("Received data from server:", data);
                if (data && data.messages) {
                    data.messages.forEach((message) => {
                        if (message.message_text && message.sender) {
                            addMessage(message, message.sender);
                        }
                    });
                }
                lastTimestamp = data.timestamp || lastTimestamp;
            })
            .catch((error) => {
                console.error("Error getting messages:", error);
            });
    }

    function addMessage(message, sender) {
        console.log("Adding message:", message, "from sender:", sender);
    
        if (message && message.message_text && sender) {
            const messageDiv = document.createElement("div");
            messageDiv.className = "message";
            const messageText = document.createElement("p");
    
            const displaySender = sender || 'Guest';
            const displayMessage = message.message_text || '';
    
            console.log("Displaying:", displaySender, displayMessage);
    
            const senderDiv = document.createElement("div");
            senderDiv.className = "sender";
            senderDiv.innerText = displaySender;
            messageDiv.appendChild(senderDiv);
    
            messageText.innerText = displayMessage;
            messageDiv.appendChild(messageText);
    
            chatBox.appendChild(messageDiv);
        }
    }
    
    messageForm.addEventListener("submit", function (e) {
        e.preventDefault();
        const message = messageInput.value;

        if (message) {
            const username = sessionStorage.getItem('username');
            addMessage(message, username);
            messageInput.value = "";

            const requestBody = { message, username };
            
            fetch("/send_message", {
                method: "POST",
                body: JSON.stringify({ message, username }), 
                headers: { "Content-Type": "application/json" }, 
            })
            .then((response) => response.json())
            .then((data) => {
                if (data && data.message) {
                    console.log("Server response after sending message:", data.message);
                } else {
                    console.error("Invalid server response:", data);
                }
            })
            .catch((error) => {
                console.error("There was a problem with the fetch operation:", error);
            });
        }
    });

    setInterval(getMessages, 1000);
    // Создание группы
document.getElementById('create-group-btn').addEventListener('click', () => {
    const groupName = prompt('Введите название группы:');
    if (groupName) {
        fetch('/create_group', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name: groupName})
        })
        .then(response => response.json())
        .then(data => loadGroups());
    }
});
async function loadGroups() {
    try {
        const response = await fetch('/get_groups');
        const groups = await response.json();
        console.log("Groups loaded:", groups);
        
        const groupsList = document.getElementById('groups-list');
        groupsList.innerHTML = groups.map(group => `
            <div class="group-item" data-group-id="${group.id}">
                ${group.name}
                <button onclick="loadGroupMembers(${group.id})">Показать участников</button>
            </div>
        `).join('');
    } catch (error) {
        console.error("Error loading groups:", error);
    }
}

// Загрузка списка групп
function loadGroups() {
    fetch('/get_groups')
    .then(response => response.json())
    .then(groups => {
        const groupsList = document.getElementById('groups-list');
        groupsList.innerHTML = groups.map(group => `
            <div class="group-item" data-group-id="${group.id}">
                ${group.name}
                ${group.role === 'owner' ? 
                    '<button class="manage-group-btn">Управление</button>' : ''}
            </div>
        `).join('');
    });
}

    document.addEventListener('click', async (e) => {
        if (e.target.classList.contains('manage-group-btn')) {
            const groupId = e.target.closest('.group-item').dataset.groupId;
            const members = await fetch(`/get_group_members?group_id=${groupId}`)
                .then(res => res.json());
            
            const membersHtml = members.map(member => `
                <div class="member">
                    ${member.username}
                    <select class="role-select" data-user-id="${member.id}">
                        <option ${member.role === 'member' ? 'selected' : ''}>member</option>
                        <option ${member.role === 'admin' ? 'selected' : ''}>admin</option>
                    </select>
                    <button class="remove-member-btn">×</button>
                </div>
            `).join('');
            
            document.getElementById('group-members').innerHTML = membersHtml;
        }
    });
});

let currentGroup = null;

document.addEventListener('click', async (e) => {
    if (e.target.closest('.group-item')) {
        const groupId = e.target.closest('.group-item').dataset.groupId;
        currentGroup = groupId;
        loadGroupMessages(groupId);
    }
});

async function loadGroupMessages(groupId) {
    const response = await fetch(`/get_group_messages?group_id=${groupId}`);
    const data = await response.json();
    displayMessages(data.messages);
}

document.getElementById('send-btn').addEventListener('click', async () => {
    const message = messageInput.value.trim();
    if (message && currentGroup) {
        await fetch('/send_message', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                message,
                group_id: currentGroup
            })
        });
        messageInput.value = '';
    }
});

document.getElementById('add-member-btn').addEventListener('click', async () => {
    const username = document.getElementById('new-member-input').value;
    const role = document.getElementById('new-member-role').value;
    
    const userResponse = await fetch(`/get_user_id?username=${username}`);
    const userData = await userResponse.json();
    
    if (userData.user_id) {
        await fetch('/add_to_group', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                group_id: currentGroup,
                user_id: userData.user_id,
                role: role
            })
        });
        updateMembersList();
    }
});

async function updateMembersList() {
    const response = await fetch(`/get_group_members?group_id=${currentGroup}`);
    const members = await response.json();
    
    const membersHtml = members.map(member => `
        <div class="member">
            ${member.username}
            <select class="member-role" data-user-id="${member.user_id}">
                <option ${member.role === 'member' ? 'selected' : ''}>member</option>
                <option ${member.role === 'admin' ? 'selected' : ''}>admin</option>
            </select>
            <button class="remove-member-btn" data-user-id="${member.user_id}">×</button>
        </div>
    `).join('');
    
    document.getElementById('members-list').innerHTML = membersHtml;
}


const socket = new WebSocket('ws://localhost:8000/ws');

socket.onmessage = (event) => {
    const message = JSON.parse(event.data);
    if (message.type === 'new_group_message') {
        displayMessage(message.data);
    } else if (message.type === 'group_update') {
        loadGroups();
    }
};
