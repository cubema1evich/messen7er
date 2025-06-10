import os
import base64
import json

from urllib.parse import parse_qs
from webob import Request
from models.UserModel import *
from utils import *
from .base import json_response, TemplateView
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from utils.pswd_utils import load_rsa_keys

private_key, public_key = load_rsa_keys()

class RegisterView(TemplateView):
    template = 'templates/register.html'

    def response(self, environ, start_response):
        request = Request(environ)
        if request.method == 'POST':
            post_data = request.POST
            username = post_data.get('username', '').strip()
            password = post_data.get('password', '')

            success, error = UserModel.create_user(username, password)
            
            if success:
                return json_response(
                    {'message': 'Регистрация прошла успешно!'},
                    start_response
                )
            else:
                return json_response(
                    {'error': error},
                    start_response,
                    '400 Bad Request' if 'уже существует' in error else '500 Internal Server Error'
                )

        return super().response(environ, start_response)


class LoginView(TemplateView):
    template = 'templates/login.html'

    def response(self, environ, start_response):
        if environ['REQUEST_METHOD'] == 'POST':
            request = Request(environ)
            post_data = parse_qs(request.body.decode('utf-8'))
            username = post_data.get('username', [''])[0].strip()
            password = post_data.get('password', [''])[0]

            user_id, error = UserModel.authenticate(username, password)
            if user_id:
                # Генерируем сеансовый ключ (32 байта для AES-256)
                session_key = os.urandom(32)
                
                # Шифруем сеансовый ключ с помощью приватного ключа RSA
                encrypted_session_key = public_key.encrypt(
                    session_key,
                    padding.OAEP(
                        mgf=padding.MGF1(algorithm=hashes.SHA256()),
                        algorithm=hashes.SHA256(),
                        label=None
                    )
                )
                 
                # Кодируем в base64 для передачи
                encrypted_session_key_b64 = base64.b64encode(encrypted_session_key).decode('utf-8')
                
                # Кодируем уже расшифрованный ключ
                session_key_b64 = base64.b64encode(session_key).decode('utf-8')
                headers = [
                    ('Content-Type', 'application/json'),
                    ('Set-Cookie', f'user_id={user_id}; Path=/; HttpOnly; SameSite=Lax'),
                    ('Set-Cookie', f'session_key={session_key_b64}; Path=/; HttpOnly; SameSite=Lax')  # Кладём расшифрованный ключ!
                ]
                
                data = json.dumps({
                    'redirect': '/',
                    'session_key': encrypted_session_key_b64
                })
                
                start_response('200 OK', headers)
                return [data.encode('utf-8')]
            else:
                return json_response(
                    {'error': error},
                    start_response,
                    '401 Unauthorized'
                )
        return super().response(environ, start_response)