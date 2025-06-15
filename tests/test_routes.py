import unittest
import routes
import mimes
import pytest
pytestmark = pytest.mark.routes

class TestRoutes(unittest.TestCase):
    def route(self, url, expected):
        self.assertEqual(routes.route(url), expected)

    def test_root(self):
        """Тест корня сайта"""
        self.route('/', '/')
        self.route('/index.html', '/index.html')

    def test_static(self):
        """Тест static файлов"""
        self.route('/static/app.js', '/static/app.js')

class TestMimes(unittest.TestCase):
    def mime(self, file, content):
        self.assertEqual(mimes.get_mime(file), content)

    def test_html(self):
        self.mime('/index.html', 'text/html')

    def test_css(self):
        self.mime('/static/style.css', 'text/css')
