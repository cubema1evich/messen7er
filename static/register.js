document.addEventListener("DOMContentLoaded", function () {
    const registerForm = document.getElementById("register-form");

    registerForm.addEventListener("submit", function (e) {
        e.preventDefault();
        
        const username = document.getElementById("username").value.trim();
        const password = document.getElementById("password").value;

        if (!username || !password) {
            alert("Заполните все поля!");
            return;
        }

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
                window.location.href = "/login";
            } else {
                // Парсим JSON с ошибкой
                const errorData = await response.json();
                if (response.status === 400 && errorData.error === 'Username already exists') {
                    alert("Пользователь с таким именем уже существует!");
                } else {
                    throw new Error(errorData.error || 'Ошибка регистрации');
                }
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert(error.message);
        });
    });
});