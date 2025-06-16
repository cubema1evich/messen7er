document.addEventListener("DOMContentLoaded", function () {
    const loginForm = document.getElementById("login-form");
    

    function isValidUsername(username) {
        const regex = /^[a-zA-Zа-яА-Я0-9_-]{3,15}$/u;
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

        loginForm.addEventListener("submit", async function (e) {
        e.preventDefault();
        const username = document.getElementById("username").value.trim();
        const password = document.getElementById("password").value;
        
        if (!isValidUsername(username)) {
            showAlert('Недопустимое имя пользователя');
            return;
        }

        const requestBody = new URLSearchParams({ username, password });

        try {
            const response = await fetch("/login", {
                method: "POST",
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded'
                },
                body: requestBody
            });

            if (!response.ok) {
                const err = await response.json();
                throw new Error(err.error || 'Ошибка при логине');
            }

            const data = await response.json();

            if (data.redirect) {
                sessionStorage.setItem('session_id', data.session_id);
                sessionStorage.setItem('session_key', data.session_key);
                sessionStorage.setItem('username', username);
                window.location.href = data.redirect;
            }


        } catch (error) {
            showAlert(error.message);
        }
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