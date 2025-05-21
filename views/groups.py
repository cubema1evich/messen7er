import sqlite3
import json
import time
import logging

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
                
                # Проверяем, что пользователь не пытается добавить самого себя
                if int(target_user_id) == int(user_id):
                    return json_response(
                        {'error': 'Нельзя добавить самого себя в группу'}, 
                        start_response, 
                        '400 Bad Request'
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
                ''', (group_id, f'Пользователь {username} исключен из группы 🚪', int(time.time())))
                
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
