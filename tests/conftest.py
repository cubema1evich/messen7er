import pytest
import time
import random
import string
from webtest import TestApp
from app import app, initialize_database

DB_PATH = 'data.db'

@pytest.fixture(scope='session', autouse=True)
def setup_db():
    # Создаём таблицы, если их нет
    initialize_database()
    yield

@pytest.fixture
def test_app():
    return TestApp(app)

@pytest.fixture
def auth_headers(test_app):
    # Только латиница и цифры, без подчёркиваний!
    rand = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    username = f'testuser{rand}'
    test_app.post('/register', {
        'username': username,
        'password': 'Testpass123!'
    })
    resp = test_app.post('/login', {
        'username': username,
        'password': 'Testpass123!'
    })
    cookies = resp.headers['Set-Cookie']
    return {'Authorization': f'Bearer {username}'}