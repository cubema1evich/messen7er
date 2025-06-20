import os
import base64
import json

from urllib.parse import parse_qs
from webob import Request
from models.UserModel import *
from models.session import *
from utils import *
from .base import json_response, TemplateView, View


class RegisterView(TemplateView):
    template = 'templates/register.html'

    def response(self, environ, start_response):
        request = Request(environ)
        if request.method == 'POST':
            post_data = request.POST
            username = post_data.get('username', '').strip()
            password = post_data.get('password', '')

            success, error = UserModel.create_user(username, password)
            
            if success:
                return json_response(
                    {'message': 'Регистрация прошла успешно!'},
                    start_response
                )
            else:
                return json_response(
                    {'error': error},
                    start_response,
                    '400 Bad Request' if 'уже существует' in error else '500 Internal Server Error'
                )

        return super().response(environ, start_response)


class LoginView(TemplateView):
    template = 'templates/login.html'

    def response(self, environ, start_response):
        if environ['REQUEST_METHOD'] == 'POST':
            request = Request(environ)
            post_data = parse_qs(request.body.decode('utf-8'))
            username = post_data.get('username', [''])[0].strip()
            password = post_data.get('password', [''])[0]

            user_id, error = UserModel.authenticate(username, password)
            if user_id:
                
                (session_id, key) = create_session()
                headers = [
                    ('Content-Type', 'application/json'),
                    ('Set-Cookie', f'user_id={user_id}; Path=/; HttpOnly; SameSite=Lax'),
                ]
                
                session_key = base64.b64encode(key).decode('utf8')
                data = json.dumps({
                    'session_id': session_id,
                    'session_key': session_key,
                    'redirect': '/',
                })
                
                start_response('200 OK', headers)
                return [data.encode('utf-8')]
            else:
                return json_response(
                    {'error': error},
                    start_response,
                    '401 Unauthorized'
                )
        return super().response(environ, start_response)
    
class LogoutView(View):
    def response(self, environ, start_response):
        request = Request(environ)
        session_id = request.cookies.get('session_id')
        if not session_id:
            # ищем в query string
            session_id = request.GET.get('session_id')
        
        if session_id:
            delete_session(session_id)
        
        # Очищаем куки
        headers = [
            ('Set-Cookie', 'user_id=; Path=/; Expires=Thu, 01 Jan 1970 00:00:00 GMT; HttpOnly; SameSite=Lax'),
            ('Set-Cookie', 'session_id=; Path=/; Expires=Thu, 01 Jan 1970 00:00:00 GMT; HttpOnly; SameSite=Lax'),
            ('Location', '/login')
        ]
        start_response('303 See Other', headers)
        return []
    
class DeleteSessionView(View):
    def response(self, environ, start_response):
        session_id = environ['url_params'][0]
        if delete_session(session_id):
            return json_response({'status': 'success'}, start_response)
        else:
            return json_response({'error': 'Session not found'}, start_response, '404 Not Found')