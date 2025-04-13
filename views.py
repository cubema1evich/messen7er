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
                a.filename
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

                    # Обработка файлов (только если есть файлы и сообщение было сохранено)
                    if files and message_id:
                        unique_files = set()
                        for file in files:
                            if file.filename and file.file:
                                file_content = file.file.read()
                                file_hash = hashlib.md5(file_content).hexdigest()
                                file.file.seek(0)

                                # Проверка на дубликаты
                                cursor.execute('''
                                    SELECT id FROM attachments 
                                    WHERE file_path = ? AND message_type = ?
                                ''', (f'/static/uploads/{file_hash}_{secure_filename(file.filename)}', message_type))
                                
                                if cursor.fetchone():
                                    continue
                                
                                if file_hash in unique_files:
                                    continue
                                unique_files.add(file_hash)

                                filename = secure_filename(file.filename)
                                unique_name = f"{file_hash}_{filename}"
                                file_path = os.path.join('static', 'uploads', unique_name)
                                
                                if not os.path.exists(file_path):
                                    with open(file_path, 'wb') as f:
                                        f.write(file.file.read())
                                
                                cursor.execute('''
                                    INSERT INTO attachments 
                                    (message_type, message_id, file_path, mime_type, filename)
                                    VALUES (?, ?, ?, ?, ?)
                                ''', ('private' if message_type == 'private' else message_type, 
                                    message_id, 
                                    f'/static/uploads/{unique_name}', 
                                    file.type, 
                                    filename))
                                
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
                # Создаем группу
                cursor.execute('''
                    INSERT INTO groups (name, creator_id, created_at)
                    VALUES (?, ?, ?)
                ''', (group_name, user_id, int(time.time())))
                
                group_id = cursor.lastrowid
                
                # Добавляем создателя
                cursor.execute('''
                    INSERT INTO group_members (group_id, user_id, role)
                    VALUES (?, ?, ?)
                ''', (group_id, user_id, 'owner'))
                
                cursor.connection.commit()
                return json_response(
                    {'status': 'success', 'group_id': group_id}, 
                    start_response
                )

        except Exception as e:
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
            content_length = int(environ.get('CONTENT_LENGTH', 0))
            post_data = json.loads(request.body.decode('utf-8'))
            
            group_id = post_data.get('group_id')
            username = post_data.get('username')
            role = post_data.get('role', 'member')

            # Проверка наличия всех параметров
            if not all([user_id, group_id, username]):
                return json_response({'error': 'Missing parameters'}, start_response, '400 Bad Request')

            conn = sqlite3.connect('data.db')
            cursor = conn.cursor()

            # Проверка прав пользователя
            cursor.execute('''
                SELECT role FROM group_members 
                WHERE group_id = ? AND user_id = ?
            ''', (group_id, user_id))
            user_role = cursor.fetchone()
            
            if not user_role or user_role[0] not in ['owner', 'admin']:
                return forbidden_response(start_response)

            # Поиск ID добавляемого пользователя
            cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
            target_user = cursor.fetchone()
            if not target_user:
                return json_response({'error': 'User not found'}, start_response, '404 Not Found')
            
            target_user_id = target_user[0]

            # Добавление в группу
            cursor.execute('''
                INSERT OR IGNORE INTO group_members (group_id, user_id, role)
                VALUES (?, ?, ?)
            ''', (group_id, target_user_id, role))
            
            conn.commit()
            return json_response({'status': 'success'}, start_response)
            
        except Exception as e:
            print(f"Error: {str(e)}")  # Логирование ошибки
            return json_response({'error': 'Internal Server Error'}, start_response, '500 Internal Server Error')
        finally:
            if 'conn' in locals():
                conn.close()
                            
class GetGroupsView(View):
    def response(self, environ, start_response):
        request = Request(environ)
        user_id = request.cookies.get('user_id')
        
        if not user_id:
            return json_response(
                {'error': 'Not authorized'}, 
                start_response, 
                '401 Unauthorized'
            )

        conn = sqlite3.connect('data.db')
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                SELECT g.group_id, g.name 
                FROM groups g
                JOIN group_members gm ON g.group_id = gm.group_id
                WHERE gm.user_id = ?
            ''', (user_id,))
            
            groups = [{
                'id': row[0],
                'name': row[1]
            } for row in cursor.fetchall()]
            
            return json_response(groups, start_response)
        
        finally:
            conn.close()

class GetGroupMessagesView(View):
    def response(self, environ, start_response):
        try:
            request = Request(environ)
            group_id = request.GET.get('group_id')
            timestamp = int(request.GET.get('timestamp', 0))
            user_id = request.cookies.get('user_id')

            if not user_id:
                return forbidden_response(start_response)

            with get_db_cursor() as cursor:
                # Проверка членства в группе
                cursor.execute('''
                    SELECT 1 FROM group_members 
                    WHERE group_id = ? AND user_id = ?
                ''', (group_id, user_id))
                if not cursor.fetchone():
                    return forbidden_response(start_response)

                cursor.execute('''
                    SELECT 
                        gm.message_id,
                        u.username,
                        gm.message_text,
                        gm.timestamp,
                        a.file_path,
                        a.mime_type,
                        a.filename
                    FROM group_messages gm
                    JOIN users u ON gm.user_id = u.id
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
            logging.error(f"GetGroupMessages error: {str(e)}")
            return json_response(
                {'error': 'Internal server error'}, 
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
            content_length = int(environ.get('CONTENT_LENGTH', 0))
            post_data = json.loads(request.body.decode('utf-8'))
            group_id = post_data.get('group_id')

            if not user_id or not group_id:
                return forbidden_response(start_response)

            conn = sqlite3.connect('data.db')
            cursor = conn.cursor()
            
            # Удаляем пользователя из группы
            cursor.execute('''
                DELETE FROM group_members 
                WHERE group_id = ? AND user_id = ?
            ''', (group_id, user_id))
            
            conn.commit()
            return json_response({'status': 'success'}, start_response)
            
        except Exception as e:
            return json_response({'error': str(e)}, start_response, '500 Internal Server Error')
        finally:
            conn.close()

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

            if not user_id or not other_user:
                return forbidden_response(start_response)

            with get_db_cursor() as cursor:
                # Получаем ID собеседника
                cursor.execute('SELECT id FROM users WHERE username = ?', (other_user,))
                result = cursor.fetchone()
                if not result:
                    return json_response({'error': 'User not found'}, start_response, '404 Not Found')
                other_user_id = result[0]

                cursor.execute('''
                    SELECT 
                        pm.id,
                        pm.message_text,
                        u.username,
                        pm.timestamp,
                        a.file_path, 
                        a.mime_type, 
                        a.filename
                    FROM private_messages pm
                    JOIN users u ON pm.sender_id = u.id
                    LEFT JOIN attachments a ON a.message_id = pm.id AND a.message_type = 'private'
                    WHERE 
                        ((pm.sender_id = ? AND pm.receiver_id = ?)
                        OR 
                        (pm.sender_id = ? AND pm.receiver_id = ?))
                    AND pm.timestamp > ?
                    ORDER BY pm.timestamp ASC
                ''', (user_id, other_user_id, other_user_id, user_id, timestamp))
                
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
                # Улучшенный запрос с проверкой существования пользователя
                cursor.execute('''
                    SELECT u.username, MAX(pm.timestamp) as last_activity
                    FROM (
                        SELECT sender_id as user_id, timestamp 
                        FROM private_messages 
                        WHERE receiver_id = ?
                        UNION ALL
                        SELECT receiver_id as user_id, timestamp 
                        FROM private_messages 
                        WHERE sender_id = ?
                    ) pm
                    JOIN users u ON pm.user_id = u.id
                    WHERE u.id != ?
                    GROUP BY u.username
                    ORDER BY last_activity DESC
                ''', (user_id, user_id, user_id))
                
                chats = [{
                    'username': row[0],
                    'last_activity': row[1] or 0  # Защита от NULL
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