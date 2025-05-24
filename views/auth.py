import json

from urllib.parse import parse_qs
from webob import Request
from models.UserModel import *
from utils import *
from .base import json_response, TemplateView


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
                headers = [
                    ('Content-Type', 'application/json'),
                    ('Set-Cookie', f'user_id={user_id}; Path=/; HttpOnly; SameSite=Lax')
                ]
                data = json.dumps({'redirect': '/'})
                start_response('200 OK', headers)
                return [data.encode('utf-8')]
            else:
                return json_response(
                    {'error': error},
                    start_response,
                    '401 Unauthorized'
                )
        return super().response(environ, start_response)