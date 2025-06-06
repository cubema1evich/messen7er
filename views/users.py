import json
import logging

from webob import Request
from models.GroupModel import *
from models.MessageModel import *
from models.UserModel import *
from utils import *
from .base import View, json_response


class GetUserIdView(View):
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

            # Используем UserModel вместо прямого запроса
            user = UserModel.get_user_by_id(user_id)
            if not user:
                return json_response({'error': 'User not found'}, start_response, '404 Not Found')
                
            response_data = {
                'user_id': user_id,
                'username': user['username']
            }
            
            headers = [
                ('Content-Type', 'application/json'),
                ('Access-Control-Allow-Origin', 'http://localhost:8000'),
                ('Access-Control-Allow-Credentials', 'true'),
                ('Set-Cookie', f'user_id={user_id}; Path=/; HttpOnly; SameSite=Lax')
            ]
            
            start_response('200 OK', headers)
            return [json.dumps(response_data).encode('utf-8')]
            
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

            # Получаем ID целевого пользователя
            target_user_id = UserModel.get_user_id(username)
            if not target_user_id:
                return json_response(
                    {'error': 'User not found'}, 
                    start_response, 
                    '404 Not Found'
                )

            result = GroupModel.change_role(
                group_id=group_id,
                user_id=target_user_id,
                new_role=new_role,
                changer_id=user_id
            )
            
            if 'error' in result:
                return json_response(
                    {'error': result['error']}, 
                    start_response, 
                    '403 Forbidden' if 'Недостаточно прав' in result['error'] else '500 Internal Server Error'
                )
            
            # Добавляем системное сообщение
            role_names = {
                'owner': 'владельцем',
                'admin': 'администратором',
                'member': 'участником'
            }
            MessageModel.create_message(
                message_type='group',
                user_id=0,  # System
                message_text=f'Пользователь {username} назначен {role_names[new_role]}',
                group_id=group_id
            )
            
            return json_response({
                'status': 'success',
                'new_role': new_role,
                'role_name': role_names[new_role]
            }, start_response)
            
        except Exception as e:
            logging.error(f"ChangeMemberRole error: {str(e)}")
            return json_response(
                {'error': 'Internal Server Error'}, 
                start_response, 
                '500 Internal Server Error'
            )