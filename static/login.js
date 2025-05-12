document.addEventListener("DOMContentLoaded", function () {
    const loginForm = document.getElementById("login-form");

    function isValidUsername(username) {
        const regex = /^[a-zA-Zа-яА-Я0-9_-]{3,20}$/u;
        return regex.test(username);
    }

    function showAlert(message, type = 'error') {
        const container = document.getElementById('alerts-container');
        const alert = document.createElement('div');
        
        alert.className = `alert alert-${type}`;
        alert.innerHTML = `
            <span class="alert-icon">${type === 'error' ? '⚠' : '✅'}</span>
            <span class="alert-text">${message}</span>
        `;
        container.appendChild(alert);
        
        setTimeout(() => {
            alert.remove();
        }, 5000);
    }

    loginForm.addEventListener("submit", function (e) {
        e.preventDefault();
        const username = document.getElementById("username").value.trim();
        const password = document.getElementById("password").value;

        if (!isValidUsername(username)) {
            showAlert('Имя пользователя может содержать только:<br>• Буквы (рус/англ)<br>• Цифры<br>• Дефисы и подчеркивания<br>• Длину от 3 до 20 символов');
            return;
        }

        fetch("/login", {
            method: "POST",
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded'
            },
            body: new URLSearchParams({ username, password })
        })
        .then(response => {
            if (!response.ok) {
                return response.json().then(err => Promise.reject(err));
            }
            return response.json();
        })
        .then(data => {
            if (data.redirect) {
                window.location.href = data.redirect;
            }
        })
        .catch(error => {
            const message = error.error || 'Ошибка соединения с сервером';
            showAlert(message);
        });
    });
});
            
    function getUserId(username) {
        fetch('/get_user_id')
            .then(response => response.json())
            .then(data => {
                sessionStorage.setItem('username', username);
                if (data.redirect) {
                    window.location.replace(data.redirect);
                }
            })
            .catch(error => {
                console.error("Error fetching user_id:", error);
            });
    }
