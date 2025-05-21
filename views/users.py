import sqlite3
import json
import time
import logging


from webob import Request

from utils import *
from .base import View, json_response


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

class GetGeneralMembersView(View):
    def response(self, environ, start_response):
        with get_db_cursor() as cursor:
            cursor.execute('SELECT username FROM users')
            members = [row[0] for row in cursor.fetchall()]
            return json_response({'members': members}, start_response)

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
