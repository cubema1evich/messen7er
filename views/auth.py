import sqlite3
import json
import logging
import re

from urllib.parse import parse_qs
from webob import Request

from utils import *
from .base import json_response, TemplateView


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

            try:
                user_id, error = self.authenticate_user(username, password)
                if user_id:
                    headers = [
                        ('Content-Type', 'application/json'),
                        ('Set-Cookie', f'user_id={user_id}; Path=/; HttpOnly; SameSite=Lax')
                    ]
                    data = json.dumps({'redirect': '/'})
                    start_response('200 OK', headers)
                    return [data.encode('utf-8')]
                else:
                    return json_response(
                        {'error': error},
                        start_response,
                        '401 Unauthorized'
                    )
            except Exception as e:
                logging.error(f"Login error: {str(e)}")
                return json_response(
                    {'error': 'Внутренняя ошибка сервера'},
                    start_response,
                    '500 Internal Server Error'
                )
        return super().response(environ, start_response)
        
    def authenticate_user(self, username, password):
        try:
            with get_db_cursor() as cursor:
                # Проверка существования пользователя
                cursor.execute(
                    'SELECT id, password FROM users WHERE username=?',
                    (username,)
                )
                result = cursor.fetchone()
                
                if not result:
                    return None, 'Пользователь не найден'
                
                user_id, hashed_password = result
                if not check_password(hashed_password, password):
                    return None, 'Неверный пароль'
                
                return user_id, None
        except Exception as e:
            raise

    def get_post_data(self, request):
        try:
            data = request.POST
            return data
        except Exception as e:
            print(f"Error while extracting POST data: {e}")
            return None