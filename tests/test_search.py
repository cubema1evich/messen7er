import pytest
import time

pytestmark = pytest.mark.search

def test_search_users(test_app, auth_headers):
    response = test_app.get('/search_users?q=test', headers=auth_headers)
    assert response.status_code == 200
    assert any('testuser' in u for u in response.json['users'])

def test_search_users_no_results(test_app, auth_headers):
    response = test_app.get('/search_users?q=nonexistentuser', headers=auth_headers)
    assert response.status_code == 200
    assert response.json['users'] == []

def test_search_users_special_chars(test_app, auth_headers):
    # Зарегистрировать пользователя с цифрами
    test_app.post('/register', {'username': 'testuser123', 'password': 'Testpass123!'})
    response = test_app.get('/search_users?q=123', headers=auth_headers)
    assert response.status_code == 200
    assert any('123' in u for u in response.json['users'])

def test_search_messages(test_app, auth_headers):
    # Отправляем сообщение для поиска
    test_app.post_json('/send_message', {
        'message': 'Special search term'
    }, headers=auth_headers)
    # Ищем
    response = test_app.get('/search_messages?q=Special', headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json['messages']) > 0
    assert any('Special' in msg['text'] for msg in response.json['messages'])

def test_search_messages_no_results(test_app, auth_headers):
    response = test_app.get('/search_messages?q=notfoundterm', headers=auth_headers)
    assert response.status_code == 200
    assert response.json['messages'] == []

def test_search_messages_pagination(test_app, auth_headers):
    # Отправляем несколько сообщений
    for i in range(15):
        test_app.post_json('/send_message', {'message': f'PaginateTest {i}'}, headers=auth_headers)
    response = test_app.get('/search_messages?q=PaginateTest&per_page=5&page=2', headers=auth_headers)
    assert response.status_code == 200
    assert response.json['page'] == 2
    assert response.json['per_page'] == 5
    assert len(response.json['messages']) <= 5

def test_search_messages_sorting(test_app, auth_headers):
    # Отправляем два сообщения с разным временем
    test_app.post_json('/send_message', {'message': 'SortTest1'}, headers=auth_headers)
    time.sleep(1)
    test_app.post_json('/send_message', {'message': 'SortTest2'}, headers=auth_headers)
    # Поиск с сортировкой по дате
    response = test_app.get('/search_messages?q=SortTest&sort=date', headers=auth_headers)
    assert response.status_code == 200
    assert response.json['messages'][0]['text'] == 'SortTest2'

def test_search_messages_private(test_app, auth_headers):
    # Создаем второго пользователя
    test_app.post('/register', {'username': 'searchpartner', 'password': 'Testpass123!'})
    # Отправляем приватное сообщение
    test_app.post_json('/send_message', {
        'message': 'PrivateSearch',
        'receiver': 'searchpartner'
    }, headers=auth_headers)
    # Поиск по приватному чату
    response = test_app.get('/search_messages?q=PrivateSearch&type=private&chat_id=searchpartner', headers=auth_headers)
    assert response.status_code == 200
    assert any('PrivateSearch' in msg['text'] for msg in response.json['messages'])

def test_search_messages_group(test_app, auth_headers):
    # Создаем группу
    group_resp = test_app.post_json('/create_group', {'name': 'searchgroup'}, headers=auth_headers)
    group_id = group_resp.json['group_id']
    # Отправляем сообщение в группу
    test_app.post_json('/send_message', {
        'message': 'GroupSearch',
        'group_id': group_id
    }, headers=auth_headers)
    # Поиск по группе
    response = test_app.get(f'/search_messages?q=GroupSearch&type=group&chat_id={group_id}', headers=auth_headers)
    assert response.status_code == 200
    assert any('GroupSearch' in msg['text'] for msg in response.json['messages'])