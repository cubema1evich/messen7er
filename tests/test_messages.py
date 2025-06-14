import pytest
from webtest import TestApp
from app import app

pytestmark = pytest.mark.messages

def test_send_message(test_app, auth_headers):
    response = test_app.post_json('/send_message', {
        'message': 'Hello World!'
    }, headers=auth_headers)
    assert response.status_code == 200
    assert response.json['status'] == 'success'
    assert 'message_id' in response.json

def test_get_messages(test_app, auth_headers):
    # Сначала отправляем сообщение
    send_resp = test_app.post_json('/send_message', {
        'message': 'Test message'
    }, headers=auth_headers)
    msg_id = send_resp.json['message_id']

    # Получаем сообщения
    response = test_app.get('/get_messages?timestamp=0', headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json['messages']) > 0
    # Проверяем, что хотя бы одно сообщение содержит нужный текст
    assert any('Test message' in msg['message_text'] for msg in response.json['messages'])

def test_delete_message(test_app, auth_headers):
    # Отправляем сообщение
    send_resp = test_app.post_json('/send_message', {
        'message': 'To be deleted'
    }, headers=auth_headers)
    msg_id = send_resp.json['message_id']

    # Удаляем
    response = test_app.delete(f'/delete_message/{msg_id}?type=general', headers=auth_headers)
    assert response.status_code == 200
    assert 'Сообщение удалено' in response.json['status']

def test_edit_message(test_app, auth_headers):
    # Отправляем сообщение
    send_resp = test_app.post_json('/send_message', {
        'message': 'To be edited'
    }, headers=auth_headers)
    msg_id = send_resp.json['message_id']

    # Редактируем
    response = test_app.put_json(f'/edit_message/{msg_id}?type=general', {
        'message': 'Edited message'
    }, headers=auth_headers)
    assert response.status_code == 200
    assert 'Сообщение обновлено' in response.json['status']

def test_send_empty_message(test_app, auth_headers):
    response = test_app.post_json('/send_message', {
        'message': ''
    }, headers=auth_headers)
    assert response.status_code == 200
    assert response.json['status'] == 'nothing to save'

def test_delete_foreign_message(test_app, auth_headers):
    # Пользователь 1 отправляет сообщение
    send_resp = test_app.post_json('/send_message', {
        'message': 'Not your message'
    }, headers=auth_headers)
    msg_id = send_resp.json['message_id']

    # Новый пользователь, новый клиент
    test_app2 = TestApp(app)
    test_app2.post('/register', {'username': 'otheruser', 'password': 'Otherpass123!'})
    login_resp = test_app2.post('/login', {'username': 'otheruser', 'password': 'Otherpass123!'})
    headers2 = {'Authorization': 'Bearer otheruser'}
    response = test_app2.delete(f'/delete_message/{msg_id}?type=general', headers=headers2, expect_errors=True)
    assert response.status_code == 403

def test_get_messages_timestamp_filter(test_app, auth_headers):
    # Отправляем два сообщения с задержкой
    import time as t
    send_resp1 = test_app.post_json('/send_message', {'message': 'First'}, headers=auth_headers)
    t.sleep(1)
    send_resp2 = test_app.post_json('/send_message', {'message': 'Second'}, headers=auth_headers)
    msg_id2 = send_resp2.json['message_id']

    # Получаем только новые сообщения по timestamp
    response = test_app.get(f'/get_messages?timestamp={int(t.time())-1}', headers=auth_headers)
    assert response.status_code == 200
    assert any(msg['message_text'] == 'Second' for msg in response.json['messages'])

def test_send_system_message(test_app, auth_headers):
    resp = test_app.post_json('/send_system_message', {'message': 'System!'}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json['status'] == 'success'