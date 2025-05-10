from collections import namedtuple
import sqlite3
import json
import time
import uuid
import os 
import logging
import hashlib
import re

from urllib.parse import parse_qs
from mimes import get_mime
from webob import Request
from werkzeug.utils import secure_filename

from utils import *
 
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='app.log'
)

Response = namedtuple("Response", "status headers data")

def json_response(data, start_response, status='200 OK'):
    headers = [
        ('Content-Type', 'application/json'),
        ('Access-Control-Allow-Origin', 'http://localhost:8000'),
        ('Access-Control-Allow-Credentials', 'true')
    ]
    start_response(status, headers)
    return [json.dumps(data).encode('utf-8')]

def forbidden_response(start_response):
    start_response('403 Forbidden', [('Content-Type', 'text/plain')])
    return [b'Access denied']

class View:
    path = ''

    def __init__(self, url) -> None:
        self.url = url

    def response(self, environ, start_response):
        file_path = self.path + self.url
        file_path = file_path.lstrip('/')  # Убираем ведущий слеш
        
        if not os.path.exists(file_path):
            start_response('404 Not Found', [('Content-Type', 'text/plain')])
            return [b'File not found']
        
        try:
            mime_type = get_mime(file_path)
            
            # Для текстовых файлов
            if mime_type.startswith('text/') or mime_type in ['application/javascript', 'application/json']:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = f.read()
                start_response('200 OK', [('Content-Type', mime_type)])
                return [data.encode('utf-8')]
            # Для бинарных файлов
            else:
                with open(file_path, 'rb') as f:
                    data = f.read()
                start_response('200 OK', [('Content-Type', mime_type)])
                return [data]
                
        except UnicodeDecodeError:
            # Если не получилось прочитать как текст, пробуем как бинарный
            with open(file_path, 'rb') as f:
                data = f.read()
            start_response('200 OK', [('Content-Type', mime_type)])
            return [data]
        except Exception as e:
            logging.error(f"Error serving file {file_path}: {str(e)}")
            start_response('500 Internal Server Error', [('Content-Type', 'text/plain')])
            return [b'Internal Server Error']

    def read_file(self, file_name):
        print(file_name)
        with open(file_name, 'r', encoding='utf-8') as file:
            return file.read()

class TemplateView(View):
    template = ''

    def __init__(self, url) -> None:
        super().__init__(url)
        self.url = '/' + self.template

    def response(self, environ, start_response):
        file_name = self.path + self.url
        headers = [('Content-type', get_mime(file_name))]
        try:
            data = self.read_file(file_name[1:])
            status = '200 OK'
        except FileNotFoundError:
            data = ''
            status = '404 Not found'
        start_response(status, headers)
        return [data.encode('utf-8')]

    def read_file(self, file_name):
        print(file_name)
        with open(file_name, 'r', encoding='utf-8') as file:
            return file.read()

class IndexView(TemplateView):
    template = 'templates/index.html'

class NotFoundView(TemplateView):
    template = 'templates/404.html'
    
    def response(self, environ, start_response):
        headers = [('Content-type', 'text/html')]
        try:
            with open(self.template, 'r', encoding='utf-8') as file:
                data = file.read()
            start_response('404 Not Found', headers)
            return [data.encode('utf-8')]
        except FileNotFoundError:
            start_response('404 Not Found', headers)
            return [b'<h1>404 Not Found</h1><p>Page not found</p>']
        

class ForbiddenView(TemplateView):
    template = 'templates/403.html'
    
    def response(self, environ, start_response):
        headers = [('Content-type', 'text/html')]
        try:
            with open(self.template, 'r', encoding='utf-8') as file:
                data = file.read()
            start_response('403 Forbidden', headers)
            return [data.encode('utf-8')]
        except FileNotFoundError:
            start_response('403 Forbidden', headers)
            return [b'<h1>403 Forbidden</h1><p>Access denied</p>']

class InternalServerErrorView(TemplateView):
    template = 'templates/500.html'
    
    def response(self, environ, start_response):
        headers = [('Content-type', 'text/html')]
        try:
            with open(self.template, 'r', encoding='utf-8') as file:
                data = file.read()
            start_response('500 Internal Server Error', headers)
            return [data.encode('utf-8')]
        except FileNotFoundError:
            start_response('500 Internal Server Error', headers)
            return [b'<h1>500 Internal Server Error</h1><p>Server error occurred</p>']
        
class GetMessageView(View):
    def response(self, environ, start_response):
        try:
            # Парсинг и валидация параметров
            query_params = parse_qs(environ.get('QUERY_STRING', ''))
            timestamp = self._parse_timestamp(query_params)
            
            with get_db_cursor() as cursor:
                messages = self._fetch_messages(cursor, timestamp)
                
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

    def _fetch_messages(self, cursor, timestamp):
        cursor.execute('''
            SELECT 
                m.message_id,
                m.sender,
                m.message_text,
                m.timestamp,
                a.file_path,
                a.mime_type,
                a.filename,
                'general' as type
            FROM messages m
            LEFT JOIN attachments a ON a.message_id = m.message_id AND a.message_type = 'general'
            WHERE m.timestamp > ?
            ORDER BY m.timestamp
        ''', (timestamp,))
        
        messages = {}
        for row in cursor.fetchall():
            msg_id = row[0]
            if msg_id not in messages:
                messages[msg_id] = {
                    'id': msg_id,
                    'sender': row[1],
                    'message_text': row[2],
                    'timestamp': row[3],
                    'attachments': []
                }
            
            if row[4]:  # Если есть вложение
                messages[msg_id]['attachments'].append({
                    'path': row[4],
                    'mime_type': row[5],
                    'filename': row[6]
                })
                
        return list(messages.values())

    def _get_new_timestamp(self, messages, old_timestamp):
        if messages:
            return max(msg['timestamp'] for msg in messages)
        return old_timestamp

    def get_new_messages_from_db(self, timestamp):
        """Устаревший метод, рекомендуется использовать response"""
        try:
            with get_db_cursor() as cursor:
                messages = self._fetch_messages(cursor, timestamp)
                
            return (
                [{
                    'sender': msg['sender'],
                    'message_text': msg['message_text'],
                    'timestamp': msg['timestamp'],
                    'attachments': msg['attachments']
                } for msg in messages],
                self._get_new_timestamp(messages, timestamp)
            )
        except Exception as e:
            logging.error(f"get_new_messages_from_db error: {str(e)}")
            return [], timestamp

class GetUserIdView(View):
    def fetch_user_id_from_database(self, username):
        connection = sqlite3.connect('data.db')
        cursor = connection.cursor()

        cursor.execute("SELECT user_id FROM users WHERE username=?", (username,))
        
        user_id = cursor.fetchone()

        cursor.close()
        connection.close()

        return user_id[0] if user_id else None

    def response(self, environ, start_response):
        try:
            request = Request(environ)
            user_id_cookie = request.cookies.get('user_id')
            
            if not user_id_cookie:
                return json_response({'user_id': None}, start_response)
            
            # Проверяем валидность user_id из cookie
            try:
                user_id = int(user_id_cookie)
            except (ValueError, TypeError):
                return json_response({'error': 'Invalid user_id format'}, start_response, '400 Bad Request')

            with get_db_cursor() as cursor:
                # Получаем username по user_id
                cursor.execute("SELECT username FROM users WHERE id = ?", (user_id,))
                user = cursor.fetchone()
                
                if not user:
                    return json_response({'error': 'User not found'}, start_response, '404 Not Found')
                
                # Возвращаем и user_id и username для удобства
                response_data = {
                    'user_id': user_id,
                    'username': user[0]
                }
                
                headers = [
                    ('Content-Type', 'application/json'),
                    ('Access-Control-Allow-Origin', 'http://localhost:8000'),
                    ('Access-Control-Allow-Credentials', 'true'),
                    ('Set-Cookie', f'user_id={user_id}; Path=/; HttpOnly; SameSite=Lax')
                ]
                
                start_response('200 OK', headers)
                return [json.dumps(response_data).encode('utf-8')]
                request = Request(environ)
            if not request.cookies.get('user_id'):
                return json_response({'error': 'Not authorized'}, start_response, '401 Unauthorized')
                
        except Exception as e:
            logging.error(f"GetUserId error: {str(e)}", exc_info=True)
            return json_response(
                {'error': 'Internal server error'}, 
                start_response, 
                '500 Internal Server Error'
            )
        

class SendMessageView(View):
    def response(self, environ, start_response):
        try:
            request = Request(environ)
            user_id = request.cookies.get('user_id')

            
            
            if not user_id:
                return forbidden_response(start_response)

            if request.content_type.startswith('multipart/form-data'):
                post_data = request.POST
                files = request.POST.getall('files')  # Получаем файлы
                message = post_data.get('message', '').strip()  # Получаем текст
            else:
                return json_response(
                    {'error': 'Invalid content type'}, 
                    start_response, 
                    '400 Bad Request'
                )
            
            # Не сохраняем если нет ни текста, ни файлов
            if not message and not files:
                return json_response({'status': 'nothing to save'}, start_response)

            message = post_data.get('message', '').strip()
            group_id = post_data.get('group_id')
            receiver = post_data.get('receiver')


            with get_db_cursor() as cursor:
                cursor.execute('SELECT username FROM users WHERE id = ?', (user_id,))
                user = cursor.fetchone()
                if not user:
                    return forbidden_response(start_response)
                username = user[0]

                timestamp = int(time.time())
                message_id = None
                message_type = None

                # Сохраняем сообщение только если есть текст ИЛИ файлы
                if message or files:
                    if group_id:
                        # Групповое сообщение
                        cursor.execute('''
                            INSERT INTO group_messages 
                            (group_id, user_id, message_text, timestamp)
                            VALUES (?, ?, ?, ?)
                        ''', (group_id, user_id, message, timestamp))
                        message_type = 'group'
                        message_id = cursor.lastrowid
                        
                    elif receiver:
                        # Личное сообщение
                        cursor.execute('SELECT id FROM users WHERE username = ?', (receiver,))
                        receiver_user = cursor.fetchone()
                        if not receiver_user:
                            return json_response({'error': 'User not found'}, start_response, '404 Not Found')
                            
                        cursor.execute('''
                            INSERT INTO private_messages 
                            (sender_id, receiver_id, message_text, timestamp)
                            VALUES (?, ?, ?, ?)
                        ''', (user_id, receiver_user[0], message, timestamp))
                        message_type = 'private'
                        message_id = cursor.lastrowid
                        
                    else:
                        # Общее сообщение
                        cursor.execute('''
                            INSERT INTO messages 
                            (user_id, sender, message_text, timestamp)
                            VALUES (?, ?, ?, ?)
                        ''', (user_id, username, message, timestamp))
                        message_type = 'general'
                        message_id = cursor.lastrowid

                    if files and message_id:
                        unique_files = set()
                        for file in files:
                            if file.filename and file.file:
                                file_content = file.file.read()
                                file_hash = hashlib.md5(file_content).hexdigest()
                                file.file.seek(0)  
                                
                                if file_hash in unique_files:
                                    continue
                                unique_files.add(file_hash)
                                
                                filename = secure_filename(file.filename)
                                unique_name = f"{file_hash}_{filename}"
                                file_path = os.path.join('static', 'uploads', unique_name)
                                
                                if not os.path.exists(file_path):
                                    with open(file_path, 'wb') as f:
                                        f.write(file_content)
                                
                                cursor.execute('''
                                    INSERT INTO attachments 
                                    (message_type, message_id, file_path, mime_type, filename)
                                    VALUES (?, ?, ?, ?, ?)
                                ''', (message_type, message_id, f'/static/uploads/{unique_name}', file.type, filename))
                                
                                if files and message_id and not unique_files:
                                    cursor.connection.rollback()
                                    return json_response({'error': 'No files to save'}, start_response, '400 Bad Request')

                cursor.connection.commit()

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

            table_info = {
                'general': ('messages', 'message_id', 'user_id'),
                'group': ('group_messages', 'message_id', 'user_id'),
                'private': ('private_messages', 'id', 'sender_id')
            }

            if message_type not in table_info:
                return json_response(
                    {'error': 'Invalid message type'}, 
                    start_response, 
                    '400 Bad Request'
                )

            table, id_col, user_col = table_info[message_type]

            with get_db_cursor() as cursor:
                # Для групповых сообщений проверяем права
                if message_type == 'group':
                    # Получаем group_id сообщения
                    cursor.execute(f'''
                        SELECT group_id FROM group_messages 
                        WHERE message_id = ?
                    ''', (message_id,))
                    group_result = cursor.fetchone()
                    
                    if not group_result:
                        return json_response(
                            {'error': 'Message not found'}, 
                            start_response, 
                            '404 Not Found'
                        )
                    
                    group_id = group_result[0]
                    
                    # Проверяем права пользователя
                    cursor.execute('''
                        SELECT role FROM group_members 
                        WHERE group_id = ? AND user_id = ?
                    ''', (group_id, user_id))
                    role_result = cursor.fetchone()
                    
                    if not role_result:
                        return json_response(
                            {'error': 'Not a group member'}, 
                            start_response, 
                            '403 Forbidden'
                        )
                    
                    role = role_result[0]
                    
                    # Если не админ, проверяем что это его сообщение
                    if role not in ('owner', 'admin'):
                        cursor.execute(f'''
                            SELECT {user_col} 
                            FROM {table} 
                            WHERE {id_col} = ?
                        ''', (message_id,))
                        message_owner = cursor.fetchone()
                        
                        if not message_owner or int(message_owner[0]) != user_id:
                            return json_response(
                                {'error': 'Недостаточно прав'}, 
                                start_response, 
                                '403 Forbidden'
                            )

                # Удаляем сообщение
                cursor.execute(f'''
                    DELETE FROM {table} 
                    WHERE {id_col} = ?
                ''', (message_id,))

                # Удаляем вложения
                cursor.execute('''
                    DELETE FROM attachments 
                    WHERE message_type = ? 
                    AND message_id = ?
                ''', (message_type, message_id))

                cursor.connection.commit()
                return json_response(
                    {'status': 'Сообщение удалено'}, 
                    start_response
                )

        except Exception as e:
            logging.error(f"Ошибка удаления: {str(e)}")
            return json_response(
                {'error': 'Внутренняя ошибка сервера'}, 
                start_response, 
                '500 Internal Server Error'
            )

class RegisterView(TemplateView):
    template = 'templates/register.html'

    def response(self, environ, start_response):
        request = Request(environ)
        if request.method == 'POST':
            post_data = request.POST
            username = post_data.get('username', '').strip()
            password = post_data.get('password', '')

            # Проверка имени пользователя
            if not re.match(r'^[a-zA-Zа-яА-Я0-9_-]{3,20}$', username):
                return json_response(
                    {'error': 'Недопустимое имя пользователя'},
                    start_response,
                    '400 Bad Request'
                )

            # Проверка пароля
            if len(password) < 6:
                return json_response(
                    {'error': 'Пароль должен быть не менее 6 символов'},
                    start_response,
                    '400 Bad Request'
                )

            try:
                hashed_password = hash_password(password)
                with get_db_cursor() as cursor:
                    cursor.execute(
                        'INSERT INTO users (username, password) VALUES (?, ?)',
                        (username, hashed_password)
                    )
                    cursor.connection.commit()
                return json_response(
                    {'message': 'Регистрация прошла успешно!'},
                    start_response
                )

            except sqlite3.IntegrityError:
                return json_response(
                    {'error': 'Пользователь с таким именем уже существует'},
                    start_response,
                    '400 Bad Request'
                )
            except Exception as e:
                logging.error(f"Registration error: {str(e)}")
                return json_response(
                    {'error': 'Ошибка сервера при регистрации'},
                    start_response,
                    '500 Internal Server Error'
                )

        return super().response(environ, start_response)

    def register_user(self, username, password):
        """
        Регистрирует пользователя в базе данных.
        """
        try:
            hashed_password = hash_password(password)
            with get_db_cursor() as cursor:
                cursor.execute('INSERT INTO users (username, password) VALUES (?, ?)', 
                            (username, hashed_password))
                cursor.connection.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        except Exception as e:
            raise

    def get_post_data(self, request, key):
        try:
            data = request.POST.get(key, '')
            #print(f"Received data for {key}: {data}") 
            return data
        except Exception as e:
            print(f"Error while extracting {key}: {e}")
            return None

class LoginView(TemplateView):
    template = 'templates/login.html'

    def response(self, environ, start_response):
        if environ['REQUEST_METHOD'] == 'POST':
            request = Request(environ)
            post_data = parse_qs(request.body.decode('utf-8'))
            username = post_data.get('username', [''])[0].strip()
            password = post_data.get('password', [''])[0]

            # Проверка имени
            if not re.match(r'^[a-zA-Zа-яА-Я0-9_-]{3,20}$', username):
                return json_response(
                    {'error': 'Недопустимое имя пользователя'},
                    start_response,
                    '400 Bad Request'
                )

            if username and password:
                user_id = self.authenticate_user(username, password)
                if user_id is not None:
                    status = '200 OK'
                    headers = [
                        ('Content-Type', 'application/json'),
                        ('Set-Cookie', f'user_id={user_id}; Path=/; HttpOnly; SameSite=Lax')
                    ]
                    data = json.dumps({'redirect': '/'})  
                    start_response(status, headers)
                    return [data.encode('utf-8')]
                else:
                    status = '401 Unauthorized'
                    headers = [
                        ('Content-Type', 'application/json'),
                        ('Set-Cookie', f'user_id={user_id}; Path=/; HttpOnly; SameSite=Lax')
                    ]
                    data = json.dumps({'error': 'Invalid username or password'})
                    start_response(status, headers)
                    return [data.encode('utf-8')]
            else:
                status = '400 Bad Request'
                headers = [
                        ('Content-Type', 'application/json'),
                        ('Set-Cookie', f'user_id={user_id}; Path=/; HttpOnly; SameSite=Lax')
                    ]
                data = json.dumps({'error': 'Invalid username or password'})
                start_response(status, headers)
                return [data.encode('utf-8')]
        else:
            return super().response(environ, start_response)
        
    def authenticate_user(self, username, password):
        """
        Аутентифицирует пользователя.
        """
        try:
            with get_db_cursor() as cursor:
                cursor.execute(
                    'SELECT id, password FROM users WHERE username=?',
                    (username,)
                )
                result = cursor.fetchone()
                if result:
                    user_id, hashed_password = result
                    if check_password(hashed_password, password):
                        return user_id
            return None
        except Exception as e:
            raise

    def get_post_data(self, request):
        try:
            data = request.POST
            return data
        except Exception as e:
            print(f"Error while extracting POST data: {e}")
            return None
        
class CreateGroupView(View):
    def response(self, environ, start_response):
        """
        Генерирует HTTP-ответ для создания группы.
        """
        try:
            request = Request(environ)
            user_id = request.cookies.get('user_id')
            content_length = int(environ.get('CONTENT_LENGTH', 0))
            post_data = json.loads(environ['wsgi.input'].read(content_length))
            group_name = post_data.get('name', '')

            if not group_name:
                return json_response(
                    {'error': 'Укажите название группы'}, 
                    start_response, 
                    '400 Bad Request'
                )

            with get_db_cursor() as cursor:
                cursor.execute('SELECT group_id FROM groups WHERE name = ?', (group_name,))
                if cursor.fetchone():
                    return json_response(
                        {'error': 'Группа с таким именем уже существует'},
                        start_response,
                        '400 Bad Request'
                    )
                
                # Создаем группу
                timestamp = int(time.time())
                cursor.execute('''
                    INSERT INTO groups (name, creator_id, created_at)
                    VALUES (?, ?, ?)
                ''', (group_name, user_id, timestamp))
                
                group_id = cursor.lastrowid
                
                # Добавляем создателя как владельца
                cursor.execute('''
                    INSERT INTO group_members (group_id, user_id, role, joined_at)
                    VALUES (?, ?, ?, ?)
                ''', (group_id, user_id, 'owner', timestamp))
                
                cursor.connection.commit()
                return json_response(
                    {'status': 'success', 'group_id': group_id}, 
                    start_response
                )
            
        except Exception as e:
            logging.error(f"Error creating group: {str(e)}", exc_info=True)
            return json_response(
                {'error': 'Ошибка сервера'}, 
                start_response, 
                '500 Internal Server Error'
            )

class AddToGroupView(View):
    def response(self, environ, start_response):
        try:
            request = Request(environ)
            user_id = request.cookies.get('user_id')
            
            if not user_id:
                return json_response(
                    {'error': 'Not authorized'}, 
                    start_response, 
                    '401 Unauthorized'
                )

            content_length = int(environ.get('CONTENT_LENGTH', 0))
            post_data = json.loads(environ['wsgi.input'].read(content_length))
            
            group_id = post_data.get('group_id')
            username = post_data.get('username')
            role = post_data.get('role', 'member')

            with get_db_cursor() as cursor:
                # Проверяем права текущего пользователя
                cursor.execute('''
                    SELECT role FROM group_members 
                    WHERE group_id = ? AND user_id = ?
                ''', (group_id, user_id))
                current_user_role = cursor.fetchone()
                
                if not current_user_role:
                    return json_response(
                        {'error': 'Вы не состоите в этой группе', 'code': 'not_member'}, 
                        start_response, 
                        '403 Forbidden'
                    )
                
                if current_user_role[0] not in ['owner', 'admin']:
                    return json_response(
                        {
                            'error': 'Недостаточно прав для добавления участников',
                            'code': 'insufficient_permissions',
                            'required_role': 'admin'
                        }, 
                        start_response, 
                        '403 Forbidden'
                    )
                
                # Проверяем существование группы
                cursor.execute('SELECT name FROM groups WHERE group_id = ?', (group_id,))
                group = cursor.fetchone()
                if not group:
                    return json_response(
                        {'error': 'Group not found'}, 
                        start_response, 
                        '404 Not Found'
                    )
                
                # Добавляем в группу
                cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
                target_user = cursor.fetchone()
                if not target_user:
                    return json_response(
                        {'error': 'User not found'}, 
                        start_response, 
                        '404 Not Found'
                    )
                
                target_user_id = target_user[0]
                
                # Проверяем, что не пытаемся изменить права владельца
                if target_user_id == user_id and role != 'owner':
                    return json_response(
                        {'error': 'Нельзя изменить свои права'}, 
                        start_response, 
                        '400 Bad Request'
                    )
                
                try:
                    timestamp = int(time.time())
                    cursor.execute('''
                        INSERT OR REPLACE INTO group_members 
                        (group_id, user_id, role, joined_at)
                        VALUES (?, ?, ?, ?)
                    ''', (group_id, target_user_id, role, timestamp))
                    
                    # Добавляем системное сообщение
                    cursor.execute('''
                        INSERT INTO group_messages 
                        (group_id, user_id, message_text, timestamp)
                        VALUES (?, 0, ?, ?)
                    ''', (group_id, f'Пользователь {username} добавлен в группу! 🎉', timestamp))
                    
                    cursor.connection.commit()
                    
                    return json_response({
                        'status': 'success',
                        'group_id': group_id,
                        'group_name': group[0],
                        'requires_ui_update': True  
                    }, start_response)
                    
                except sqlite3.IntegrityError:
                    return json_response(
                        {'error': 'User already in group'}, 
                        start_response, 
                        '400 Bad Request'
                    )
        except Exception as e:
            logging.error(f"AddToGroup error: {str(e)}")
            return json_response(
                {'error': 'Internal Server Error'}, 
                start_response, 
                '500 Internal Server Error'
            )
                                    
class GetGroupsView(View):
    def response(self, environ, start_response):
        request = Request(environ)
        user_id = request.cookies.get('user_id')
        if not user_id:
            return forbidden_response(start_response)

        with get_db_cursor() as cursor:
            cursor.execute('''
                SELECT g.group_id, g.name, gm.role
                FROM groups g
                JOIN group_members gm ON g.group_id = gm.group_id
                WHERE gm.user_id = ?
                ORDER BY g.name
            ''', (user_id,))
            
            groups = [{
                'id': row[0],
                'name': row[1],
                'role': row[2]
            } for row in cursor.fetchall()]
            
            return json_response(groups, start_response)

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

            with get_db_cursor() as cursor:
                cursor.execute('''
                    SELECT 
                        gm.message_id,
                        CASE 
                            WHEN gm.user_id = 0 THEN 'System'
                            ELSE u.username
                        END as sender,
                        gm.message_text,
                        gm.timestamp,
                        a.file_path,
                        a.mime_type,
                        a.filename,
                        'group' as type,
                        gm.user_id
                    FROM group_messages gm
                    LEFT JOIN users u ON gm.user_id = u.id
                    LEFT JOIN attachments a 
                        ON a.message_id = gm.message_id 
                        AND a.message_type = 'group'
                    WHERE gm.group_id = ? AND gm.timestamp > ?
                    ORDER BY gm.timestamp
                ''', (group_id, timestamp))
                
                messages = {}
                for row in cursor.fetchall():
                    msg_id = row[0]
                    if msg_id not in messages:
                        messages[msg_id] = {
                            'id': msg_id,
                            'sender': row[1],
                            'message_text': row[2],
                            'timestamp': row[3],
                            'type': row[7],
                            'user_id': row[8],
                            'attachments': []
                        }
                    
                    if row[4]:  # Если есть вложение
                        messages[msg_id]['attachments'].append({
                            'path': row[4],
                            'mime_type': row[5],
                            'filename': row[6]
                        })
                
                return json_response({
                    'messages': list(messages.values()),
                    'timestamp': max([msg['timestamp'] for msg in messages.values()] or [timestamp])
                }, start_response)

        except Exception as e:
            logging.error(f"GetGroupMessages error: {str(e)}", exc_info=True)
            return json_response(
                {'error': 'Internal server error'}, 
                start_response, 
                '500 Internal Server Error'
            )

class CheckGroupAccessView(View):
    def response(self, environ, start_response):
        try:
            request = Request(environ)
            user_id = request.cookies.get('user_id')
            group_id = request.GET.get('group_id')
            
            if not user_id:
                return json_response(
                    {'error': 'Not authorized'}, 
                    start_response, 
                    '401 Unauthorized'
                )
            
            with get_db_cursor() as cursor:
                cursor.execute('''
                    SELECT 1 FROM group_members 
                    WHERE group_id = ? AND user_id = ?
                ''', (group_id, user_id))
                
                has_access = cursor.fetchone() is not None
                
                cursor.execute('SELECT 1 FROM groups WHERE group_id = ?', (group_id,))
                group_exists = cursor.fetchone() is not None
                
                return json_response({
                    'has_access': has_access,
                    'group_exists': group_exists
                }, start_response)
                
        except Exception as e:
            logging.error(f"CheckGroupAccess error: {str(e)}")
            return json_response(
                {'error': 'Internal Server Error'}, 
                start_response, 
                '500 Internal Server Error'
            )
            
class GetGroupNameView(View):
    def response(self, environ, start_response):
        group_id = Request(environ).GET.get('group_id')
        conn = sqlite3.connect('data.db')
        cursor = conn.cursor()
        cursor.execute('SELECT name FROM groups WHERE group_id = ?', (group_id,))
        group_name = cursor.fetchone()
        conn.close()
        return json_response({'name': group_name[0]}, start_response)
    
class LeaveGroupView(View):
    def response(self, environ, start_response):
        try:
            request = Request(environ)
            user_id = request.cookies.get('user_id')
            
            if not user_id:
                return json_response(
                    {'error': 'Not authorized'}, 
                    start_response, 
                    '401 Unauthorized'
                )

            content_length = int(environ.get('CONTENT_LENGTH', 0))
            post_data = json.loads(environ['wsgi.input'].read(content_length))
            group_id = post_data.get('group_id')

            with get_db_cursor() as cursor:
                try:
                    cursor.execute('BEGIN TRANSACTION')
                    
                    # Проверяем роль пользователя
                    cursor.execute('''
                        SELECT role, username FROM group_members
                        JOIN users ON group_members.user_id = users.id
                        WHERE group_id = ? AND user_id = ?
                    ''', (group_id, user_id))
                    result = cursor.fetchone()
                    
                    if not result:
                        return json_response(
                            {'error': 'User not in group'}, 
                            start_response, 
                            '400 Bad Request'
                        )
                    
                    role, username = result
                    
                    # Если это владелец - удаляем группу
                    if role == 'owner':
                        # Удаляем всех участников
                        cursor.execute('''
                            DELETE FROM group_members WHERE group_id = ?
                        ''', (group_id,))
                        
                        # Удаляем группу
                        cursor.execute('''
                            DELETE FROM groups WHERE group_id = ?
                        ''', (group_id,))
                        
                        # Добавляем системное сообщение
                        cursor.execute('''
                            INSERT INTO group_messages 
                            (group_id, user_id, message_text, timestamp)
                            VALUES (?, 0, ?, ?)
                        ''', (group_id, f'Группа удалена владельцем {username}', int(time.time())))
                    else:
                        # Просто удаляем пользователя
                        cursor.execute('''
                            DELETE FROM group_members 
                            WHERE group_id = ? AND user_id = ?
                        ''', (group_id, user_id))
                        
                        # Добавляем системное сообщение
                        cursor.execute('''
                            INSERT INTO group_messages 
                            (group_id, user_id, message_text, timestamp)
                            VALUES (?, 0, ?, ?)
                        ''', (group_id, f'Пользователь {username} покинул группу', int(time.time())))
                    
                    cursor.connection.commit()
                    
                    return json_response(
                        {'status': 'success'}, 
                        start_response
                    )
                
                except Exception as e:
                    cursor.connection.rollback()
                    logging.error(f"LeaveGroup error: {str(e)}")
                    return json_response(
                        {'error': 'Internal Server Error'}, 
                        start_response, 
                        '500 Internal Server Error'
                    )
        except Exception as e:
            logging.error(f"LeaveGroup error: {str(e)}")
            return json_response(
                {'error': 'Internal Server Error'}, 
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

            # Правильное чтение тела запроса
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

            with get_db_cursor() as cursor:
                # Получаем ID получателя
                cursor.execute(
                    'SELECT id FROM users WHERE username = ?',
                    (receiver,)
                )
                result = cursor.fetchone()
                if not result:
                    return json_response(
                        {'error': 'User not found'}, 
                        start_response, 
                        '404 Not Found'
                    )
                
                receiver_id = result[0]
                timestamp = int(time.time())

                # Сохраняем сообщение
                cursor.execute('''
                    INSERT INTO private_messages 
                    (sender_id, receiver_id, message_text, timestamp)
                    VALUES (?, ?, ?, ?)
                ''', (user_id, receiver_id, message, timestamp))
                
                cursor.connection.commit()
                return json_response({'status': 'success'}, start_response)

        except Exception as e:
            print(f"Error in private message: {str(e)}")
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

            with get_db_cursor() as cursor:
                # Получаем ID собеседника
                cursor.execute('SELECT id FROM users WHERE username = ?', (other_user,))
                result = cursor.fetchone()
                if not result:
                    return json_response(
                        {'error': 'User not found'}, 
                        start_response, 
                        '404 Not Found'
                    )
                
                other_user_id = result[0]
                
                cursor.execute('''
                    SELECT 
                        pm.id,
                        pm.message_text,
                        u_sender.username as sender,
                        pm.timestamp,
                        a.file_path,
                        a.mime_type,
                        a.filename,
                        pm.sender_id
                    FROM private_messages pm
                    JOIN users u_sender ON pm.sender_id = u_sender.id
                    LEFT JOIN attachments a ON a.message_id = pm.id AND a.message_type = 'private'
                    WHERE ((pm.sender_id = ? AND pm.receiver_id = ?)
                    OR (pm.sender_id = ? AND pm.receiver_id = ?))
                    AND pm.timestamp > ?
                    ORDER BY pm.timestamp ASC
                ''', [user_id, other_user_id, other_user_id, user_id, timestamp])
                
                messages = []
                current_msg_id = None
                current_msg = None
                
                for row in cursor.fetchall():
                    msg_id = row[0]
                    if msg_id != current_msg_id:
                        if current_msg:
                            messages.append(current_msg)
                        current_msg = {
                            'id': msg_id,
                            'sender': row[2],
                            'message_text': row[1],
                            'timestamp': row[3],
                            'attachments': []
                        }
                        current_msg_id = msg_id
                    
                    if row[4]:  # Если есть вложение
                        current_msg['attachments'].append({
                            'path': row[4],
                            'mime_type': row[5],
                            'filename': row[6]
                        })
                
                if current_msg:
                    messages.append(current_msg)

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

class SearchUsersView(View):
    def response(self, environ, start_response):
        try:
            request = Request(environ)
            search_term = request.GET.get('q', '')
            
            with get_db_cursor() as cursor:
                cursor.execute('''
                    SELECT username FROM users 
                    WHERE username LIKE ? 
                    AND username != ?
                    LIMIT 10
                ''', (f'%{search_term}%', request.cookies.get('user_id')))
                
                users = [row[0] for row in cursor.fetchall()]
                return json_response({'users': users}, start_response)
                
        except Exception as e:
            return json_response({'error': str(e)}, start_response, '500 Internal Server Error')

class GetPrivateChatsView(View):
    def response(self, environ, start_response):
        try:
            request = Request(environ)
            user_id = request.cookies.get('user_id')
            if not user_id:
                return forbidden_response(start_response)

            with get_db_cursor() as cursor:

                cursor.execute('''
                    SELECT DISTINCT u.username, 
                           (SELECT MAX(timestamp) FROM private_messages 
                            WHERE (sender_id = ? AND receiver_id = u.id) 
                               OR (sender_id = u.id AND receiver_id = ?)) as last_activity
                    FROM users u
                    JOIN private_messages pm ON (pm.sender_id = u.id OR pm.receiver_id = u.id)
                    WHERE (pm.sender_id = ? OR pm.receiver_id = ?)
                    AND u.id != ?
                    ORDER BY last_activity DESC
                ''', (user_id, user_id, user_id, user_id, user_id))
                
                chats = [{
                    'username': row[0],
                    'last_activity': row[1] or 0
                } for row in cursor.fetchall()]

            return json_response({'chats': chats}, start_response)
            
        except Exception as e:
            print(f"Error in GetPrivateChatsView: {str(e)}")
            return json_response(
                {'error': 'Internal server error'}, 
                start_response, 
                '500 Internal Server Error'
            )
        
class SearchMessagesView(View):
    def response(self, environ, start_response):
        try:
            request = Request(environ)
            query_params = parse_qs(environ.get('QUERY_STRING', ''))
            
            # Получаем параметры
            search_query = query_params.get('q', [''])[0].strip()
            chat_type = query_params.get('type', ['general'])[0]
            chat_id = query_params.get('chat_id', [None])[0]
            page = int(query_params.get('page', ['1'])[0])
            per_page = int(query_params.get('per_page', ['20'])[0])
            sort = query_params.get('sort', ['date'])[0]
            
            if not search_query:
                return json_response({'error': 'Search query is required'}, start_response, '400 Bad Request')

            offset = (page - 1) * per_page
            user_id = request.cookies.get('user_id')
            
            if not user_id:
                return forbidden_response(start_response)

            with get_db_cursor() as cursor:
                if chat_type == 'group':
                    # Поиск в группе
                    cursor.execute('''
                        SELECT 
                            gm.message_id as id,
                            gm.message_text as text,
                            u.username as sender,
                            gm.timestamp,
                            gm.message_text as snippet
                        FROM group_messages gm
                        JOIN users u ON gm.user_id = u.id
                        WHERE gm.group_id = ? AND gm.message_text LIKE ? COLLATE NOCASE
                        ORDER BY gm.timestamp DESC
                        LIMIT ? OFFSET ?
                    ''', [chat_id, f'%{search_query}%', per_page, offset])
                    
                elif chat_type == 'private':
                    # Поиск в личных сообщениях
                    # Сначала получаем ID собеседника по username
                    cursor.execute("SELECT id FROM users WHERE username = ?", (chat_id,))
                    partner = cursor.fetchone()
                    if not partner:
                        return json_response({'error': 'User not found'}, start_response, '404 Not Found')
                    
                    partner_id = partner[0]
                    
                    cursor.execute('''
                        SELECT 
                            pm.id as id,
                            pm.message_text as text,
                            u.username as sender,
                            pm.timestamp,
                            pm.message_text as snippet
                        FROM private_messages pm
                        JOIN users u ON pm.sender_id = u.id
                        WHERE (
                            (pm.sender_id = ? AND pm.receiver_id = ?) OR 
                            (pm.sender_id = ? AND pm.receiver_id = ?)
                        )
                        AND pm.message_text LIKE ? COLLATE NOCASE
                        ORDER BY pm.timestamp DESC
                        LIMIT ? OFFSET ?
                    ''', [user_id, partner_id, partner_id, user_id, f'%{search_query}%', per_page, offset])
                    
                else:
                    # Поиск в общем чате
                    cursor.execute('''
                        SELECT 
                            message_id as id,
                            message_text as text,
                            sender,
                            timestamp,
                            message_text as snippet
                        FROM messages
                        WHERE message_text LIKE ? COLLATE NOCASE 
                        ORDER BY timestamp DESC
                        LIMIT ? OFFSET ?
                    ''', [f'%{search_query}%', per_page, offset])

                results = []
                for row in cursor.fetchall():
                    results.append({
                        'id': row[0],
                        'text': row[1],
                        'sender': row[2],
                        'timestamp': row[3],
                        'snippet': row[4]
                    })

                # Получаем общее количество
                if chat_type == 'group':
                    cursor.execute('''
                        SELECT COUNT(*) 
                        FROM group_messages 
                        WHERE group_id = ? AND message_text LIKE ? COLLATE NOCASE
                    ''', [chat_id, f'%{search_query}%'])
                elif chat_type == 'private':
                    cursor.execute('''
                        SELECT COUNT(*) 
                        FROM private_messages 
                        WHERE (
                            (sender_id = ? AND receiver_id = ?) OR 
                            (sender_id = ? AND receiver_id = ?)
                        )
                        AND message_text LIKE ? COLLATE NOCASE
                    ''', [user_id, partner_id, partner_id, user_id, f'%{search_query}%'])
                else:
                    cursor.execute('''
                        SELECT COUNT(*) 
                        FROM messages 
                        WHERE message_text LIKE ? COLLATE NOCASE
                    ''', [f'%{search_query}%'])

                total_count = cursor.fetchone()[0]

                return json_response({
                    'messages': results,
                    'total': total_count,
                    'page': page,
                    'per_page': per_page,
                    'total_pages': (total_count + per_page - 1) // per_page
                }, start_response)

        except Exception as e:
            logging.error(f"Search error: {str(e)}", exc_info=True)
            return json_response(
                {'error': str(e)},  # Возвращаем текст ошибки для отладки
                start_response,
                '500 Internal Server Error'
            )
class GetGroupMembersView(View):
    def response(self, environ, start_response):
        request = Request(environ)
        user_id = request.cookies.get('user_id')
        group_id = request.GET.get('group_id')
        
        if not user_id:
            return forbidden_response(start_response)

        with get_db_cursor() as cursor:
            # Проверяем что пользователь состоит в группе
            cursor.execute('''
                SELECT 1 FROM group_members 
                WHERE group_id = ? AND user_id = ?
            ''', (group_id, user_id))
            
            if not cursor.fetchone():
                return json_response(
                    {'error': 'Not a group member'}, 
                    start_response, 
                    '403 Forbidden'
                )
            
            # Получаем участников с ролями
            cursor.execute('''
                SELECT u.username, gm.role, gm.joined_at
                FROM group_members gm
                JOIN users u ON gm.user_id = u.id
                WHERE gm.group_id = ?
                ORDER BY 
                    CASE gm.role 
                        WHEN 'owner' THEN 1
                        WHEN 'admin' THEN 2
                        ELSE 3
                    END,
                    gm.joined_at
            ''', (group_id,))
            
            members = [{
                'username': row[0],
                'role': row[1],
                'joined_at': row[2]
            } for row in cursor.fetchall()]
            
            return json_response({'members': members}, start_response)

class GetGeneralMembersView(View):
    def response(self, environ, start_response):
        with get_db_cursor() as cursor:
            cursor.execute('SELECT username FROM users')
            members = [row[0] for row in cursor.fetchall()]
            return json_response({'members': members}, start_response)

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
        
class EditMessageView(View):
    def response(self, environ, start_response):
        try:
            message_id = int(environ['url_params'][0])
            query = parse_qs(environ['QUERY_STRING'])
            message_type = query.get('type', ['general'])[0]

            if message_type not in ['general', 'group', 'private']:
                return json_response(
                    {'error': 'Неверный тип сообщения'},
                    start_response,
                    '400 Bad Request'
                )

            user_id = self.get_user_id(environ)
            if not user_id:
                return forbidden_response(start_response)

            table_map = {
                'general': ('messages', 'message_id', 'user_id'),
                'group': ('group_messages', 'message_id', 'user_id'),
                'private': ('private_messages', 'id', 'sender_id')
            }

            table, id_col, user_col = table_map[message_type]

            content_length = int(environ.get('CONTENT_LENGTH', 0))
            data = json.loads(environ['wsgi.input'].read(content_length))
            new_text = data.get('message', '').strip()
            new_timestamp = data.get('timestamp', int(time.time()))
            
            if not new_text:
                return json_response(
                    {'error': 'Текст сообщения не может быть пустым'}, 
                    start_response, 
                    '400 Bad Request'
                )

            with get_db_cursor() as cursor:
                cursor.execute(f'''
                    SELECT {user_col} 
                    FROM {table} 
                    WHERE {id_col} = ?
                ''', (message_id,))
                result = cursor.fetchone()

                if not result:
                    return json_response(
                        {'error': 'Сообщение не найдено'}, 
                        start_response, 
                        '404 Not Found'
                    )

                if int(result[0]) != int(user_id):
                    return json_response(
                        {'error': 'Нет прав на редактирование'}, 
                        start_response, 
                        '403 Forbidden'
                    )

                cursor.execute(f'''
                    UPDATE {table} 
                    SET message_text = ?, timestamp = ?
                    WHERE {id_col} = ?
                ''', (new_text, new_timestamp, message_id))
                
                cursor.connection.commit()
                return json_response({'status': 'Сообщение обновлено'}, start_response)

        except Exception as e:
            logging.error(f"Ошибка редактирования: {str(e)}", exc_info=True)
            return json_response(
                {'error': 'Внутренняя ошибка сервера'}, 
                start_response, 
                '500 Internal Server Error'
            )

    def get_user_id(self, environ):
        request = Request(environ)
        return int(request.cookies.get('user_id', 0))
    
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
        
class CheckGroupsUpdatesView(View):
    def response(self, environ, start_response):
        try:
            request = Request(environ)
            user_id = request.cookies.get('user_id')
            if not user_id:
                return json_response({'updated': False}, start_response)

            last_check = int(request.GET.get('last_check', 0))
            
            with get_db_cursor() as cursor:
                # Проверяем изменения в членстве в группах
                cursor.execute('''
                    SELECT 1 FROM group_members 
                    WHERE user_id = ? AND timestamp > ?
                    LIMIT 1
                ''', (user_id, last_check))
                membership_updated = cursor.fetchone() is not None
                
                # Проверяем изменения в самих группах (например, переименование)
                cursor.execute('''
                    SELECT 1 FROM groups g
                    JOIN group_members gm ON g.group_id = gm.group_id
                    WHERE gm.user_id = ? AND g.created_at > ?
                    LIMIT 1
                ''', (user_id, last_check))
                groups_updated = cursor.fetchone() is not None
                
                # Проверяем новые сообщения в группах
                cursor.execute('''
                    SELECT 1 FROM group_messages
                    WHERE group_id IN (
                        SELECT group_id FROM group_members WHERE user_id = ?
                    ) AND timestamp > ?
                    LIMIT 1
                ''', (user_id, last_check))
                messages_updated = cursor.fetchone() is not None
                
                updated = membership_updated or groups_updated or messages_updated
                return json_response({
                    'updated': updated,
                    'new_timestamp': int(time.time())  # Возвращаем текущее время для следующей проверки
                }, start_response)
                
        except Exception as e:
            logging.error(f"CheckGroupsUpdates error: {str(e)}")
            return json_response({'updated': False}, start_response)

class CheckPrivateChatsUpdatesView(View):
    def response(self, environ, start_response):
        try:
            request = Request(environ)
            user_id = request.cookies.get('user_id')
            if not user_id:
                return json_response({'updated': False}, start_response)

            with get_db_cursor() as cursor:
                # Получаем timestamp последнего сообщения в приватных чатах
                cursor.execute('''
                    SELECT MAX(timestamp) FROM (
                        SELECT MAX(timestamp) as timestamp 
                        FROM private_messages 
                        WHERE sender_id = ? OR receiver_id = ?
                        GROUP BY 
                            CASE WHEN sender_id = ? THEN receiver_id ELSE sender_id END
                    )
                ''', (user_id, user_id, user_id))
                
                last_update = cursor.fetchone()[0] or 0
                
                # Проверяем новые сообщения
                cursor.execute('''
                    SELECT 1 FROM private_messages
                    WHERE (sender_id = ? OR receiver_id = ?)
                    AND timestamp > ?
                    LIMIT 1
                ''', (user_id, user_id, last_update))
                
                updated = cursor.fetchone() is not None
                return json_response({'updated': updated}, start_response)
                
        except Exception as e:
            logging.error(f"CheckPrivateChatsUpdates error: {str(e)}")
            return json_response({'updated': False}, start_response)
        
def check_group_permissions(cursor, user_id, group_id, required_role=None):
    """Проверяет права пользователя в группе"""
    cursor.execute('''
        SELECT role FROM group_members 
        WHERE group_id = ? AND user_id = ?
    ''', (group_id, user_id))
    result = cursor.fetchone()
    
    if not result:
        return False  # Пользователь не в группе
    
    user_role = result[0]
    
    if required_role == 'owner':
        return user_role == 'owner'
    elif required_role == 'admin':
        return user_role in ('owner', 'admin')
    
    return True  # Для обычных участников

class ChangeMemberRoleView(View):
    def response(self, environ, start_response):
        try:
            request = Request(environ)
            user_id = request.cookies.get('user_id')
            
            if not user_id:
                return json_response(
                    {'error': 'Not authorized'}, 
                    start_response, 
                    '401 Unauthorized'
                )

            content_length = int(environ.get('CONTENT_LENGTH', 0))
            post_data = json.loads(environ['wsgi.input'].read(content_length))
            
            group_id = post_data.get('group_id')
            username = post_data.get('username')
            new_role = post_data.get('role')

            if not all([group_id, username, new_role]):
                return json_response(
                    {'error': 'Missing parameters'}, 
                    start_response, 
                    '400 Bad Request'
                )

            if new_role not in ['owner', 'admin', 'member']:
                return json_response(
                    {'error': 'Invalid role'}, 
                    start_response, 
                    '400 Bad Request'
                )

            with get_db_cursor() as cursor:
                # Проверяем права текущего пользователя
                cursor.execute('''
                    SELECT role FROM group_members 
                    WHERE group_id = ? AND user_id = ?
                ''', (group_id, user_id))
                current_user_role = cursor.fetchone()
                
                if not current_user_role or current_user_role[0] not in ['owner', 'admin']:
                    return json_response(
                        {'error': 'Недостаточно прав'}, 
                        start_response, 
                        '403 Forbidden'
                    )
                
                # Получаем ID целевого пользователя
                cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
                target_user = cursor.fetchone()
                if not target_user:
                    return json_response(
                        {'error': 'User not found'}, 
                        start_response, 
                        '404 Not Found'
                    )
                
                target_user_id = target_user[0]
                
                # Проверяем что не пытаемся изменить себя
                if target_user_id == user_id and new_role != 'owner':
                    return json_response(
                        {'error': 'Нельзя изменить свою роль'}, 
                        start_response, 
                        '400 Bad Request'
                    )
                
                # Проверяем текущую роль целевого пользователя
                cursor.execute('''
                    SELECT role FROM group_members 
                    WHERE group_id = ? AND user_id = ?
                ''', (group_id, target_user_id))
                target_current_role = cursor.fetchone()
                
                if not target_current_role:
                    return json_response(
                        {'error': 'User not in group'}, 
                        start_response, 
                        '400 BadRequest'
                    )
                
                # Только владелец может назначать владельца
                if new_role == 'owner' and current_user_role[0] != 'owner':
                    return json_response(
                        {'error': 'Только владелец может передавать права'}, 
                        start_response, 
                        '403 Forbidden'
                    )
                
                # Обновляем роль
                cursor.execute('''
                    UPDATE group_members 
                    SET role = ?
                    WHERE group_id = ? AND user_id = ?
                ''', (new_role, group_id, target_user_id))
                
                # Если передаем владение, меняем свою роль на admin
                if new_role == 'owner':
                    cursor.execute('''
                        UPDATE group_members 
                        SET role = 'admin'
                        WHERE group_id = ? AND user_id = ?
                    ''', (group_id, user_id))
                
                # Добавляем системное сообщение
                role_names = {
                    'owner': 'владельцем',
                    'admin': 'администратором',
                    'member': 'участником'
                }
                
                cursor.execute('''
                    INSERT INTO group_messages 
                    (group_id, user_id, message_text, timestamp)
                    VALUES (?, 0, ?, ?)
                ''', (group_id, f'Пользователь {username} назначен {role_names[new_role]}', int(time.time())))
                
                cursor.connection.commit()
                
                return json_response({
                    'status': 'success',
                    'new_role': new_role
                }, start_response)
                
        except Exception as e:
            logging.error(f"ChangeMemberRole error: {str(e)}")
            return json_response(
                {'error': 'Internal Server Error'}, 
                start_response, 
                '500 Internal Server Error'
            )
        
class RenameGroupView(View):
    def response(self, environ, start_response):
        try:
            request = Request(environ)
            user_id = request.cookies.get('user_id')
            
            if not user_id:
                return json_response(
                    {'error': 'Not authorized'}, 
                    start_response, 
                    '401 Unauthorized'
                )

            content_length = int(environ.get('CONTENT_LENGTH', 0))
            post_data = json.loads(environ['wsgi.input'].read(content_length))
            
            group_id = post_data.get('group_id')
            new_name = post_data.get('new_name')

            if not group_id or not new_name:
                return json_response(
                    {'error': 'Missing parameters'}, 
                    start_response, 
                    '400 Bad Request'
                )

            with get_db_cursor() as cursor:
                # Проверяем права пользователя
                cursor.execute('''
                    SELECT role FROM group_members 
                    WHERE group_id = ? AND user_id = ?
                ''', (group_id, user_id))
                result = cursor.fetchone()
                
                if not result or result[0] not in ('owner', 'admin'):
                    return json_response(
                        {'error': 'Недостаточно прав для изменения названия группы'},
                        start_response,
                        '403 Forbidden'
                    )
                
                # Проверяем, что новое имя не занято
                cursor.execute('''
                    SELECT 1 FROM groups 
                    WHERE name = ? AND group_id != ?
                ''', (new_name, group_id))
                if cursor.fetchone():
                    return json_response(
                        {'error': 'Группа с таким именем уже существует'},
                        start_response,
                        '400 Bad Request'
                    )
                
                # Обновляем название группы
                cursor.execute('''
                    UPDATE groups 
                    SET name = ? 
                    WHERE group_id = ?
                ''', (new_name, group_id))
                
                # Добавляем системное сообщение
                cursor.execute('''
                    INSERT INTO group_messages 
                    (group_id, user_id, message_text, timestamp)
                    VALUES (?, 0, ?, ?)
                ''', (group_id, f'Название группы изменено на "{new_name}"', int(time.time())))
                
                cursor.connection.commit()
                
                return json_response(
                    {'status': 'success', 'new_name': new_name}, 
                    start_response
                )
                
        except Exception as e:
            logging.error(f"RenameGroup error: {str(e)}")
            return json_response(
                {'error': 'Internal Server Error'}, 
                start_response, 
                '500 Internal Server Error'
            )
        
class RemoveFromGroupView(View):
    def response(self, environ, start_response):
        try:
            request = Request(environ)
            user_id = request.cookies.get('user_id')
            
            if not user_id:
                return json_response(
                    {'error': 'Not authorized'}, 
                    start_response, 
                    '401 Unauthorized'
                )

            content_length = int(environ.get('CONTENT_LENGTH', 0))
            post_data = json.loads(environ['wsgi.input'].read(content_length))
            
            group_id = post_data.get('group_id')
            username = post_data.get('username')

            if not all([group_id, username]):
                return json_response(
                    {'error': 'Missing parameters'}, 
                    start_response, 
                    '400 Bad Request'
                )

            with get_db_cursor() as cursor:
                cursor.execute('''
                    SELECT role FROM group_members 
                    WHERE group_id = ? AND user_id = ?
                ''', (group_id, user_id))
                current_user_role = cursor.fetchone()
                
                if not current_user_role:
                    return json_response(
                        {'error': 'Вы не состоите в этой группе'}, 
                        start_response, 
                        '403 Forbidden'
                    )
                
                current_user_role = current_user_role[0]
                
                cursor.execute('''
                    SELECT id, role FROM users 
                    JOIN group_members ON users.id = group_members.user_id
                    WHERE username = ? AND group_id = ?
                ''', (username, group_id))
                target_user = cursor.fetchone()
                
                if not target_user:
                    return json_response(
                        {'error': 'Пользователь не найден в группе'}, 
                        start_response, 
                        '404 Not Found'
                    )
                
                target_user_id, target_user_role = target_user
                
                if current_user_role == 'owner':
                    pass
                elif current_user_role == 'admin':
                    if target_user_role != 'member':
                        return json_response(
                            {'error': 'Вы можете исключать только участников'}, 
                            start_response, 
                            '403 Forbidden'
                        )
                else:
                    return json_response(
                        {'error': 'Недостаточно прав для исключения'}, 
                        start_response, 
                        '403 Forbidden'
                    )
                
                if target_user_id == user_id:
                    return json_response(
                        {'error': 'Нельзя исключить самого себя'}, 
                        start_response, 
                        '400 Bad Request'
                    )
                
                cursor.execute('''
                    DELETE FROM group_members 
                    WHERE group_id = ? AND user_id = ?
                ''', (group_id, target_user_id))
                
                cursor.execute('''
                    INSERT INTO group_messages 
                    (group_id, user_id, message_text, timestamp)
                    VALUES (?, 0, ?, ?)
                ''', (group_id, f'Пользователь {username} исключен из группы', int(time.time())))
                
                cursor.execute('''
                    DELETE FROM group_messages 
                    WHERE group_id = ? AND user_id = ? AND timestamp > ?
                ''', (group_id, target_user_id, int(time.time())))
                
                cursor.connection.commit()
                
                return json_response({
                    'status': 'success',
                    'removed_user': username,
                    'group_id': group_id,
                    'is_current_user': (target_user_id == int(user_id)),
                    'message': 'Пользователь успешно исключен'
                }, start_response)
                
        except Exception as e:
            logging.error(f"RemoveFromGroup error: {str(e)}")
            return json_response(
                {'error': 'Internal Server Error'}, 
                start_response, 
                '500 Internal Server Error'
            )
        
class GetGeneralMembersView(View):
    def response(self, environ, start_response):
        with get_db_cursor() as cursor:
            cursor.execute('SELECT username FROM users')
            members = [row[0] for row in cursor.fetchall()]
            return json_response({'members': members}, start_response)
        
class CheckGroupsUpdatesView(View):
    def response(self, environ, start_response):
        try:
            request = Request(environ)
            user_id = request.cookies.get('user_id')
            if not user_id:
                return json_response({'updated': False}, start_response)

            last_check = int(request.GET.get('last_check', 0))
            force_update = request.GET.get('force', 'false').lower() == 'true'
            
            with get_db_cursor() as cursor:
                #Проверка нового пользователя
                cursor.execute('''
                    SELECT 1 FROM group_members 
                    WHERE user_id = ? AND joined_at > ?
                    LIMIT 1
                ''', (user_id, last_check))
                new_groups = cursor.fetchone() is not None
                
                #Проверка изменений
                cursor.execute('''
                    SELECT 1 FROM groups g
                    JOIN group_members gm ON g.group_id = gm.group_id
                    WHERE gm.user_id = ? AND g.updated_at > ?
                    LIMIT 1
                ''', (user_id, last_check))
                groups_updated = cursor.fetchone() is not None
                
                # Проверка новых сообщений
                cursor.execute('''
                    SELECT 1 FROM group_messages
                    WHERE group_id IN (
                        SELECT group_id FROM group_members WHERE user_id = ?
                    ) AND timestamp > ?
                    LIMIT 1
                ''', (user_id, last_check))
                messages_updated = cursor.fetchone() is not None
                
                updated = new_groups or groups_updated or messages_updated or force_update
                return json_response({
                    'updated': updated,
                    'new_timestamp': int(time.time())
                }, start_response)
                
        except Exception as e:
            logging.error(f"CheckGroupsUpdates error: {str(e)}")
            return json_response({'updated': False}, start_response)