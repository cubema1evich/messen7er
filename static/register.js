document.addEventListener("DOMContentLoaded", function () {
    const registerForm = document.getElementById("register-form");
    const usernameInput = document.getElementById("username");
    const passwordInput = document.getElementById("password");

    function showAlert(message, type = 'error') {
        const container = document.getElementById('alerts-container');
        const alert = document.createElement('div');
        alert.className = `alert ${type}`;
        
        // Иконки
        const icons = {
            error: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                      <path d="M12 9v3m0 0v3m0-3h3m-3 0H9m12 0a9 9 0 11-18 0 9 9 0 0118 0z"/>
                    </svg>`,
            success: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                       <path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
                     </svg>`
        };
    
        alert.innerHTML = `
            <span class="alert-icon">${icons[type]}</span>
            ${message}
        `;
        
        container.prepend(alert);
        
        setTimeout(() => {
            alert.style.opacity = '0';
            setTimeout(() => alert.remove(), 300);
        }, 4000);
    }

    function isValidUsername(username) {
        const regex = /^[a-zA-Zа-яА-Я0-9_-]{3,15}$/u;
        return regex.test(username);
    }

    function validateForm(username, password) {
        // 1 Очистка предыдущих ошибок
        usernameInput.classList.remove('input-error');
        passwordInput.classList.remove('input-error');

        let isValid = true;

        if (!username) {
            showAlert('Пожалуйста, введите имя пользователя');
            usernameInput.classList.add('input-error');
            isValid = false;
        } else if (!isValidUsername(username)) {
            showAlert('Имя может содержать только буквы, цифры, дефисы и подчёркивания (3-15 символов)');
            usernameInput.classList.add('input-error');
            isValid = false;
        }

        if (!password) {
            showAlert('Пожалуйста, введите пароль');
            passwordInput.classList.add('input-error');
            isValid = false;
        } else if (password.length < 6) {
            showAlert('Пароль должен быть не менее 6 символов');
            passwordInput.classList.add('input-error');
            isValid = false;
        }

        return isValid;
    }

    registerForm.addEventListener("submit", function (e) {
        e.preventDefault();
        
        const username = usernameInput.value.trim();
        const password = passwordInput.value;

        // Очищаем предыдущие уведомления
        document.getElementById('alerts-container').innerHTML = '';

        if (!validateForm(username, password)) return;

        const requestBody = new URLSearchParams({ username, password });

        fetch('/register', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded'
            },
            body: requestBody
        })
        .then(async response => {
            if (response.ok) {
                showAlert('Регистрация прошла успешно! Перенаправление...', 'success');
                setTimeout(() => window.location.href = "/login", 1500);
            } else {
                const errorData = await response.json();
                showAlert(errorData.error || 'Ошибка регистрации');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showAlert('Ошибка соединения с сервером');
        });
    });
});