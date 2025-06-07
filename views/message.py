from collections import namedtuple
import json
import time
import os 
import logging
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
import base64

from urllib.parse import parse_qs
from mimes import get_mime
from webob import Request
from werkzeug.utils import secure_filename
from utils import *
from .base import View, json_response, forbidden_response
from .crypro import *
from models.MessageModel import *
from models.UserModel import *

SERVER_PRIVATE_KEY = None
USER_SESSION_KEYS = {}


def generate_keys_if_not_exist():
    if not os.path.exists('server_private.pem'):
        # Генерируем приватный ключ
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        
        # Сохраняем приватный ключ
        with open('server_private.pem', 'wb') as f:
            f.write(private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ))
        
        # Сохраняем публичный ключ
        with open('server_public.pem', 'wb') as f:
            f.write(private_key.public_key().public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            ))

# Вызываем перед загрузкой ключа
generate_keys_if_not_exist()

def load_private_key():
    global SERVER_PRIVATE_KEY
    try:
        with open('server_private.pem', 'rb') as key_file:
            SERVER_PRIVATE_KEY = serialization.load_pem_private_key(
                key_file.read(),
                password=None,
                backend=default_backend()
            )
    except Exception as e:
        logging.error(f"Failed to load private key: {str(e)}")
        raise

load_private_key()

class GetMessageView(View):
    def response(self, environ, start_response):
        try:
            request = Request(environ)
            query_params = parse_qs(environ.get('QUERY_STRING', ''))
            timestamp = self._parse_timestamp(query_params)
            user_id = request.cookies.get('user_id')  # Получаем user_id из куки
            
            # Получаем сообщения из модели
            messages = MessageModel.get_general_messages(timestamp)

            # Если запрошено шифрование
            encrypt = query_params.get('encrypt', ['false'])[0] == 'true'
            
            if encrypt and user_id:
                for msg in messages:
                    if 'message_text' in msg:
                        msg['message_text'] = {
                            'encrypted': True,
                            'data': encrypt_message_for_user(msg['message_text'], user_id)
                        }
                
            return json_response({
                'messages': messages,
                'timestamp': self._get_new_timestamp(messages, timestamp)
            }, start_response)
            
        except ValueError as e:
            return json_response({'error': str(e)}, start_response, '400 Bad Request')
        except Exception as e:
            logging.error(f"GetMessageView error: {str(e)}")
            return json_response(
                {'error': 'Internal server error'}, 
                start_response, 
                '500 Internal Server Error'
            )

    def _parse_timestamp(self, query_params):
        try:
            return int(query_params.get('timestamp', ['0'])[0])
        except (ValueError, TypeError):
            raise ValueError("Invalid timestamp format")

    def _get_new_timestamp(self, messages, old_timestamp):
        if messages:
            return max(msg['timestamp'] for msg in messages)
        return old_timestamp

class SendMessageView(View):
    def decrypt_file(self, file_data, session_key):
        try:
            # Первые 12 байт - IV, остальное - зашифрованные данные
            iv = file_data[:12]
            ciphertext = file_data[12:]
            
            cipher = Cipher(
                algorithms.AES(session_key),
                modes.GCM(iv),
                backend=default_backend()
            )
            decryptor = cipher.decryptor()
            return decryptor.update(ciphertext) + decryptor.finalize()
        except Exception as e:
            logging.error(f"File decryption error: {str(e)}")
            return file_data
        
    def decrypt_message(self, encrypted_data, session_key):
        try:
            data = json.loads(encrypted_data)
            iv = base64.b64decode(data['iv'])
            ciphertext = base64.b64decode(data['data'])
            
            # Создаем cipher объект
            cipher = Cipher(
                algorithms.AES(session_key),
                modes.GCM(iv),
                backend=default_backend()
            )
            decryptor = cipher.decryptor()
            
            # Расшифровываем сообщение
            decrypted = decryptor.update(ciphertext) + decryptor.finalize()
            return decrypted.decode('utf-8')
        except Exception as e:
            logging.error(f"Decryption error: {str(e)}")
            return f"[Ошибка расшифровки: {str(e)}]"
    
    def response(self, environ, start_response):
        try:
            request = Request(environ)
            user_id = request.cookies.get('user_id')
            
            if not user_id:
                return forbidden_response(start_response)

            if request.content_type.startswith('multipart/form-data'):
                post_data = request.POST
                files = request.POST.getall('files')
                message = post_data.get('message', '').strip()
            else:
                return json_response(
                    {'error': 'Invalid content type'}, 
                    start_response, 
                    '400 Bad Request'
                )
            
            encrypted_message = post_data.get('message', '')
            session_key = USER_SESSION_KEYS.get(user_id)
                
            if encrypted_message and session_key:
                message = self.decrypt_message(encrypted_message, session_key)
            else:
                message = encrypted_message
            
            # Не сохраняем если нет ни текста, ни файлов
            if not message and not files:
                return json_response({'status': 'nothing to save'}, start_response)

            message = post_data.get('message', '').strip()
            group_id = post_data.get('group_id')
            receiver = post_data.get('receiver')

            # Определяем тип сообщения
            if group_id:
                message_type = 'group'
            elif receiver:
                message_type = 'private'
            else:
                message_type = 'general'

            # Для приватных сообщений получаем ID получателя
            receiver_id = None
            if message_type == 'private':
                with get_db_cursor() as cursor:
                    cursor.execute('SELECT id FROM users WHERE username = ?', (receiver,))
                    receiver_user = cursor.fetchone()
                    if not receiver_user:
                        return json_response(
                            {'error': 'User not found'}, 
                            start_response, 
                            '404 Not Found'
                        )
                    receiver_id = receiver_user[0]

            # Создаем сообщение в базе данных
            message_id = MessageModel.create_message(
                message_type=message_type,
                user_id=user_id,
                message_text=message,
                group_id=group_id,
                receiver_id=receiver_id
            )
            
            if not message_id:
                raise Exception("Failed to create message")

            # Обрабатываем файлы

            if files:
                unique_files = set()
                upload_folder = os.path.join('static', 'uploads')
                os.makedirs(upload_folder, exist_ok=True)
                
                for file in files:
                    if file.filename and file.file:
                        file_data = file.file.read()
                        
                        if session_key:
                            try:
                                file_data = self.decrypt_file(file_data, session_key)
                            except Exception as e:
                                logging.error(f"Failed to decrypt file: {str(e)}")
                        
                        # Сохраняем файл
                        filename = secure_filename(file.filename)
                        file_path = os.path.join(upload_folder, filename)
                        
                        with open(file_path, 'wb') as f:
                            f.write(file_data)
                        
                        file_info = {
                            'path': f'/static/uploads/{filename}',
                            'mime_type': file.type,
                            'filename': filename
                        }
                        
                        if file_info['path'] not in unique_files:
                            unique_files.add(file_info['path'])
                            MessageModel.add_attachment(
                                message_type=message_type,
                                message_id=message_id,
                                file_path=file_info['path'],
                                mime_type=file_info['mime_type'],
                                filename=file_info['filename']
                            )

            return json_response({'status': 'success'}, start_response)

        except Exception as e:
            logging.error(f"Error in SendMessageView: {str(e)}", exc_info=True)
            return json_response(
                {'error': 'Internal server error'}, 
                start_response, 
                '500 Internal Server Error'
            )
          
class DeleteMessageView(View):
    def get_user_id(self, environ):
        request = Request(environ)
        try:
            return int(request.cookies.get('user_id', 0))
        except (ValueError, TypeError):
            return 0

    def response(self, environ, start_response):
        try:
            message_id = int(environ['url_params'][0])
            query = parse_qs(environ['QUERY_STRING'])
            message_type = query.get('type', ['general'])[0]
            user_id = self.get_user_id(environ)
            
            if not user_id:
                return forbidden_response(start_response)

            # Добавим логирование для отладки
            logging.info(f"Attempt to delete message: type={message_type}, id={message_id}, user={user_id}")
            
            success = MessageModel.delete_message(
                message_type=message_type,
                message_id=message_id,
                user_id=user_id
            )
            
            if not success:
                logging.warning(f"Delete failed: no permissions for user {user_id}")
                return json_response(
                    {'error': 'Недостаточно прав для удаления'}, 
                    start_response, 
                    '403 Forbidden'
                )

            return json_response({'status': 'Сообщение удалено'}, start_response)

        except Exception as e:
            logging.error(f"Ошибка удаления: {str(e)}", exc_info=True)
            return json_response(
                {'error': 'Внутренняя ошибка сервера'}, 
                start_response, 
                '500 Internal Server Error'
            )
        
class EditMessageView(View):
    def get_user_id(self, environ):
        request = Request(environ)
        try:
            return int(request.cookies.get('user_id', 0))
        except (ValueError, TypeError):
            return 0

    def response(self, environ, start_response):
        try:
            message_id = int(environ['url_params'][0])
            query = parse_qs(environ['QUERY_STRING'])
            message_type = query.get('type', ['general'])[0]
            user_id = self.get_user_id(environ)
            
            if not user_id:
                return forbidden_response(start_response)

            # Добавим логирование для отладки
            logging.info(f"Attempt to edit message: type={message_type}, id={message_id}, user={user_id}")
            
            content_length = int(environ.get('CONTENT_LENGTH', 0))
            data = json.loads(environ['wsgi.input'].read(content_length))
            new_text = data.get('message', '').strip()
            
            if not new_text:
                return json_response(
                    {'error': 'Текст сообщения не может быть пустым'}, 
                    start_response, 
                    '400 Bad Request'
                )

            success = MessageModel.edit_message(
                message_type=message_type,
                message_id=message_id,
                user_id=user_id,
                new_text=new_text
            )
            
            if not success:
                logging.warning(f"Edit failed: no permissions for user {user_id}")
                return json_response(
                    {'error': 'Нет прав на редактирование'}, 
                    start_response, 
                    '403 Forbidden'
                )

            return json_response({'status': 'Сообщение обновлено'}, start_response)

        except Exception as e:
            logging.error(f"Ошибка редактирования: {str(e)}", exc_info=True)
            return json_response(
                {'error': 'Внутренняя ошибка сервера'}, 
                start_response, 
                '500 Internal Server Error'
            )

class GetGroupMessagesView(View):
    def response(self, environ, start_response):
        try:
            request = Request(environ)
            query_string = environ.get('QUERY_STRING', '')
            group_id = None
            
            for param in query_string.split('&'):
                if param.startswith('group_id='):
                    group_id = param.split('=')[1]
                    break
            
            if not group_id:
                return json_response(
                    {'error': 'Group ID is required'},
                    start_response,
                    '400 Bad Request'
                )
            
            try:
                group_id = int(group_id)
            except ValueError:
                return json_response(
                    {'error': 'Invalid group ID format'},
                    start_response,
                    '400 Bad Request'
                )
            
            timestamp = int(request.GET.get('timestamp', 0))
            user_id = request.cookies.get('user_id')

            if not user_id:
                return forbidden_response(start_response)

            # Получаем сообщения из модели
            messages = MessageModel.get_group_messages(group_id, timestamp)
                
            return json_response({
                'messages': messages,
                'timestamp': max([msg['timestamp'] for msg in messages] or [timestamp])
            }, start_response)

        except Exception as e:
            logging.error(f"GetGroupMessages error: {str(e)}", exc_info=True)
            return json_response(
                {'error': 'Internal server error'}, 
                start_response, 
                '500 Internal Server Error'
            )

class GetPrivateMessagesView(View):
    def response(self, environ, start_response):
        try:
            request = Request(environ)
            user_id = request.cookies.get('user_id')
            other_user = request.GET.get('user')
            timestamp = int(request.GET.get('timestamp', 0))

            if not user_id:
                return json_response(
                    {'error': 'Not authorized'}, 
                    start_response, 
                    '401 Unauthorized'
                )
            
            if not other_user:
                return json_response(
                    {'error': 'User parameter is required'},
                    start_response,
                    '400 Bad Request'
                )

            # Получаем ID собеседника через UserModel
            with get_db_cursor() as cursor:
                cursor.execute('SELECT id FROM users WHERE username = ?', (other_user,))
                result = cursor.fetchone()
                if not result:
                    return json_response(
                        {'error': 'User not found'}, 
                        start_response, 
                        '404 Not Found'
                    )
                
                other_user_id = result[0]
                
            messages = MessageModel.get_private_messages(
                user_id=user_id,
                other_user_id=other_user_id,
                timestamp=timestamp
            )
            
            new_timestamp = max([msg['timestamp'] for msg in messages]) if messages else timestamp
            
            return json_response({
                'messages': messages,
                'timestamp': new_timestamp
            }, start_response)

        except Exception as e:
            print(f"Error in private messages: {str(e)}")
            return json_response(
                {'error': 'Internal server error'}, 
                start_response, 
                '500 Internal Server Error'
            )

class SendPrivateMessageView(View):
    def response(self, environ, start_response):
        try:
            request = Request(environ)
            user_id = request.cookies.get('user_id')
            
            if not user_id:
                return forbidden_response(start_response)

            content_length = int(environ.get('CONTENT_LENGTH', 0))
            post_data = json.loads(environ['wsgi.input'].read(content_length))
            
            receiver = post_data.get('receiver')
            message = post_data.get('message')

            if not receiver or not message:
                return json_response(
                    {'error': 'Missing parameters'}, 
                    start_response, 
                    '400 Bad Request'
                )

            receiver_id = UserModel.get_user_id(receiver)
            if not receiver_id:
                return json_response(
                    {'error': 'User not found'}, 
                    start_response, 
                    '404 Not Found'
                )
                
                receiver_id = result[0]

            message_id = MessageModel.create_message(
                message_type='private',
                user_id=user_id,
                message_text=message,
                receiver_id=receiver_id
            )
            
            if not message_id:
                raise Exception("Failed to create private message")
                
            return json_response({'status': 'success'}, start_response)

        except Exception as e:
            print(f"Error in private message: {str(e)}")
            return json_response(
                {'error': 'Internal server error'}, 
                start_response, 
                '500 Internal Server Error'
            )

class SendSystemMessageView(View):
    def response(self, environ, start_response):
        try:
            request = Request(environ)
            data = json.loads(request.body.decode('utf-8'))
            
            if data['type'] == 'group_leave':
                message_text = f"Пользователь {data['username']} покинул группу"                
                with get_db_cursor() as cursor:
                    cursor.execute('''
                        INSERT INTO group_messages 
                        (group_id, user_id, message_text, timestamp)
                        VALUES (?, 0, ?, ?)
                    ''', (data['group_id'], message_text, int(time.time())))
                    
                    cursor.connection.commit()
                    
            return json_response({'status': 'success'}, start_response)
            
        except Exception as e:
            return json_response({'error': str(e)}, start_response, '500 Internal Server Error')
            
class CheckMessagesView(View):
    def response(self, environ, start_response):
        try:
            request = Request(environ)
            query = parse_qs(environ['QUERY_STRING'])
            message_type = query.get('type', ['general'])[0]
            message_ids = query.get('ids', [''])[0].split(',')
            
            if not message_ids or not message_ids[0]:
                return json_response({'existingIds': []}, start_response)

            with get_db_cursor() as cursor:
                if message_type == 'group':
                    chat_id = query.get('chat_id', [None])[0]
                    cursor.execute('''
                        SELECT message_id 
                        FROM group_messages 
                        WHERE group_id = ? AND message_id IN (%s)
                    ''' % ','.join('?'*len(message_ids)), 
                    [chat_id] + message_ids)
                elif message_type == 'private':
                    # Для приватных чатов нужно проверить оба направления
                    user_id = request.cookies.get('user_id')
                    chat_id = query.get('chat_id', [None])[0]
                    cursor.execute('SELECT id FROM users WHERE username = ?', (chat_id,))
                    partner = cursor.fetchone()
                    if not partner:
                        return json_response({'existingIds': []}, start_response)
                    
                    cursor.execute('''
                        SELECT id 
                        FROM private_messages 
                        WHERE (
                            (sender_id = ? AND receiver_id = ?) OR
                            (sender_id = ? AND receiver_id = ?)
                        ) AND id IN (%s)
                    ''' % ','.join('?'*len(message_ids)), 
                    [user_id, partner[0], partner[0], user_id] + message_ids)
                else:
                    cursor.execute('''
                        SELECT message_id 
                        FROM messages 
                        WHERE message_id IN (%s)
                    ''' % ','.join('?'*len(message_ids)), 
                    message_ids)
                
                existing_ids = [str(row[0]) for row in cursor.fetchall()]
                return json_response({'existingIds': existing_ids}, start_response)
                
        except Exception as e:
            logging.error(f"CheckMessages error: {str(e)}")
            return json_response({'existingIds': []}, start_response)
        
class CheckEditedMessagesView(View):
    def response(self, environ, start_response):
        try:
            request = Request(environ)
            query = parse_qs(environ['QUERY_STRING'])
            message_type = query.get('type', ['general'])[0]
            last_timestamp = int(query.get('last_timestamp', [0])[0])
            
            with get_db_cursor() as cursor:
                if message_type == 'group':
                    chat_id = query.get('chat_id', [None])[0]
                    cursor.execute('''
                        SELECT 
                            gm.message_id as id,
                            gm.message_text as text,
                            gm.timestamp
                        FROM group_messages gm
                        WHERE gm.group_id = ? 
                        AND gm.timestamp > ?
                        ORDER BY gm.timestamp DESC
                    ''', (chat_id, last_timestamp))
                elif message_type == 'private':
                    user_id = request.cookies.get('user_id')
                    chat_id = query.get('chat_id', [None])[0]
                    cursor.execute('SELECT id FROM users WHERE username = ?', (chat_id,))
                    partner = cursor.fetchone()
                    if not partner:
                        return json_response({'editedMessages': []}, start_response)
                    
                    cursor.execute('''
                        SELECT 
                            pm.id as id,
                            pm.message_text as text,
                            pm.timestamp
                        FROM private_messages pm
                        WHERE (
                            (pm.sender_id = ? AND pm.receiver_id = ?) OR
                            (pm.sender_id = ? AND pm.receiver_id = ?)
                        )
                        AND pm.timestamp > ?
                        ORDER BY pm.timestamp DESC
                    ''', [user_id, partner[0], partner[0], user_id, last_timestamp])
                else:
                    cursor.execute('''
                        SELECT 
                            m.message_id as id,
                            m.message_text as text,
                            m.timestamp
                        FROM messages m
                        WHERE m.timestamp > ?
                        ORDER BY m.timestamp DESC
                    ''', (last_timestamp,))
                
                edited_messages = [{
                    'id': row[0],
                    'text': row[1],
                    'timestamp': row[2]
                } for row in cursor.fetchall()]
                
                return json_response({'editedMessages': edited_messages}, start_response)
                
        except Exception as e:
            logging.error(f"CheckEditedMessages error: {str(e)}")
            return json_response({'editedMessages': []}, start_response)
