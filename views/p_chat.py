from collections import namedtuple
import sqlite3
import json
import time
import uuid
import os 
import logging
import hashlib
import re

from webob import Request
from models import *

from utils import *
from .base import View, json_response, forbidden_response


class GetPrivateChatsView(View):
    def response(self, environ, start_response):
        try:
            request = Request(environ)
            user_id = request.cookies.get('user_id')
            if not user_id:
                return forbidden_response(start_response)

            chats = MessageModel.get_private_chats(user_id)
            return json_response({'chats': chats}, start_response)
            
        except Exception as e:
            print(f"Error in GetPrivateChatsView: {str(e)}")
            return json_response(
                {'error': 'Internal server error'}, 
                start_response, 
                '500 Internal Server Error'
            )
        
class CheckPrivateChatsUpdatesView(View):
    def response(self, environ, start_response):
        try:
            request = Request(environ)
            user_id = request.cookies.get('user_id')
            if not user_id:
                return json_response({'updated': False}, start_response)

            with get_db_cursor() as cursor:
                # Получаем timestamp последнего сообщения в приватных чатах
                cursor.execute('''
                    SELECT MAX(timestamp) FROM (
                        SELECT MAX(timestamp) as timestamp 
                        FROM private_messages 
                        WHERE sender_id = ? OR receiver_id = ?
                        GROUP BY 
                            CASE WHEN sender_id = ? THEN receiver_id ELSE sender_id END
                    )
                ''', (user_id, user_id, user_id))
                
                last_update = cursor.fetchone()[0] or 0
                
                # Проверяем новые сообщения
                cursor.execute('''
                    SELECT 1 FROM private_messages
                    WHERE (sender_id = ? OR receiver_id = ?)
                    AND timestamp > ?
                    LIMIT 1
                ''', (user_id, user_id, last_update))
                
                updated = cursor.fetchone() is not None
                return json_response({'updated': updated}, start_response)
                
        except Exception as e:
            logging.error(f"CheckPrivateChatsUpdates error: {str(e)}")
            return json_response({'updated': False}, start_response)
        
def check_group_permissions(cursor, user_id, group_id, required_role=None):
    """Проверяет права пользователя в группе"""
    cursor.execute('''
        SELECT role FROM group_members 
        WHERE group_id = ? AND user_id = ?
    ''', (group_id, user_id))
    result = cursor.fetchone()
    
    if not result:
        return False  # Пользователь не в группе
    
    user_role = result[0]
    
    if required_role == 'owner':
        return user_role == 'owner'
    elif required_role == 'admin':
        return user_role in ('owner', 'admin')
    
    return True
