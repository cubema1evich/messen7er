document.addEventListener("DOMContentLoaded", function () {
    const registerForm = document.getElementById("register-form");

    registerForm.addEventListener("submit", function (e) {
        e.preventDefault();
        console.log("Form submitted");

        const usernameInput = document.getElementById("username");
        const passwordInput = document.getElementById("password");

        const username = usernameInput.value;
        const password = passwordInput.value;

        const requestBody = new URLSearchParams({ username, password });
        console.log("Request body:", requestBody); // Проверка содержимого запроса

        fetch('/register', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded'
            },
            body: requestBody
        }).then(response => {
            if (response.ok) {
                window.location.href = "/login"; // Успешный редирект
            } else {
                throw new Error('Registration failed');
            }
        }).catch(error => {
            console.error('Error:', error);
            alert("Registration error. Please try again.");
        });
    });
});
