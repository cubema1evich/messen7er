from collections import namedtuple
import sqlite3
import json
import time
import uuid
import os 
import logging
import hashlib
import re

from urllib.parse import parse_qs
from webob import Request

from utils import *
from .base import View, json_response, forbidden_response

class SearchUsersView(View):
    def response(self, environ, start_response):
        try:
            request = Request(environ)
            search_term = request.GET.get('q', '')
            
            with get_db_cursor() as cursor:
                cursor.execute('''
                    SELECT username FROM users 
                    WHERE username LIKE ? 
                    AND username != ?
                    LIMIT 10
                ''', (f'%{search_term}%', request.cookies.get('user_id')))
                
                users = [row[0] for row in cursor.fetchall()]
                return json_response({'users': users}, start_response)
                
        except Exception as e:
            return json_response({'error': str(e)}, start_response, '500 Internal Server Error')
        
class SearchMessagesView(View):
    def response(self, environ, start_response):
        try:
            request = Request(environ)
            query_params = parse_qs(environ.get('QUERY_STRING', ''))
            
            # Получаем параметры
            search_query = query_params.get('q', [''])[0].strip()
            chat_type = query_params.get('type', ['general'])[0]
            chat_id = query_params.get('chat_id', [None])[0]
            page = int(query_params.get('page', ['1'])[0])
            per_page = int(query_params.get('per_page', ['20'])[0])
            sort = query_params.get('sort', ['date'])[0]
            
            if not search_query:
                return json_response({'error': 'Search query is required'}, start_response, '400 Bad Request')

            offset = (page - 1) * per_page
            user_id = request.cookies.get('user_id')
            
            if not user_id:
                return forbidden_response(start_response)

            with get_db_cursor() as cursor:
                if chat_type == 'group':
                    # Поиск в группе
                    cursor.execute('''
                        SELECT 
                            gm.message_id as id,
                            gm.message_text as text,
                            u.username as sender,
                            gm.timestamp,
                            gm.message_text as snippet
                        FROM group_messages gm
                        JOIN users u ON gm.user_id = u.id
                        WHERE gm.group_id = ? AND gm.message_text LIKE ? COLLATE NOCASE
                        ORDER BY gm.timestamp DESC
                        LIMIT ? OFFSET ?
                    ''', [chat_id, f'%{search_query}%', per_page, offset])
                    
                elif chat_type == 'private':
                    # Поиск в личных сообщениях
                    # Сначала получаем ID собеседника по username
                    cursor.execute("SELECT id FROM users WHERE username = ?", (chat_id,))
                    partner = cursor.fetchone()
                    if not partner:
                        return json_response({'error': 'User not found'}, start_response, '404 Not Found')
                    
                    partner_id = partner[0]
                    
                    cursor.execute('''
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
                        AND pm.message_text LIKE ? COLLATE NOCASE
                        ORDER BY pm.timestamp DESC
                        LIMIT ? OFFSET ?
                    ''', [user_id, partner_id, partner_id, user_id, f'%{search_query}%', per_page, offset])
                    
                else:
                    # Поиск в общем чате
                    cursor.execute('''
                        SELECT 
                            message_id as id,
                            message_text as text,
                            sender,
                            timestamp,
                            message_text as snippet
                        FROM messages
                        WHERE message_text LIKE ? COLLATE NOCASE 
                        ORDER BY timestamp DESC
                        LIMIT ? OFFSET ?
                    ''', [f'%{search_query}%', per_page, offset])

                results = []
                for row in cursor.fetchall():
                    results.append({
                        'id': row[0],
                        'text': row[1],
                        'sender': row[2],
                        'timestamp': row[3],
                        'snippet': row[4]
                    })

                # Получаем общее количество
                if chat_type == 'group':
                    cursor.execute('''
                        SELECT COUNT(*) 
                        FROM group_messages 
                        WHERE group_id = ? AND message_text LIKE ? COLLATE NOCASE
                    ''', [chat_id, f'%{search_query}%'])
                elif chat_type == 'private':
                    cursor.execute('''
                        SELECT COUNT(*) 
                        FROM private_messages 
                        WHERE (
                            (sender_id = ? AND receiver_id = ?) OR 
                            (sender_id = ? AND receiver_id = ?)
                        )
                        AND message_text LIKE ? COLLATE NOCASE
                    ''', [user_id, partner_id, partner_id, user_id, f'%{search_query}%'])
                else:
                    cursor.execute('''
                        SELECT COUNT(*) 
                        FROM messages 
                        WHERE message_text LIKE ? COLLATE NOCASE
                    ''', [f'%{search_query}%'])

                total_count = cursor.fetchone()[0]

                return json_response({
                    'messages': results,
                    'total': total_count,
                    'page': page,
                    'per_page': per_page,
                    'total_pages': (total_count + per_page - 1) // per_page
                }, start_response)

        except Exception as e:
            logging.error(f"Search error: {str(e)}", exc_info=True)
            return json_response(
                {'error': str(e)},  # Возвращаем текст ошибки для отладки
                start_response,
                '500 Internal Server Error'
            )

