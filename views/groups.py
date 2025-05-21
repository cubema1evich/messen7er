import sqlite3
import json
import time
import logging

from models import *
from webob import Request
from .base import json_response, forbidden_response, View
from utils import *


class GetGroupMembersView(View):
    def response(self, environ, start_response):
        request = Request(environ)
        user_id = request.cookies.get('user_id')
        group_id = request.GET.get('group_id')
        
        if not user_id:
            return forbidden_response(start_response)

        # Проверяем доступ к группе
        if not GroupModel.check_group_access(group_id, user_id):
            return json_response(
                {'error': 'Not a group member'}, 
                start_response, 
                '403 Forbidden'
            )
        
        # Получаем участников через модель
        members = GroupModel.get_group_members(group_id)
        return json_response({'members': members}, start_response)

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

            if not group_id:
                return json_response(
                    {'error': 'Group ID is required'}, 
                    start_response, 
                    '400 Bad Request'
                )

            result = GroupModel.leave_group(
                group_id=group_id,
                user_id=user_id
            )
            
            if 'error' in result:
                return json_response(result, start_response, '400 Bad Request')
            
            return json_response({
                'status': 'success',
                'is_group_deleted': result['is_group_deleted']
            }, start_response)
            
        except Exception as e:
            logging.error(f"LeaveGroup error: {str(e)}")
            return json_response(
                {'error': 'Internal Server Error'}, 
                start_response, 
                '500 Internal Server Error'
            )

class CreateGroupView(View):
    def response(self, environ, start_response):
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

            result = GroupModel.create_group(group_name, user_id)
            
            if 'error' in result:
                status_code = '400 Bad Request' if 'уже существует' in result['error'] else '500 Internal Server Error'
                return json_response(result, start_response, status_code)
            
            return json_response(result, start_response)
            
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

            if not all([group_id, username]):
                return json_response(
                    {'error': 'Missing parameters'}, 
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
                
            # Проверяем что пользователь не пытается добавить самого себя
            if int(target_user_id) == int(user_id):
                return json_response(
                    {'error': 'Cannot add yourself'}, 
                    start_response, 
                    '400 Bad Request'
                )

            # Добавляем через модель
            result = GroupModel.add_member(
                group_id=group_id,
                user_id=target_user_id,
                role=role
            )
            
            if 'error' in result:
                return json_response(
                    {'error': result['error']}, 
                    start_response, 
                    '400 Bad Request' if result['error'] == 'User already in group' else '500 Internal Server Error'
                )
            
            # Добавляем системное сообщение
            MessageModel.create_message(
                message_type='group',
                user_id=0,  # System
                message_text=f'Пользователь {username} добавлен в группу!',
                group_id=group_id
            )
            
            return json_response({
                'status': 'success',
                'message': f'User {username} added successfully'
            }, start_response)
            
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

        groups = GroupModel.get_user_groups(user_id)
        return json_response(groups, start_response)

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

            result = GroupModel.rename_group(
                group_id=group_id,
                new_name=new_name,
                user_id=user_id
            )
            
            if 'error' in result:
                status_code = '400 Bad Request' if 'уже существует' in result['error'] else '403 Forbidden'
                return json_response(result, start_response, status_code)
            
            # Добавляем системное сообщение
            MessageModel.create_message(
                message_type='group',
                user_id=0,  # System
                message_text=f'Название группы изменено на "{new_name}"',
                group_id=group_id
            )
            
            return json_response({
                'status': 'success',
                'new_name': new_name
            }, start_response)
            
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

            # Получаем ID целевого пользователя
            target_user_id = UserModel.get_user_id(username)
            if not target_user_id:
                return json_response(
                    {'error': 'User not found'}, 
                    start_response, 
                    '404 Not Found'
                )

            result = GroupModel.remove_member(
                group_id=group_id,
                user_id=target_user_id,
                remover_id=user_id
            )
            
            if 'error' in result:
                return json_response(
                    {'error': result['error']}, 
                    start_response, 
                    '403 Forbidden' if 'Недостаточно прав' in result['error'] else '500 Internal Server Error'
                )
            
            # Добавляем системное сообщение
            action = 'исключен из группы' if target_user_id != user_id else 'покинул группу'
            MessageModel.create_message(
                message_type='group',
                user_id=0,  # System
                message_text=f'Пользователь {username} {action}',
                group_id=group_id
            )
            
            return json_response({
                'status': 'success',
                'message': f'User {username} removed successfully'
            }, start_response)
            
        except Exception as e:
            logging.error(f"RemoveFromGroup error: {str(e)}")
            return json_response(
                {'error': 'Internal Server Error'}, 
                start_response, 
                '500 Internal Server Error'
            )
