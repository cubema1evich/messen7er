import os
import sqlite3
import logging
import hashlib
import bcrypt
import re
from werkzeug.utils import secure_filename
from typing import List, Dict, Optional
from collections import defaultdict
from contextlib import contextmanager
from utils import get_db_cursor
from datetime import datetime

class MessageModel:
    @staticmethod
    def get_general_messages(timestamp: int) -> List[Dict]:
        """
        Получает общие сообщения (из общего чата) новее указанного timestamp
        
        Args:
            timestamp: Временная метка для фильтрации сообщений
            
        Returns:
            Список сообщений с вложениями
        """
        with get_db_cursor() as cursor:
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
            
            return MessageModel._process_messages(cursor)

    @staticmethod
    def get_group_messages(group_id: int, timestamp: int) -> List[Dict]:
        """
        Получает сообщения из группового чата новее указанного timestamp
        
        Args:
            group_id: ID группы
            timestamp: Временная метка для фильтрации сообщений
            
        Returns:
            Список сообщений с вложениями
        """
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
            
            return MessageModel._process_messages(cursor)

    @staticmethod
    def get_private_messages(user_id: int, other_user_id: int, timestamp: int) -> List[Dict]:
        """
        Получает приватные сообщения между пользователями новее указанного timestamp
        
        Args:
            user_id: ID текущего пользователя
            other_user_id: ID собеседника
            timestamp: Временная метка для фильтрации сообщений
            
        Returns:
            Список сообщений с вложениями
        """
        with get_db_cursor() as cursor:
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
            
            return MessageModel._process_messages(cursor)

    @staticmethod
    def _process_messages(cursor) -> List[Dict]:
        """
        Обрабатывает результаты SQL-запроса и группирует вложения по сообщениям
        
        Args:
            cursor: Курсор с результатами запроса
            
        Returns:
            Список сообщений с вложениями
        """
        messages = defaultdict(dict)
        
        for row in cursor.fetchall():
            msg_id = row[0]
            if msg_id not in messages:
                messages[msg_id] = {
                    'id': msg_id,
                    'sender': row[1],
                    'message_text': row[2],
                    'timestamp': row[3],
                    'type': row[7] if len(row) > 7 else 'general',
                    'attachments': []
                }
                if len(row) > 8:  # Для групповых сообщений
                    messages[msg_id]['user_id'] = row[8]
            
            if row[4]:  # Если есть вложение
                messages[msg_id]['attachments'].append({
                    'path': row[4],
                    'mime_type': row[5],
                    'filename': row[6]
                })
                
        return list(messages.values())
    
    @staticmethod
    def create_message(
        message_type: str,
        user_id: int,
        message_text: str,
        group_id: Optional[int] = None,
        receiver_id: Optional[int] = None
    ) -> Optional[int]:
        """
        Создает новое сообщение (общее, групповое или приватное)
        
        Args:
            message_type: Тип сообщения ('general', 'group' или 'private')
            user_id: ID отправителя
            message_text: Текст сообщения
            group_id: ID группы (для групповых сообщений)
            receiver_id: ID получателя (для приватных сообщений)
            
        Returns:
            ID созданного сообщения или None в случае ошибки
        """
        try:
            with get_db_cursor() as cursor:
                timestamp = int(datetime.now().timestamp())
                
                if message_type == 'group':
                    cursor.execute('''
                        INSERT INTO group_messages 
                        (group_id, user_id, message_text, timestamp)
                        VALUES (?, ?, ?, ?)
                    ''', (group_id, user_id, message_text, timestamp))
                elif message_type == 'private':
                    cursor.execute('''
                        INSERT INTO private_messages 
                        (sender_id, receiver_id, message_text, timestamp)
                        VALUES (?, ?, ?, ?)
                    ''', (user_id, receiver_id, message_text, timestamp))
                else:  # general
                    # Получаем username отправителя
                    cursor.execute('SELECT username FROM users WHERE id = ?', (user_id,))
                    sender = cursor.fetchone()[0]
                    
                    cursor.execute('''
                        INSERT INTO messages 
                        (user_id, sender, message_text, timestamp)
                        VALUES (?, ?, ?, ?)
                    ''', (user_id, sender, message_text, timestamp))
                
                message_id = cursor.lastrowid
                cursor.connection.commit()
                return message_id
                
        except Exception as e:
            logging.error(f"Error creating message: {str(e)}")
            return None

    @staticmethod
    def add_attachment(
        message_type: str,
        message_id: int,
        file_path: str,
        mime_type: str,
        filename: str
    ) -> bool:
        """
        Добавляет вложение к сообщению
        
        Args:
            message_type: Тип сообщения ('general', 'group' или 'private')
            message_id: ID сообщения
            file_path: Путь к файлу
            mime_type: MIME-тип файла
            filename: Оригинальное имя файла
            
        Returns:
            True если успешно, False в случае ошибки
        """
        try:
            with get_db_cursor() as cursor:
                cursor.execute('''
                    INSERT INTO attachments 
                    (message_type, message_id, file_path, mime_type, filename)
                    VALUES (?, ?, ?, ?, ?)
                ''', (message_type, message_id, file_path, mime_type, filename))
                cursor.connection.commit()
                return True
        except Exception as e:
            logging.error(f"Error adding attachment: {str(e)}")
            return False

    @staticmethod
    def save_uploaded_file(file, upload_folder: str) -> Optional[dict]:
        """
        Сохраняет загруженный файл на сервере
        
        Args:
            file: Файловый объект из request.FILES
            upload_folder: Папка для загрузки
            
        Returns:
            Словарь с информацией о файле или None в случае ошибки
        """
        try:
            if not file.filename or not file.file:
                return None
                
            file_content = file.file.read()
            file_hash = hashlib.md5(file_content).hexdigest()
            file.file.seek(0)
            
            filename = secure_filename(file.filename)
            unique_name = f"{file_hash}_{filename}"
            file_path = os.path.join(upload_folder, unique_name)
            
            if not os.path.exists(file_path):
                with open(file_path, 'wb') as f:
                    f.write(file_content)
            
            return {
                'path': f'/static/uploads/{unique_name}',
                'mime_type': file.type,
                'filename': filename
            }
        except Exception as e:
            logging.error(f"Error saving file: {str(e)}")
            return None

    @staticmethod
    def delete_message(message_type: str, message_id: int, user_id: int) -> bool:
        """
        Удаляет сообщение с проверкой прав (обновлённая версия)
        """
        try:
            with get_db_cursor() as cursor:
                if message_type == 'general':
                    # Для общего чата - только свои сообщения
                    cursor.execute('''
                        SELECT user_id FROM messages WHERE message_id = ?
                    ''', (message_id,))
                    result = cursor.fetchone()
                    if not result or int(result[0]) != user_id:
                        return False
                    
                    cursor.execute('DELETE FROM messages WHERE message_id = ?', (message_id,))
                    
                elif message_type == 'private':
                    # Для личных - только свои сообщения
                    cursor.execute('''
                        SELECT sender_id FROM private_messages WHERE id = ?
                    ''', (message_id,))
                    result = cursor.fetchone()
                    if not result or int(result[0]) != user_id:
                        return False
                        
                    cursor.execute('DELETE FROM private_messages WHERE id = ?', (message_id,))
                    
                elif message_type == 'group':
                    # Для групповых - сложная проверка прав
                    cursor.execute('''
                        SELECT gm.user_id, g.group_id, gm2.role 
                        FROM group_messages gm
                        JOIN groups g ON gm.group_id = g.group_id
                        JOIN group_members gm2 ON g.group_id = gm2.group_id AND gm2.user_id = ?
                        WHERE gm.message_id = ?
                    ''', (user_id, message_id))
                    result = cursor.fetchone()
                    
                    if not result:
                        return False  # Пользователь не в группе или сообщение не существует
                        
                    message_owner_id, group_id, user_role = result
                    
                    # Владельцы и админы могут удалять любые сообщения
                    if user_role in ('owner', 'admin'):
                        pass
                    # Обычные участники - только свои сообщения
                    elif int(message_owner_id) != user_id:
                        return False
                    
                    cursor.execute('DELETE FROM group_messages WHERE message_id = ?', (message_id,))
                
                # Удаляем вложения в любом случае
                cursor.execute('''
                    DELETE FROM attachments 
                    WHERE message_type = ? AND message_id = ?
                ''', (message_type, message_id))
                
                cursor.connection.commit()
                return True
                
        except Exception as e:
            logging.error(f"Error deleting message: {str(e)}")
            return False

    @staticmethod
    def edit_message(
        message_type: str,
        message_id: int,
        user_id: int,
        new_text: str
    ) -> bool:
        """
        Редактирует сообщение с проверкой прав (обновлённая версия)
        """
        try:
            with get_db_cursor() as cursor:
                timestamp = int(datetime.now().timestamp())
                
                if message_type == 'general':
                    # Общий чат - только свои сообщения
                    cursor.execute('''
                        SELECT user_id FROM messages WHERE message_id = ?
                    ''', (message_id,))
                    result = cursor.fetchone()
                    if not result or int(result[0]) != user_id:
                        return False
                        
                    cursor.execute('''
                        UPDATE messages 
                        SET message_text = ?, timestamp = ?
                        WHERE message_id = ?
                    ''', (new_text, timestamp, message_id))
                    
                elif message_type == 'private':
                    # Личные сообщения - только свои
                    cursor.execute('''
                        SELECT sender_id FROM private_messages WHERE id = ?
                    ''', (message_id,))
                    result = cursor.fetchone()
                    if not result or int(result[0]) != user_id:
                        return False
                        
                    cursor.execute('''
                        UPDATE private_messages 
                        SET message_text = ?, timestamp = ?
                        WHERE id = ?
                    ''', (new_text, timestamp, message_id))
                    
                elif message_type == 'group':
                    # Групповые сообщения - сложная проверка прав
                    cursor.execute('''
                        SELECT gm.user_id, g.group_id, gm2.role 
                        FROM group_messages gm
                        JOIN groups g ON gm.group_id = g.group_id
                        JOIN group_members gm2 ON g.group_id = gm2.group_id AND gm2.user_id = ?
                        WHERE gm.message_id = ?
                    ''', (user_id, message_id))
                    result = cursor.fetchone()
                    
                    if not result:
                        return False  # Пользователь не в группе или сообщение не существует
                        
                    message_owner_id, group_id, user_role = result
                    
                    # Владельцы и админы могут редактировать любые сообщения
                    if user_role in ('owner', 'admin'):
                        pass
                    # Обычные участники - только свои сообщения
                    elif int(message_owner_id) != user_id:
                        return False
                        
                    cursor.execute('''
                        UPDATE group_messages 
                        SET message_text = ?, timestamp = ?
                        WHERE message_id = ?
                    ''', (new_text, timestamp, message_id))
                
                cursor.connection.commit()
                return True
                
        except Exception as e:
            logging.error(f"Error editing message: {str(e)}")
            return False
        
    @staticmethod
    def get_private_chats(user_id: int) -> list:
        """Получает список приватных чатов пользователя"""
        with get_db_cursor() as cursor:
            cursor.execute('''
                SELECT DISTINCT 
                    CASE 
                        WHEN pm.sender_id = ? THEN u_receiver.username
                        ELSE u_sender.username
                    END as partner,
                    MAX(pm.timestamp) as last_activity
                FROM private_messages pm
                JOIN users u_sender ON pm.sender_id = u_sender.id
                JOIN users u_receiver ON pm.receiver_id = u_receiver.id
                WHERE pm.sender_id = ? OR pm.receiver_id = ?
                GROUP BY partner
                ORDER BY last_activity DESC
            ''', (user_id, user_id, user_id))
            return [{
                'username': row[0],
                'last_activity': row[1] or 0
            } for row in cursor.fetchall()]
        
    @staticmethod
    def search_messages(
        search_query: str,
        message_type: str = 'general',
        chat_id: Optional[str] = None,
        user_id: Optional[int] = None,
        page: int = 1,
        per_page: int = 20,
        sort: str = 'date'
    ) -> dict:
        """
        Исправленный поиск сообщений
        """
        try:
            with get_db_cursor() as cursor:
                # Определяем параметры для разных типов сообщений
                if message_type == 'group':
                    query = """
                        SELECT 
                            gm.message_id as id,
                            gm.message_text as text,
                            CASE 
                                WHEN gm.user_id = 0 THEN 'System'
                                ELSE u.username
                            END as sender,
                            gm.timestamp,
                            gm.message_text as snippet
                        FROM group_messages gm
                        LEFT JOIN users u ON gm.user_id = u.id
                        WHERE gm.group_id = ? AND gm.message_text LIKE ?
                        ORDER BY gm.timestamp DESC
                        LIMIT ? OFFSET ?
                    """
                    params = [chat_id, f'%{search_query}%', per_page, (page - 1) * per_page]
                    
                    count_query = """
                        SELECT COUNT(*) 
                        FROM group_messages 
                        WHERE group_id = ? AND message_text LIKE ?
                    """
                    count_params = [chat_id, f'%{search_query}%']
                    
                elif message_type == 'private':
                    # Получаем ID собеседника
                    cursor.execute("SELECT id FROM users WHERE username = ?", (chat_id,))
                    partner = cursor.fetchone()
                    if not partner:
                        return {'messages': [], 'total': 0}
                    
                    query = """
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
                        AND pm.message_text LIKE ?
                        ORDER BY pm.timestamp DESC
                        LIMIT ? OFFSET ?
                    """
                    params = [
                        user_id, partner[0],  # user_id -> partner
                        partner[0], user_id,  # partner -> user_id
                        f'%{search_query}%',
                        per_page, (page - 1) * per_page
                    ]
                    
                    count_query = """
                        SELECT COUNT(*) 
                        FROM private_messages 
                        WHERE (
                            (sender_id = ? AND receiver_id = ?) OR 
                            (sender_id = ? AND receiver_id = ?)
                        )
                        AND message_text LIKE ?
                    """
                    count_params = [
                        user_id, partner[0],
                        partner[0], user_id,
                        f'%{search_query}%'
                    ]
                    
                else:  # general
                    query = """
                        SELECT 
                            m.message_id as id,
                            m.message_text as text,
                            m.sender,
                            m.timestamp,
                            m.message_text as snippet
                        FROM messages m
                        WHERE m.message_text LIKE ?
                        ORDER BY m.timestamp DESC
                        LIMIT ? OFFSET ?
                    """
                    params = [f'%{search_query}%', per_page, (page - 1) * per_page]
                    
                    count_query = """
                        SELECT COUNT(*) 
                        FROM messages 
                        WHERE message_text LIKE ?
                    """
                    count_params = [f'%{search_query}%']
                
                # Выполняем поиск
                cursor.execute(query, params)
                messages = []
                for row in cursor.fetchall():
                    messages.append({
                        'id': row[0],
                        'text': row[1],
                        'sender': row[2],
                        'timestamp': row[3],
                        'snippet': row[4]
                    })
                
                # Получаем общее количество
                cursor.execute(count_query, count_params)
                total = cursor.fetchone()[0]
                
                return {
                    'messages': messages,
                    'total': total,
                    'page': page,
                    'per_page': per_page
                }
                
        except Exception as e:
            logging.error(f"Search error: {str(e)}")
            return {
                'messages': [],
                'total': 0,
                'page': page,
                'per_page': per_page
            }
        
class UserModel:
    @staticmethod
    def get_user_id(username: str) -> Optional[int]:
        """Получает ID пользователя по имени"""
        with get_db_cursor() as cursor:
            cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
            result = cursor.fetchone()
            return result[0] if result else None

    @staticmethod
    def create_user(username: str, password: str) -> tuple:
        """
        Создает нового пользователя
        Возвращает (success, error_message)
        """
        if not re.match(r'^[a-zA-Zа-яА-Я0-9_-]{3,20}$', username):
            return False, 'Недопустимое имя пользователя'
        
        if len(password) < 6:
            return False, 'Пароль должен быть не менее 6 символов'

        try:
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
            with get_db_cursor() as cursor:
                cursor.execute(
                    'INSERT INTO users (username, password) VALUES (?, ?)',
                    (username, hashed_password)
                )
                cursor.connection.commit()
            return True, None
        except sqlite3.IntegrityError:
            return False, 'Пользователь с таким именем уже существует'
        except Exception as e:
            logging.error(f"Registration error: {str(e)}")
            return False, 'Ошибка сервера при регистрации'

    @staticmethod
    def authenticate(username: str, password: str) -> tuple:
        """
        Аутентификация пользователя
        Возвращает (user_id, error_message)
        """
        try:
            with get_db_cursor() as cursor:
                cursor.execute(
                    'SELECT id, password FROM users WHERE username=?',
                    (username,)
                )
                result = cursor.fetchone()
                
                if not result:
                    return None, 'Пользователь не найден'
                
                user_id, hashed_password = result
                if not bcrypt.checkpw(password.encode('utf-8'), hashed_password):
                    return None, 'Неверный пароль'
                
                return user_id, None
        except Exception as e:
            logging.error(f"Auth error: {str(e)}")
            return None, 'Ошибка аутентификации'

    @staticmethod
    def get_user_by_id(user_id: int) -> dict:
        """Получает данные пользователя по ID"""
        with get_db_cursor() as cursor:
            cursor.execute(
                'SELECT id, username FROM users WHERE id = ?',
                (user_id,)
            )
            result = cursor.fetchone()
            return {'id': result[0], 'username': result[1]} if result else None

    @staticmethod
    def search_users(query: str, exclude_user_id: int = None) -> list:
        """Поиск пользователей по имени"""
        with get_db_cursor() as cursor:
            params = [f'%{query}%']
            if exclude_user_id:
                cursor.execute(
                    'SELECT username FROM users WHERE username LIKE ? AND id != ? LIMIT 10',
                    (f'%{query}%', exclude_user_id)
                )
            else:
                cursor.execute(
                    'SELECT username FROM users WHERE username LIKE ? LIMIT 10',
                    (f'%{query}%',)
                )
            return [row[0] for row in cursor.fetchall()]
        
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
                
                # Владельца может удалить только другой владелец
                if target_role and target_role[0] == 'owner' and remover_role[0] != 'owner':
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