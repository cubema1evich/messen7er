import sqlite3
import logging
from werkzeug.utils import secure_filename
from collections import defaultdict
from contextlib import contextmanager
from utils import get_db_cursor
from datetime import datetime

class GroupModel:
    @staticmethod
    def create_group(name: str, creator_id: int) -> dict:
        """Создает новую группу"""
        try:
            timestamp = int(datetime.now().timestamp())
            with get_db_cursor() as cursor:
                cursor.execute('''
                    INSERT INTO groups (name, creator_id, created_at)
                    VALUES (?, ?, ?)
                ''', (name, creator_id, timestamp))
                
                group_id = cursor.lastrowid
                
                # Добавляем создателя как владельца
                cursor.execute('''
                    INSERT INTO group_members (group_id, user_id, role, joined_at)
                    VALUES (?, ?, ?, ?)
                ''', (group_id, creator_id, 'owner', timestamp))
                
                cursor.connection.commit()
                return {'status': 'success', 'group_id': group_id}
        except sqlite3.IntegrityError:
            return {'error': 'Группа с таким именем уже существует'}
        except Exception as e:
            logging.error(f"Group creation error: {str(e)}")
            return {'error': 'Ошибка создания группы'}

    @staticmethod
    def get_user_groups(user_id: int) -> list:
        """Получает группы пользователя"""
        with get_db_cursor() as cursor:
            cursor.execute('''
                SELECT g.group_id, g.name, gm.role
                FROM groups g
                JOIN group_members gm ON g.group_id = gm.group_id
                WHERE gm.user_id = ?
                ORDER BY g.name
            ''', (user_id,))
            return [{
                'id': row[0],
                'name': row[1],
                'role': row[2]
            } for row in cursor.fetchall()]

    @staticmethod
    def check_group_access(group_id: int, user_id: int) -> bool:
        """Проверяет доступ пользователя к группе"""
        with get_db_cursor() as cursor:
            cursor.execute('''
                SELECT 1 FROM group_members 
                WHERE group_id = ? AND user_id = ?
            ''', (group_id, user_id))
            return cursor.fetchone() is not None
        
    @staticmethod
    def add_member(group_id: int, user_id: int, role: str = 'member') -> dict:
        """
        Добавляет участника в группу
        Возвращает {status: 'success'} или {error: 'message'}
        """
        try:
            timestamp = int(datetime.now().timestamp())
            with get_db_cursor() as cursor:
                # Проверяем существование группы
                cursor.execute('SELECT 1 FROM groups WHERE group_id = ?', (group_id,))
                if not cursor.fetchone():
                    return {'error': 'Group not found'}
                
                # Проверяем, есть ли уже пользователь в группе
                cursor.execute('''
                    SELECT 1 FROM group_members 
                    WHERE group_id = ? AND user_id = ?
                    ''', (group_id, user_id))
                if cursor.fetchone():
                    return {'error': 'Пользователь уже состоит в группе'}
                
                # Добавляем участника
                cursor.execute('''
                    INSERT OR REPLACE INTO group_members 
                    (group_id, user_id, role, joined_at)
                    VALUES (?, ?, ?, ?)
                ''', (group_id, user_id, role, timestamp))
                
                cursor.connection.commit()
                return {'status': 'success'}
                
        except sqlite3.IntegrityError:
            return {'error': 'User already in group'}
        except Exception as e:
            logging.error(f"Add member error: {str(e)}")
            return {'error': 'Internal Server Error'}

    @staticmethod
    def remove_member(group_id: int, user_id: int, remover_id: int) -> dict:
        """
        Удаляет участника из группы с проверкой прав
        Возвращает {status: 'success'} или {error: 'message'}
        """
        try:
            with get_db_cursor() as cursor:
                # Проверяем права удаляющего
                cursor.execute('''
                    SELECT role FROM group_members 
                    WHERE group_id = ? AND user_id = ?
                ''', (group_id, remover_id))
                remover_role = cursor.fetchone()
                
                if not remover_role or remover_role[0] not in ('owner', 'admin'):
                    return {'error': 'Недостаточно прав'}
                
                # Проверяем роль удаляемого
                cursor.execute('''
                    SELECT role FROM group_members 
                    WHERE group_id = ? AND user_id = ?
                ''', (group_id, user_id))
                target_role = cursor.fetchone()

                # Проверяем, существует ли участник в группе
                cursor.execute('''
                    SELECT role FROM group_members 
                    WHERE group_id = ? AND user_id = ?
                    ''', (group_id, user_id))
                target_role = cursor.fetchone()
                
                if not target_role:
                    return {'error': 'User not in group'}
                
                # Владельца может удалить только другой владелец
                if target_role and target_role[0] == 'owner':
                    return {'error': 'Нельзя удалить владельца'}
                
                # Удаляем участника
                cursor.execute('''
                    DELETE FROM group_members 
                    WHERE group_id = ? AND user_id = ?
                ''', (group_id, user_id))
                
                cursor.connection.commit()
                return {'status': 'success'}
                
        except Exception as e:
            logging.error(f"Remove member error: {str(e)}")
            return {'error': 'Internal Server Error'}

    @staticmethod
    def change_role(group_id: int, user_id: int, new_role: str, changer_id: int) -> dict:
        """
        Изменяет роль участника с проверкой прав
        Возвращает {status: 'success'} или {error: 'message'}
        """
        try:
            with get_db_cursor() as cursor:
                # Проверяем права изменяющего
                cursor.execute('''
                    SELECT role FROM group_members 
                    WHERE group_id = ? AND user_id = ?
                ''', (group_id, changer_id))
                changer_role = cursor.fetchone()
                
                if not changer_role or changer_role[0] not in ('owner', 'admin'):
                    return {'error': 'Недостаточно прав'}
                
                # Проверяем текущую роль участника
                cursor.execute('''
                    SELECT role FROM group_members 
                    WHERE group_id = ? AND user_id = ?
                ''', (group_id, user_id))
                current_role = cursor.fetchone()
                
                if not current_role:
                    return {'error': 'User not in group'}
                
                # Владельца может изменить только другой владелец
                if current_role[0] == 'owner' and changer_role[0] != 'owner':
                    return {'error': 'Нельзя изменить владельца'}
                
                # Изменяем роль
                cursor.execute('''
                    UPDATE group_members 
                    SET role = ?
                    WHERE group_id = ? AND user_id = ?
                ''', (new_role, group_id, user_id))
                
                cursor.connection.commit()
                return {'status': 'success'}
                
        except Exception as e:
            logging.error(f"Change role error: {str(e)}")
            return {'error': 'Internal Server Error'}

    @staticmethod
    def get_group_members(group_id: int) -> list:
        """Получает список участников группы"""
        with get_db_cursor() as cursor:
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
            return [{
                'username': row[0],
                'role': row[1],
                'joined_at': row[2]
            } for row in cursor.fetchall()]
        
    @staticmethod
    def rename_group(group_id: int, new_name: str, user_id: int) -> dict:
        """
        Переименовывает группу с проверкой прав
        Возвращает {status: 'success'} или {error: 'message'}
        """
        try:
            with get_db_cursor() as cursor:
                # Проверяем права пользователя
                cursor.execute('''
                    SELECT role FROM group_members 
                    WHERE group_id = ? AND user_id = ?
                ''', (group_id, user_id))
                result = cursor.fetchone()
                
                if not result or result[0] not in ('owner', 'admin'):
                    return {'error': 'Недостаточно прав для изменения названия'}
                
                # Проверяем уникальность имени
                cursor.execute('''
                    SELECT 1 FROM groups 
                    WHERE name = ? AND group_id != ?
                ''', (new_name, group_id))
                if cursor.fetchone():
                    return {'error': 'Группа с таким именем уже существует'}
                
                # Обновляем название
                cursor.execute('''
                    UPDATE groups 
                    SET name = ? 
                    WHERE group_id = ?
                ''', (new_name, group_id))
                
                cursor.connection.commit()
                return {'status': 'success'}
                
        except Exception as e:
            logging.error(f"Rename group error: {str(e)}")
            return {'error': 'Ошибка сервера'}

    @staticmethod
    def leave_group(group_id: int, user_id: int) -> dict:
        """
        Покидает группу (для обычных участников) или удаляет группу (для владельца)
        Возвращает {status: 'success', is_group_deleted: bool} или {error: 'message'}
        """
        try:
            with get_db_cursor() as cursor:
                cursor.execute('BEGIN TRANSACTION')
                
                # Проверяем роль пользователя
                cursor.execute('''
                    SELECT role, username FROM group_members
                    JOIN users ON group_members.user_id = users.id
                    WHERE group_id = ? AND user_id = ?
                ''', (group_id, user_id))
                result = cursor.fetchone()
                
                if not result:
                    return {'error': 'User not in group'}
                
                role, username = result
                
                if role == 'owner':
                    # Удаляем группу полностью
                    cursor.execute('DELETE FROM group_members WHERE group_id = ?', (group_id,))
                    cursor.execute('DELETE FROM groups WHERE group_id = ?', (group_id,))
                    is_group_deleted = True
                    action_message = f'Группа удалена владельцем {username}'
                else:
                    # Просто удаляем участника
                    cursor.execute('''
                        DELETE FROM group_members 
                        WHERE group_id = ? AND user_id = ?
                    ''', (group_id, user_id))
                    is_group_deleted = False
                    action_message = f'Пользователь {username} покинул группу'
                
                # Добавляем системное сообщение
                cursor.execute('''
                    INSERT INTO group_messages 
                    (group_id, user_id, message_text, timestamp)
                    VALUES (?, 0, ?, ?)
                ''', (group_id, action_message, int(datetime.now().timestamp())          ))
                
                cursor.connection.commit()
                return {'status': 'success', 'is_group_deleted': is_group_deleted}
                
        except Exception as e:
            cursor.connection.rollback()
            logging.error(f"Leave group error: {str(e)}")
            return {'error': 'Internal Server Error'}