from webob import Request
import pytest
pytestmark = pytest.mark.auth

def test_register(test_app):
    response = test_app.post('/register', {
        'username': 'testuser_reg',
        'password': 'Testpass123!'
    })
    assert response.status_code == 200

def test_login(test_app):
    test_app.post('/register', {
        'username': 'testuser_login',
        'password': 'Testpass123!'
    })
    response = test_app.post('/login', {
        'username': 'testuser_login',
        'password': 'Testpass123!'
    })
    assert response.status_code == 200

def test_secured_endpoint(test_app, auth_headers):
    response = test_app.get('/get_user_id', headers=auth_headers)
    assert response.status_code == 200
    assert b'testuser' in response.body

def test_register_valid(test_app):
    resp = test_app.post('/register', {
        'username': 'user_valid',
        'password': 'Validpass123'
    })
    assert resp.status_code == 200
    assert 'message' in resp.json

def test_register_short_password(test_app):
    resp = test_app.post('/register', {
        'username': 'user_shortpw',
        'password': '123'
    }, expect_errors=True)
    assert resp.status_code == 500
    assert 'Пароль должен быть не менее 6 символов' in resp.json['error']

def test_register_invalid_username(test_app):
    resp = test_app.post('/register', {
        'username': '!!badname',
        'password': 'Validpass123'
    }, expect_errors=True)
    assert resp.status_code == 500
    assert 'Недопустимое имя пользователя' in resp.json['error']

def test_register_duplicate(test_app):
    test_app.post('/register', {
        'username': 'user_dup',
        'password': 'Validpass123'
    })
    resp = test_app.post('/register', {
        'username': 'user_dup',
        'password': 'Validpass123'
    }, expect_errors=True)
    assert resp.status_code == 400
    assert 'уже существует' in resp.json['error']

def test_login_valid(test_app):
    test_app.post('/register', {
        'username': 'user_login',
        'password': 'Validpass123'
    })
    resp = test_app.post('/login', {
        'username': 'user_login',
        'password': 'Validpass123'
    })
    assert resp.status_code == 200
    assert 'Set-Cookie' in resp.headers
    assert resp.json['redirect'] == '/'

def test_login_nonexistent_user(test_app):
    resp = test_app.post('/login', {
        'username': 'no_such_user',
        'password': 'any'
    }, expect_errors=True)
    assert resp.status_code == 401
    assert 'Пользователь не найден' in resp.json['error']

def test_login_wrong_password(test_app):
    test_app.post('/register', {
        'username': 'user_wrongpw',
        'password': 'Validpass123'
    })
    resp = test_app.post('/login', {
        'username': 'user_wrongpw',
        'password': 'Wrongpass'
    }, expect_errors=True)
    assert resp.status_code == 401
    assert 'Неверный пароль' in resp.json['error']