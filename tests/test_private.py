import pytest
from webtest import TestApp
from app import app

pytestmark = pytest.mark.privatechat

def test_get_private_chats(test_app, auth_headers):
    resp = test_app.get('/get_private_chats', headers=auth_headers)
    assert resp.status_code == 200
    assert 'chats' in resp.json

def test_check_private_chats_updates(test_app, auth_headers):
    resp = test_app.get('/check_private_chats_updates', headers=auth_headers)
    assert resp.status_code == 200

def test_send_and_get_private_message(test_app, auth_headers):
    test_app.post('/register', {'username': 'privpartner', 'password': 'Testpass123!'})
    send_resp = test_app.post_json('/send_message', {
        'message': 'Private hello',
        'receiver': 'privpartner'
    }, headers=auth_headers)
    assert send_resp.status_code == 200
    resp = test_app.get('/get_private_messages?user=privpartner', headers=auth_headers)
    print(resp.json)
    assert resp.status_code == 200
    assert any(
        'Private hello' in str(msg.get('text', '')) or
        'Private hello' in str(msg.get('message_text', '')) or
        'Private hello' in str(msg.get('content', '')) or
        'Private hello' in str(msg)
        for msg in resp.json['messages']
    )

def test_private_chat_access_control(test_app, auth_headers):
    test_app.post('/register', {'username': 'privpartner2', 'password': 'Testpass123!'})
    test_app.post_json('/send_message', {
        'message': 'Secret',
        'receiver': 'privpartner2'
    }, headers=auth_headers)
    test_app2 = TestApp(app)
    test_app2.post('/register', {'username': 'intruder', 'password': 'Testpass123!'})
    test_app2.post('/login', {'username': 'intruder', 'password': 'Testpass123!'})
    headers2 = {'Authorization': 'Bearer intruder'}
    username = auth_headers['Authorization'].replace('Bearer ', '')
    resp = test_app2.get(f'/get_private_messages?chat_id=privpartner2&user={username}', headers=headers2, expect_errors=True)
    assert resp.status_code == 200
    assert resp.json['messages'] == []

def test_private_chat_updates_after_message(test_app, auth_headers):
    test_app.post('/register', {'username': 'privpartner3', 'password': 'Testpass123!'})
    test_app.post_json('/send_message', {
        'message': 'UpdateCheck',
        'receiver': 'privpartner3'
    }, headers=auth_headers)
    resp = test_app.get('/check_private_chats_updates', headers=auth_headers)
    assert resp.status_code == 200