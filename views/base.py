from collections import namedtuple
import os 
import logging
import json

from mimes import get_mime
from webob import Request

from utils import *
 

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='app.log'
)

Response = namedtuple("Response", "status headers data")

def json_response(data, start_response, status='200 OK'):
    headers = [
        ('Content-Type', 'application/json'),
        ('Access-Control-Allow-Origin', 'http://localhost:8000'),
        ('Access-Control-Allow-Credentials', 'true')
    ]
    start_response(status, headers)
    return [json.dumps(data).encode('utf-8')]

def forbidden_response(start_response):
    start_response('403 Forbidden', [('Content-Type', 'text/plain')])
    return [b'Access denied']

class View:
    path = ''

    def __init__(self, url) -> None:
        self.url = url

    def response(self, environ, start_response):
        file_path = self.path + self.url
        file_path = file_path.lstrip('/')
        
        if not os.path.exists(file_path):
            start_response('404 Not Found', [('Content-Type', 'text/plain')])
            return [b'File not found']
        
        try:
            mime_type = get_mime(file_path)
            
            if mime_type.startswith('text/') or mime_type in ['application/javascript', 'application/json']:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = f.read()
                start_response('200 OK', [('Content-Type', mime_type)])
                return [data.encode('utf-8')]
            else:
                with open(file_path, 'rb') as f:
                    data = f.read()
                start_response('200 OK', [('Content-Type', mime_type)])
                return [data]
                
        except UnicodeDecodeError:
            with open(file_path, 'rb') as f:
                data = f.read()
            start_response('200 OK', [('Content-Type', mime_type)])
            return [data]
        except Exception as e:
            logging.error(f"Error serving file {file_path}: {str(e)}")
            start_response('500 Internal Server Error', [('Content-Type', 'text/plain')])
            return [b'Internal Server Error']

class TemplateView(View):
    template = ''

    def __init__(self, url) -> None:
        super().__init__(url)
        self.url = '/' + self.template

    def response(self, environ, start_response):
        file_name = self.path + self.url
        headers = [('Content-type', get_mime(file_name))]
        try:
            data = self.read_file(file_name[1:])
            status = '200 OK'
        except FileNotFoundError:
            data = ''
            status = '404 Not found'
        start_response(status, headers)
        return [data.encode('utf-8')]

    def read_file(self, file_name):
        with open(file_name, 'r', encoding='utf-8') as file:
            return file.read()
        
class IndexView(TemplateView):
    template = 'templates/index.html'
