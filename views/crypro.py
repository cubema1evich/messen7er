import base64
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding  as asym_padding
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from webob import Response
import base64


from webob import Request

import os
import logging
import json

from .base import json_response, View, forbidden_response


# Глобальные переменные
SERVER_PRIVATE_KEY = None
USER_SESSION_KEYS = {}

# Загрузка приватного ключа при старте
def load_private_key():
    global SERVER_PRIVATE_KEY
    with open('server_private.pem', 'rb') as key_file:
        SERVER_PRIVATE_KEY = serialization.load_pem_private_key(
            key_file.read(),
            password=None,
            backend=default_backend()
        )

load_private_key()

class PublicKeyView(View):
    def response(self, environ, start_response):
        project_root = os.path.dirname(os.path.abspath(__file__))
        pubkey_path = os.path.join(project_root, '..', 'server_public.pem')
        with open(pubkey_path, 'r') as f:
            pubkey = f.read()
        res = Response(pubkey, content_type='text/plain')
        return res(environ, start_response)

def encrypt_message_for_user(message, user_id):
    """Шифрует сообщение для конкретного пользователя"""
    try:
        session_key = USER_SESSION_KEYS.get(user_id)
        if not session_key:
            return message  # Возвращаем как есть, если ключа нет
        
        iv = os.urandom(12)  # Генерируем случайный IV
        cipher = Cipher(
            algorithms.AES(session_key),
            modes.GCM(iv),
            backend=default_backend()
        )
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(message.encode('utf-8')) + encryptor.finalize()
        
        return {
            'iv': base64.b64encode(iv).decode('utf-8'),
            'data': base64.b64encode(ciphertext).decode('utf-8'),
            'tag': base64.b64encode(encryptor.tag).decode('utf-8')
        }
    except Exception as e:
        logging.error(f"Encryption error for user {user_id}: {str(e)}")
        return message  # В случае ошибки возвращаем исходное сообщение


class SetSessionKeyView(View):
    def response(self, environ, start_response):
        try:
            request = Request(environ)
            user_id = request.cookies.get('user_id')
            if not user_id:
                return forbidden_response(start_response)
            
            content_length = int(environ.get('CONTENT_LENGTH', 0))
            data = json.loads(environ['wsgi.input'].read(content_length))
            
            encrypted_key = base64.b64decode(data['key'])
            
            # Расшифровываем сессионный ключ
            session_key = SERVER_PRIVATE_KEY.decrypt(
                encrypted_key,
                asym_padding.OAEP(
                    mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            
            # Сохраняем ключ для пользователя
            USER_SESSION_KEYS[user_id] = session_key
            
            return json_response({'status': 'success'}, start_response)
        except Exception as e:
            logging.error(f"SetSessionKey error: {str(e)}")
            return json_response({'error': str(e)}, start_response, '500 Internal Server Error')