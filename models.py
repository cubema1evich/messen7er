import sqlite3
from typing import List, Dict, Optional
from collections import defaultdict
from contextlib import contextmanager
from utils import get_db_cursor

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