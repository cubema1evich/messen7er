from collections import namedtuple
import sqlite3
import json
import time
import uuid

from urllib.parse import parse_qs
from mimes import get_mime
from webob import Request

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
    pass

class GetMessageView(View):
    def __init__(self, url) -> None:
        super().__init__(url)
        self.last_timestamp = 0

    def response(self, environ, start_response):
        headers = [('Content-type', 'application/json')]
        status = '200 OK'

        query_params = parse_qs(environ.get('QUERY_STRING', ''))
        timestamp = int(query_params.get('timestamp', [0])[0])

        messages, timestamp = self.get_new_messages_from_db(timestamp)
        data = json.dumps({'messages': messages, 'timestamp': timestamp})

        #print(f"Sending messages: {data}")

        start_response(status, headers)
        return [data.encode('utf-8')]

    def get_new_messages_from_db(self, timestamp):
        conn = sqlite3.connect('data.db')
        cursor = conn.cursor()
        cursor.execute('SELECT sender, message_text, timestamp FROM messages WHERE timestamp > ?', (timestamp,))
        messages = cursor.fetchall()
        conn.close()

        if messages:
            timestamp = max(msg[2] for msg in messages)
        else:
            timestamp = timestamp

        formatted_messages = [
            {'sender': msg[0], 'message_text': msg[1].split(': ', 1)[1]} if msg[0] else {'sender': 'Guest', 'message_text': msg[1].split(': ', 1)[1]} for msg in messages
        ]

        return formatted_messages, timestamp

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
        headers = [
            ('Content-type', 'application/json'),
            ('Access-Control-Allow-Origin', 'http://localhost:8000'),  
            ('Access-Control-Allow-Credentials', 'true'), 
            ]

        request = Request(environ)

        user_id_cookie = request.cookies.get('user_id')

        if user_id_cookie:
            user_id = user_id_cookie
        else:
            user_id = None

        print("Response from /get_user_id:", {"user_id": user_id})

        if user_id is None:
            print("User ID is None. Cannot fetch messages.")
            status = '200 OK'
            data = json.dumps({'user_id': None})
            start_response(status, headers)
            return [data.encode('utf-8')]
        else:
            print(f"Fetching messages for user_id: {user_id}")

            fetched_user_id = self.fetch_user_id_from_database(user_id)

            if fetched_user_id is not None:
                user_id = fetched_user_id

            print("Fetched user_id:", user_id)

            status = '200 OK'
            data = json.dumps({'user_id': str(user_id)})  
            start_response(status, headers + [('Set-Cookie', f'user_id={user_id}; Path=/')])
            return [data.encode('utf-8')]
        
class SendMessageView(View):
    def response(self, environ, start_response):
        message, username = self.get_message_and_user_from_request(environ)
        #print("Data before sending:", message, username)

        if message and username:
            timestamp = int(time.time())
            username = self.get_nickname_from_database(username) or 'Guest'
            full_message = f"{username}: {message}"
            self.save_message_to_db(full_message, username, timestamp)

            status = '200 OK'
            headers = [('Content-type', 'application/json')]
            data = json.dumps({'message': 'Сообщение успешно получено и сохранено'})
            #print("Data after sending:", message, username)
        else:
            status = '400 Bad Request'
            headers = [('Content-type', 'application/json')]
            data = json.dumps({'error': 'Неверное сообщение или пользователь'})
            #print("Data after sending:", message, username)

        start_response(status, headers)
        return [data.encode('utf-8')]
    
    def save_message_to_db(self, message, username, timestamp, group_id=None):
        conn = sqlite3.connect('data.db')
        cursor = conn.cursor()
        user_id = self.get_nickname_from_database(username)
        
        if group_id:
            cursor.execute('''
                INSERT INTO group_messages 
                (group_id, user_id, message, timestamp)
                VALUES (?, ?, ?, ?)
            ''', (group_id, user_id, message, timestamp))
        else:
            cursor.execute('''
                INSERT INTO messages 
                (user_id, sender, message_text, timestamp)
                VALUES (?, ?, ?, ?)
            ''', (user_id, username, message, timestamp))
        
        conn.commit()
        conn.close()

    def get_message_and_user_from_request(self, environ):
        try:
            request_body_size = int(environ.get('CONTENT_LENGTH', 0))
            request_body = environ['wsgi.input'].read(request_body_size).decode('utf-8')

            parsed_body = json.loads(request_body)

            message = parsed_body.get('message', '')
            username = parsed_body.get('username', '') or 'Guest'

            if not message or not username:  
                raise ValueError("Invalid message or username")

            print(f"Received message: {message}, username: {username}")

            return message, username
        except ValueError as ve:
            print(f"ValueError: {ve}")
            return None, None
        except Exception as e:
            print(f"Error while extracting message, username, and user_id: {e}")
            return None, None


    def get_nickname_from_database(self, username):
        conn = sqlite3.connect('data.db')
        cursor = conn.cursor()
        cursor.execute('SELECT username FROM users WHERE username=?', (username,))
        nickname = cursor.fetchone()
        conn.close()

        if nickname:
            return nickname[0]
        else:
            return None

class RegisterView(TemplateView):
    template = 'templates/register.html'

    def response(self, environ, start_response):
        request = Request(environ)
        if request.method == 'POST':
            post_data = request.POST
            username = post_data.get('username', '')
            password = post_data.get('password', '')

            if username and password:
                success = self.register_user(username, password)
                if success:
                    status = '200 OK'
                    headers = [('Content-type', 'application/json')]
                    data = json.dumps({'message': 'User registered successfully'})
                else:
                    status = '400 Bad Request'
                    headers = [('Content-type', 'application/json')]
                    data = json.dumps({'error': 'Username already exists'})
            else:
                status = '400 Bad Request'
                headers = [('Content-type', 'application/json')]
                data = json.dumps({'error': 'Invalid username or password'})

            start_response(status, headers)
            return [data.encode('utf-8')]

        return super().response(environ, start_response)

    def register_user(self, username, password):
        print(f"Received username reg_us: {username}, password: {password}")
        conn = sqlite3.connect('data.db')
        cursor = conn.cursor()

        user_id = uuid.uuid4().hex # Генерируем уникальный идентификатор пользователя

        cursor.execute('SELECT * FROM users WHERE username=?', (username,))
        existing_user = cursor.fetchone()

        if existing_user:
            conn.close()
            return False  # Пользователь с таким именем уже существует

        cursor.execute('INSERT INTO users (username, password, user_id) VALUES (?, ?, ?)', (username, password, user_id))
        conn.commit()
        conn.close()
        return True  # Пользователь успешно зарегистрирован

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
            username = post_data.get('username', [''])[0]
            password = post_data.get('password', [''])[0]

            if username and password:
                user_id = self.authenticate_user(username, password)
                if user_id:
                    status = '200 OK'
                    headers = [('Content-type', 'application/json')]
                    data = json.dumps({'redirect': '/', 'user_id': str(user_id[0])})  
                    start_response(status, headers)
                    return [data.encode('utf-8')]
                else:
                    status = '401 Unauthorized'
                    headers = [('Content-type', 'application/json')]
                    data = json.dumps({'error': 'Invalid username or password'})
                    start_response(status, headers)
                    return [data.encode('utf-8')]
            else:
                status = '400 Bad Request'
                headers = [('Content-type', 'application/json')]
                data = json.dumps({'error': 'Invalid username or password'})
                start_response(status, headers)
                return [data.encode('utf-8')]
        else:
            return super().response(environ, start_response)

    def authenticate_user(self, username, password):
        conn = sqlite3.connect('data.db')
        cursor = conn.cursor()

        #print(f"Received username: {username}, password: {password}")
    
        cursor.execute('SELECT user_id FROM users WHERE username=? AND password=?', (username, password))
        user_id = cursor.fetchone()

        conn.close()    

        #print("Authenticated user_id:", user_id)  

        return str(user_id[0]) if user_id else None



    def get_post_data(self, request):
        try:
            data = request.POST
            return data
        except Exception as e:
            print(f"Error while extracting POST data: {e}")
            return None
        
class CreateGroupView(View):
    def response(self, environ, start_response):
        conn = None  # Инициализируем переменную заранее
        try:
            # Проверка метода запроса
            if environ['REQUEST_METHOD'] != 'POST':
                return json_response(
                    {'error': 'Method not allowed'}, 
                    start_response, 
                    '405 Method Not Allowed'
                )

            # Получение данных
            request = Request(environ)
            user_id = request.cookies.get('user_id')
            
            # Получение POST-данных
            content_length = int(environ.get('CONTENT_LENGTH', 0))
            post_data = json.loads(environ['wsgi.input'].read(content_length))
            group_name = post_data.get('name', '')

            # Валидация
            if not user_id:
                return json_response(
                    {'error': 'Unauthorized'}, 
                    start_response, 
                    '401 Unauthorized'
                )

            if not group_name:
                return json_response(
                    {'error': 'Group name required'}, 
                    start_response, 
                    '400 Bad Request'
                )

            # Подключение к БД
            conn = sqlite3.connect('data.db')
            cursor = conn.cursor()

            # Создание группы
            cursor.execute('''
                INSERT INTO groups (name, creator_id, created_at)
                VALUES (?, ?, ?)
            ''', (group_name, user_id, int(time.time())))
            
            group_id = cursor.lastrowid

            # Добавление создателя в группу
            cursor.execute('''
                INSERT INTO group_members (group_id, user_id, role)
                VALUES (?, ?, ?)
            ''', (group_id, user_id, 'owner'))

            conn.commit()
            return json_response(
                {'status': 'success', 'group_id': group_id}, 
                start_response
            )

        except json.JSONDecodeError:
            return json_response(
                {'error': 'Invalid JSON'}, 
                start_response, 
                '400 Bad Request'
            )
        except sqlite3.Error as e:
            print(f"[DATABASE ERROR] {e}")
            return json_response(
                {'error': 'Database error'}, 
                start_response, 
                '500 Internal Server Error'
            )
        except Exception as e:
            print(f"[GENERAL ERROR] {e}")
            return json_response(
                {'error': 'Internal server error'}, 
                start_response, 
                '500 Internal Server Error'
            )
        finally:
            if conn:  # Закрываем соединение только если оно было открыто
                conn.close()
                                
class AddToGroupView(View):
        def check_permission(self, user_id, group_id):
            # Проверка что пользователь имеет права администратора
            conn = sqlite3.connect('data.db')
            cursor = conn.cursor()
            cursor.execute('''
                SELECT role FROM group_members 
                WHERE group_id = ? AND user_id = ?
            ''', (group_id, user_id))
            role = cursor.fetchone()
            return role and role[0] in ['owner', 'admin']

        def response(self, environ, start_response):
            request = Request(environ)
            user_id = request.cookies.get('user_id')
            post_data = parse_qs(request.body.decode('utf-8'))
            
            target_user_id = post_data.get('user_id', [''])[0]
            group_id = post_data.get('group_id', [''])[0]
            role = post_data.get('role', ['member'])[0]

            if not self.check_permission(user_id, group_id):
                return forbidden_response(start_response)

            conn = sqlite3.connect('data.db')
            cursor = conn.cursor()
            
            try:
                cursor.execute('''
                    INSERT INTO group_members (group_id, user_id, role)
                    VALUES (?, ?, ?)
                ''', (group_id, target_user_id, role))
                
                conn.commit()
                return json_response({'status': 'success'})
            except sqlite3.IntegrityError:
                return json_response({'error': 'User already in group'})
            finally:
                conn.close()
            
class GetGroupsView(View):
    def response(self, environ, start_response):
        user_id = Request(environ).cookies.get('user_id')
        
        conn = sqlite3.connect('data.db')
        cursor = conn.cursor()
        
        # Получаем все группы, где пользователь является участником
        cursor.execute('''
            SELECT g.group_id, g.name, gm.role 
            FROM groups g
            JOIN group_members gm ON g.group_id = gm.group_id
            WHERE gm.user_id = ?
        ''', (user_id,))
        
        groups = [{
            'id': row[0],
            'name': row[1],
            'role': row[2]
        } for row in cursor.fetchall()]
        
        conn.close()
        
        return json_response(groups, start_response)

class GetGroupMessagesView(View):
    def response(self, environ, start_response):
        group_id = Request(environ).GET.get('group_id')
        timestamp = Request(environ).GET.get('timestamp', 0)
        
        conn = sqlite3.connect('data.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT u.username, gm.message, gm.timestamp
            FROM group_messages gm
            JOIN users u ON gm.user_id = u.user_id
            WHERE gm.group_id = ? AND gm.timestamp > ?
            ORDER BY gm.timestamp
        ''', (group_id, timestamp))
        
        messages = [{
            'sender': row[0],
            'text': row[1],
            'timestamp': row[2]
        } for row in cursor.fetchall()]
        
        conn.close()
        
        return json_response({'messages': messages}, start_response)

    def group_permission_required(required_role='member'):
        def decorator(func):
            def wrapper(self, environ, start_response):
                request = Request(environ)
                user_id = request.cookies.get('user_id')
                group_id = request.GET.get('group_id') or request.POST.get('group_id')
                
                conn = sqlite3.connect('data.db')
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT role FROM group_members 
                    WHERE user_id = ? AND group_id = ?
                ''', (user_id, group_id))
                role = cursor.fetchone()
                conn.close()
                
                if not role or role[0] not in ['owner', 'admin', required_role]:
                    return forbidden_response(start_response)
                
                return func(self, environ, start_response)
            return wrapper
        return decorator
