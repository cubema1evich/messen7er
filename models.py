import os
import sqlite3
import logging
import hashlib
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