from utils import *
from .base import TemplateView

class NotFoundView(TemplateView):
    template = 'templates/404.html'
    
    def response(self, environ, start_response):
        headers = [('Content-type', 'text/html')]
        try:
            with open(self.template, 'r', encoding='utf-8') as file:
                data = file.read()
            start_response('404 Not Found', headers)
            return [data.encode('utf-8')]
        except FileNotFoundError:
            start_response('404 Not Found', headers)
            return [b'<h1>404 Not Found</h1><p>Page not found</p>']
        

class ForbiddenView(TemplateView):
    template = 'templates/403.html'
    
    def response(self, environ, start_response):
        headers = [('Content-type', 'text/html')]
        try:
            with open(self.template, 'r', encoding='utf-8') as file:
                data = file.read()
            start_response('403 Forbidden', headers)
            return [data.encode('utf-8')]
        except FileNotFoundError:
            start_response('403 Forbidden', headers)
            return [b'<h1>403 Forbidden</h1><p>Access denied</p>']

class InternalServerErrorView(TemplateView):
    template = 'templates/500.html'
    
    def response(self, environ, start_response):
        headers = [('Content-type', 'text/html')]
        try:
            with open(self.template, 'r', encoding='utf-8') as file:
                data = file.read()
            start_response('500 Internal Server Error', headers)
            return [data.encode('utf-8')]
        except FileNotFoundError:
            start_response('500 Internal Server Error', headers)
            return [b'<h1>500 Internal Server Error</h1><p>Server error occurred</p>']
