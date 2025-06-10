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

    function base64ToArrayBuffer(base64) {
        // Удаляем все пробелы и переносы строк
        base64 = base64.replace(/[\r\n\s]/g, '');
        const binaryString = window.atob(base64);
        const bytes = new Uint8Array(binaryString.length);
        for (let i = 0; i < binaryString.length; i++) {
            bytes[i] = binaryString.charCodeAt(i);
        }
        return bytes.buffer;
    }

    
    // Функция для расшифровки сеансового ключа
    async function decryptSessionKey(encryptedSessionKey) {
        try {
            // Загружаем приватный ключ (должен быть встроен в клиент)
            const privateKeyPem = `-----BEGIN PRIVATE KEY-----
            MIIEvAIBADANBgkqhkiG9w0BAQEFAASCBKYwggSiAgEAAoIBAQCNWcLJrE+l2YZ/
            2rL+NgeiwVl0hbi5APAJIqGe/JtqEQVtXcByDANjkXRAFC/81NGk+qA2uxbh0zT1
            H/wQ/dd7fWsJciPh+rgxt1wovKc7DvaMAU7lyzBdhakbtDQ5F/byN9lf2dk3AWvZ
            yVXuGumlR8WaA/BabkpRORRcBZHM9OGGqCnK7ltfL589FEOyHzAi55MwNJAYLPvd
            F/VOiYW2VNQtC3jX2hT677kL6C1/aGPo1+x+sr+lKG9s5mYT9vfgfqcSHGlAgxDs
            UbpxmoH/4S3fHctFNeXDhDCh8CJe+ygU5xeXcSKhy7NvZ9qScCKTHmwmZEySn+5H
            iTTA7coXAgMBAAECggEAFq8Q/iG+UR9Xi60ijH6fOxShsSbEk5aoRCRf9jkTt9yD
            bR8JLe7qRvr7bPfQZlgWTM5BEodzufSVyxYW8vh0XEeu+xUWLRh59tXg3v4SLagj
            vil3lT5xGeZup8ODnftP5g87EzwitRvFSG4ccYRgJTt0uq1nJRwN+9BCiYIF+UjA
            0db9GitnniSZwX1nn2jA/lN/Lv1PdcK8tiwarx5w7mhgci4zbNtmmCTfWMdTaA/g
            DJ2b58H3OONOx8jHUnmS/kKMsczD6LLrtpxmWHmIPAx89aXg3V1mbEuRl+gKrvmi
            B5ZGXK6nMXi4cNc6nDF/7t6kyPrACrOXgqwGV+CyAQKBgQC4B9arJiC/wwFcsiRF
            wxyKoim/Rih7530hwokcOEMtNcAwojVliOtLDuMTgOzxYG0LNEvL5rpKfiyBY6aY
            sB1xq+7tqylEH7IfKvos9Q4CyGzfHCpAh9wm5D5thyqzm46dJDem8XLb4wnhepEg
            oesIF6iPLhF8tX/SdMQrY5NJXQKBgQDEoQenghCM1o+PgYvPiVqnJePLi6AbxlAd
            yAoGHsAc/iWsPiWlmmKhuOHBHxILtsnRhVnPdPi9+a5fOgGkOT9teqhh7dwHRFmI
            4++DXzaKX/jkQlzszX17pn5p9xi2YbI68WRTXhUHppz4aMYXMemtKr+j7Ka2zl4b
            ioFP4+7GAwKBgEH/VaYVS2NZ/NAQdt+p5D93fn9BGt2sm/ySdndvWfAJub33Pi0G
            mFNXqGnjL5Y03YZKH/Ck8yQp8a4JXcKeTkDoxwvm+SqcL1XsJMIgtACdfiXZRPHV
            h0dPTXAcLF0zKUcDqQ2uw2FGH9IEEa3hQ5eoXGPUwqK1uHxyMbPZxwVlAoGAPLm+
            s2znz5c0Hw3TL/UrmhOJloM4n1tPwuLUta8phcq3t8o5tjtH2spObmY6HIQHMD4O
            zpNBfuptf9taRm2nuRf4iMX8/gGN5Uj/34K4RWP+agBU0o1kA5wXzoIRj8H8WVfT
            tCuKMyKxt8Yj52Xy1Rgut2GO20ZAqiDMbu/l/iECgYAvM8eHuMWWfp3BQ0do67gt
            aDwxJT7hjZ0Q2Gt4KrwDAh+VYX8viUnc7ADoIW/sd1wtm/uaShblRVGfqpdMoiay
            a3DTUrmqqSgLMmKo/A6MX0GNs11OTun7Vgpe2WeDKeVRySmhETjwwXInuzRj1xnf
            olbY2xNZnLlJHPE1TEvW3Q==
            -----END PRIVATE KEY-----`;
            
            // Импортируем приватный ключ
            const privateKey = await window.crypto.subtle.importKey(
                'pkcs8',
                pemToArrayBuffer(privateKeyPem),
                {
                    name: 'RSA-OAEP',
                    hash: {name: 'SHA-256'}
                },
                true,
                ['decrypt']
            );
            
            console.log("Encrypted session key (Base64):", encryptedSessionKey);
            
            // Расшифровываем сеансовый ключ
            const sessionKey = await window.crypto.subtle.decrypt(
                {
                    name: 'RSA-OAEP'
                },
                privateKey,
                encryptedSessionKey
            );
            
            console.log('Session key length after decrypt:', sessionKey.byteLength); // Логирование длины
            
            return sessionKey;
        } catch (e) {
            console.error('Session key decryption error:', e);
            throw e;
        }
    }

    // Вспомогательные функции
    function pemToArrayBuffer(pem) {
        const base64 = pem.replace(/-{5}[^-]+-{5}/g, '').replace(/\s/g, '');
        return base64ToArrayBuffer(base64);
    }

    // Функция для кодирования ArrayBuffer в base64
    function arrayBufferToBase64(buffer) {
        let binary = '';
        const bytes = new Uint8Array(buffer);
        for (let i = 0; i < bytes.byteLength; i++) {
            binary += String.fromCharCode(bytes[i]);
        }
        return window.btoa(binary);
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
                // Исходно data.session_key – это зашифрованный ключ (256 байт после Base64‑декодирования)
                console.log("Raw session key from server:", data.session_key);

                // Преобразуем из Base64 в ArrayBuffer
                const encryptedSessionKey = base64ToArrayBuffer(data.session_key);
                console.log("Encrypted session key after decoding:", encryptedSessionKey);

                // Расшифровываем сеансовый ключ (должен вернуться ArrayBuffer длиной 32 байта)
                const sessionKey = await decryptSessionKey(encryptedSessionKey);
                console.log("Decrypted session key length:", sessionKey.byteLength);

                // Преобразуем полученный ключ в Base64 для хранения
                const sessionKeyBase64 = arrayBufferToBase64(sessionKey);

                // Сохраняем именно расшифрованный ключ (32 байта) – не зашифрованный RSA‑шифротекст!
                sessionStorage.setItem('session_key', sessionKeyBase64);
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