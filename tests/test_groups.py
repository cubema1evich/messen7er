import pytest
pytestmark = pytest.mark.groups

def test_create_group(test_app, auth_headers):
    response = test_app.post_json('/create_group', {
        'name': 'Test Group'
    }, headers=auth_headers)
    assert response.status_code == 200
    assert response.json['group_id'] > 0

def test_add_to_group(test_app, auth_headers):
    # Регистрируем нового пользователя
    test_app.post('/register', {
        'username': 'newgroupmember',
        'password': 'Testpass123group!'
    })
    
    # Создаем группу
    group_resp = test_app.post_json('/create_group', {
        'name': 'Member Test'
    }, headers=auth_headers)
    group_id = group_resp.json['group_id']

    # Добавляем участника
    response = test_app.post_json('/add_to_group', {
        'group_id': group_id,
        'username': 'newgroupmember'
    }, headers=auth_headers)
    assert response.status_code == 200

def test_group_messages(test_app, auth_headers):
    # Создаем группу
    group_resp = test_app.post_json('/create_group', {
        'name': 'Message Test'
    }, headers=auth_headers)
    group_id = group_resp.json['group_id']
    
    # Отправляем сообщение
    response = test_app.post_json('/send_message', {
        'message': 'Group message',
        'group_id': group_id
    }, headers=auth_headers)
    assert response.status_code == 200

def test_create_group_success(test_app, auth_headers):
    resp = test_app.post_json('/create_group', {'name': 'pytest_group'}, headers=auth_headers)
    assert resp.status_code == 200
    assert 'group_id' in resp.json

def test_create_group_no_name(test_app, auth_headers):
    resp = test_app.post_json('/create_group', {}, headers=auth_headers, expect_errors=True)
    assert resp.status_code == 400
    assert 'error' in resp.json

def test_create_group_duplicate(test_app, auth_headers):
    test_app.post_json('/create_group', {'name': 'dup_group'}, headers=auth_headers)
    resp = test_app.post_json('/create_group', {'name': 'dup_group'}, headers=auth_headers, expect_errors=True)
    assert resp.status_code == 400
    assert 'уже существует' in resp.json['error']

def test_add_to_group_success(test_app, auth_headers):
    test_app.post('/register', {'username': 'pytest_member', 'password': 'pytestpass123'})
    group_resp = test_app.post_json('/create_group', {'name': 'pytest_add'}, headers=auth_headers)
    group_id = group_resp.json['group_id']
    resp = test_app.post_json('/add_to_group', {'group_id': group_id, 'username': 'pytest_member'}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json['status'] == 'success'

def test_add_to_group_user_not_found(test_app, auth_headers):
    group_resp = test_app.post_json('/create_group', {'name': 'pytest_add_nf'}, headers=auth_headers)
    group_id = group_resp.json['group_id']
    resp = test_app.post_json('/add_to_group', {'group_id': group_id, 'username': 'no_such_user'}, headers=auth_headers, expect_errors=True)
    assert resp.status_code == 404
    assert 'User not found' in resp.json['error']

def test_add_to_group_self(test_app, auth_headers):
    group_resp = test_app.post_json('/create_group', {'name': 'pytest_add_self'}, headers=auth_headers)
    group_id = group_resp.json['group_id']
    username = auth_headers['Authorization'].replace('Bearer ', '')
    resp = test_app.post_json('/add_to_group', {'group_id': group_id, 'username': username}, headers=auth_headers, expect_errors=True)
    assert resp.status_code == 400

def test_get_group_members(test_app, auth_headers):
    test_app.post('/register', {'username': 'pytest_member2', 'password': 'pytestpass123'})
    group_resp = test_app.post_json('/create_group', {'name': 'pytest_members'}, headers=auth_headers)
    group_id = group_resp.json['group_id']
    test_app.post_json('/add_to_group', {'group_id': group_id, 'username': 'pytest_member2'}, headers=auth_headers)
    resp = test_app.get(f'/get_group_members?group_id={group_id}', headers=auth_headers)
    assert resp.status_code == 200
    assert 'members' in resp.json
    assert any(m['username'] == 'pytest_member2' for m in resp.json['members'])

def test_leave_group(test_app, auth_headers):
    group_resp = test_app.post_json('/create_group', {'name': 'pytest_leave'}, headers=auth_headers)
    group_id = group_resp.json['group_id']
    resp = test_app.post_json('/leave_group', {'group_id': group_id}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json['status'] == 'success'

def test_rename_group(test_app, auth_headers):
    group_resp = test_app.post_json('/create_group', {'name': 'pytest_rename'}, headers=auth_headers)
    group_id = group_resp.json['group_id']
    resp = test_app.post_json('/rename_group', {'group_id': group_id, 'new_name': 'pytest_renamed'}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json['status'] == 'success'
    assert resp.json['new_name'] == 'pytest_renamed'

def test_remove_from_group(test_app, auth_headers):
    test_app.post('/register', {'username': 'member2', 'password': 'pytestpass123'})
    group_resp = test_app.post_json('/create_group', {'name': 'pytest_remove'}, headers=auth_headers)
    group_id = group_resp.json['group_id']
    test_app.post_json('/add_to_group', {'group_id': group_id, 'username': 'member2'}, headers=auth_headers)
    resp = test_app.post_json('/remove_from_group', {'group_id': group_id, 'username': 'member2'}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json['status'] == 'success'  

def test_change_member_role(test_app, auth_headers):
    test_app.post('/register', {'username': 'member3', 'password': 'pytestpass123'})
    group_resp = test_app.post_json('/create_group', {'name': 'pytest_role'}, headers=auth_headers)
    group_id = group_resp.json['group_id']
    test_app.post_json('/add_to_group', {'group_id': group_id, 'username': 'member3'}, headers=auth_headers)
    resp = test_app.post_json('/change_member_role', {'group_id': group_id, 'username': 'member3', 'role': 'admin'}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json['status'] == 'success'

def test_check_group_access(test_app, auth_headers):
    group_resp = test_app.post_json('/create_group', {'name': 'pytest_access'}, headers=auth_headers)
    group_id = group_resp.json['group_id']
    resp = test_app.get(f'/check_group_access?group_id={group_id}', headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json['access'] is True

def test_get_general_chat_members(test_app, auth_headers):
    resp = test_app.get('/get_general_chat_members', headers=auth_headers)
    assert resp.status_code == 200
    assert 'members' in resp.json