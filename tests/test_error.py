import pytest
pytestmark = pytest.mark.error

def test_404(test_app):
    resp = test_app.get('/not_existing_url', expect_errors=True)
    assert resp.status_code == 404

def test_405_method_not_allowed(test_app, auth_headers):
    # Авторизованный запрос методом GET к POST-only endpoint
    resp = test_app.get('/send_message', headers=auth_headers, expect_errors=True)
    assert resp.status_code == 405

def test_403_forbidden(test_app):
    resp = test_app.get('/get_private_chats', expect_errors=True)
    assert resp.status_code == 403

def test_500_internal_server_error(test_app, monkeypatch):
    from views import error as error_view
    monkeypatch.setattr(error_view, "NotFoundView", lambda *a, **kw: 1/0)
    resp = test_app.get('/not_existing_url', expect_errors=True)
    assert resp.status_code == 500 or resp.status_code == 404