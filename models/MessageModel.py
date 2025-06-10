import base64
import os
import logging
import hashlib
from werkzeug.utils import secure_filename
from typing import List, Dict, Optional
from collections import defaultdict
from contextlib import contextmanager
from utils import get_db_cursor
from datetime import datetime
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding

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
    def get_private_messages(
        user_id: int,
        other_user_id: int,
        timestamp: int,
        session_key: Optional[bytes] = None
    ) -> List[Dict]:
        """
        Получает приватные сообщения между пользователями новее указанного timestamp
        
        Args:
            user_id: ID текущего пользователя
            other_user_id: ID или username собеседника
            timestamp: Временная метка для фильтрации сообщений
            
        Returns:
            Список сообщений с правильными полями sender и message_text
        """
        with get_db_cursor() as cursor:
            if isinstance(other_user_id, str):
                cursor.execute("SELECT id FROM users WHERE username = ?", (other_user_id,))
                other_user = cursor.fetchone()
                if not other_user:
                    return []
                other_user_id = other_user[0]

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
            
            messages = defaultdict(dict)
            
            for row in cursor.fetchall():
                msg_id = row[0]
                if msg_id not in messages:
                    try:
                        # Дешифруем сообщение, если есть ключ
                        message_text = row[1]
                        if session_key:
                            message_text = MessageEncryptor.decrypt_message(row[1], session_key)
                            
                        messages[msg_id] = {
                            'id': msg_id,
                            'sender': row[2],
                            'message_text': message_text,
                            'timestamp': row[3],
                            'attachments': []
                        }
                    except Exception as e:
                        logging.error(f"Error decrypting message {msg_id}: {str(e)}")
                        messages[msg_id] = {
                            'id': msg_id,
                            'sender': row[2],
                            'message_text': "[Не удалось расшифровать сообщение]",
                            'timestamp': row[3],
                            'attachments': []
                        }
                
                if row[4]:
                    messages[msg_id]['attachments'].append({
                        'path': row[4],
                        'mime_type': row[5],
                        'filename': row[6]
                    })
                    
            return list(messages.values())

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
        receiver_id: Optional[int] = None,
        session_key: Optional[bytes] = None
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
            # Шифруем сообщение, если предоставлен ключ
            encrypted_text = message_text
            if session_key:
                encrypted_text = MessageEncryptor.encrypt_message(message_text, session_key)
            
            timestamp = int(datetime.now().timestamp())
            
            with get_db_cursor() as cursor:
                if message_type == 'group':
                    cursor.execute('''
                        INSERT INTO group_messages 
                        (group_id, user_id, message_text, timestamp)
                        VALUES (?, ?, ?, ?)
                    ''', (group_id, user_id, encrypted_text, timestamp))
                elif message_type == 'private':
                    cursor.execute('''
                        INSERT INTO private_messages 
                        (sender_id, receiver_id, message_text, timestamp)
                        VALUES (?, ?, ?, ?)
                    ''', (user_id, receiver_id, encrypted_text, timestamp))
                else:  # general
                    cursor.execute('SELECT username FROM users WHERE id = ?', (user_id,))
                    sender = cursor.fetchone()[0]
                    
                    cursor.execute('''
                        INSERT INTO messages 
                        (user_id, sender, message_text, timestamp)
                        VALUES (?, ?, ?, ?)
                    ''', (user_id, sender, encrypted_text, timestamp))
                
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
        
class MessageEncryptor:
    @staticmethod
    def encrypt_message(message: str, session_key: bytes) -> str:
        """Шифрует сообщение с использованием AES-256-CBC"""
        try:
            # Генерируем IV (Initialization Vector)
            iv = os.urandom(16)
            
            # Создаем шифр
            cipher = Cipher(
                algorithms.AES(session_key),
                modes.CBC(iv),
                backend=default_backend()
            )
            
            # Применяем padding к сообщению
            padder = padding.PKCS7(128).padder()
            padded_data = padder.update(message.encode('utf-8')) + padder.finalize()
            
            # Шифруем
            encryptor = cipher.encryptor()
            encrypted_message = encryptor.update(padded_data) + encryptor.finalize()
            
            # Объединяем IV и зашифрованное сообщение
            combined = iv + encrypted_message
            
            # Кодируем в base64 для хранения
            return base64.b64encode(combined).decode('utf-8')
            
        except Exception as e:
            logging.error(f"Encryption error: {str(e)}")
            raise

    @staticmethod
    def decrypt_message(encrypted_message: str, session_key: bytes) -> str:
        """Дешифрует сообщение с использованием AES-256-CBC"""
        try:
            # Декодируем из base64
            combined = base64.b64decode(encrypted_message)
            
            # Извлекаем IV (первые 16 байт)
            iv = combined[:16]
            encrypted_data = combined[16:]
            
            # Создаем шифр
            cipher = Cipher(
                algorithms.AES(session_key),
                modes.CBC(iv),
                backend=default_backend()
            )
            
            # Дешифруем
            decryptor = cipher.decryptor()
            padded_data = decryptor.update(encrypted_data) + decryptor.finalize()
            
            # Удаляем padding
            unpadder = padding.PKCS7(128).unpadder()
            data = unpadder.update(padded_data) + unpadder.finalize()
            
            return data.decode('utf-8')
            
        except Exception as e:
            logging.error(f"Decryption error: {str(e)}")
            raise