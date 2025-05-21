from collections import namedtuple
import logging

from urllib.parse import parse_qs
from webob import Request
from models import *
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
            
            # Получаем параметры с проверкой
            search_query = query_params.get('q', [''])[0].strip()
            if not search_query:
                return json_response(
                    {'error': 'Search query is required'}, 
                    start_response, 
                    '400 Bad Request'
                )
            
            message_type = query_params.get('type', ['general'])[0]
            chat_id = query_params.get('chat_id', [None])[0]
            
            try:
                page = max(1, int(query_params.get('page', ['1'])[0]))
                per_page = min(50, max(1, int(query_params.get('per_page', ['20'])[0])))
            except ValueError:
                return json_response(
                    {'error': 'Invalid pagination parameters'}, 
                    start_response, 
                    '400 Bad Request'
                )
            
            sort = query_params.get('sort', ['date'])[0]
            if sort not in ['date', 'relevance']:
                sort = 'date'
            
            user_id = request.cookies.get('user_id')
            if not user_id:
                return forbidden_response(start_response)
            
            # Для приватных чатов проверяем существование собеседника
            if message_type == 'private' and chat_id:
                partner_id = UserModel.get_user_id(chat_id)
                if not partner_id:
                    return json_response(
                        {'error': 'User not found'}, 
                        start_response, 
                        '404 Not Found'
                    )
            
            # Для групповых чатов проверяем доступ
            if message_type == 'group' and chat_id:
                if not GroupModel.check_group_access(chat_id, user_id):
                    return json_response(
                        {'error': 'No access to this group'}, 
                        start_response, 
                        '403 Forbidden'
                    )
            
            # Выполняем поиск
            result = MessageModel.search_messages(
                search_query=search_query,
                message_type=message_type,
                chat_id=chat_id,
                user_id=user_id,
                page=page,
                per_page=per_page,
                sort=sort
            )
            
            # Формируем контекст для UI
            context = ""
            if message_type == 'private' and chat_id:
                context = f"в переписке с {chat_id}"
            elif message_type == 'group' and chat_id:
                with get_db_cursor() as cursor:
                    cursor.execute("SELECT name FROM groups WHERE group_id = ?", (chat_id,))
                    group_name = cursor.fetchone()
                    context = f"в группе '{group_name[0]}'" if group_name else "в группе"
            
            return json_response({
                'messages': result['messages'],
                'total': result['total'],
                'page': result['page'],
                'per_page': result['per_page'],
                'total_pages': (result['total'] + per_page - 1) // per_page,
                'context': context
            }, start_response)
            
        except Exception as e:
            logging.error(f"Search error: {str(e)}", exc_info=True)
            return json_response(
                {'error': 'Internal server error'}, 
                start_response, 
                '500 Internal Server Error'
            )
