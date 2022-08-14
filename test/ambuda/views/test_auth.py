from datetime import datetime

from flask_login import current_user

from ambuda import database as db
from ambuda.views import auth


def test_is_valid_reset_token():
    row = db.PasswordResetToken(
        user_id=1,
        is_active=True,
        created_at=datetime(2022, 1, 15, 12, 0, 0),
    )
    inactive_row = db.PasswordResetToken(
        user_id=1,
        is_active=False,
        created_at=datetime(2022, 1, 15, 12, 0, 0),
    )
    row.set_token("secret")
    inactive_row.set_token("secret")

    # OK
    assert auth._is_valid_reset_token(
        row, "secret", now=datetime(2022, 1, 15, 13, 0, 0)
    )
    # Too old
    assert not auth._is_valid_reset_token(
        row, "secret", now=datetime(2022, 1, 18, 12, 0, 0)
    )
    # Bad token
    assert not auth._is_valid_reset_token(
        row, "secret2", now=datetime(2022, 1, 15, 13, 0, 0)
    )
    # Missing row
    assert not auth._is_valid_reset_token(
        None, "secret", now=datetime(2022, 1, 15, 13, 0, 0)
    )
    # Inactive
    assert not auth._is_valid_reset_token(
        inactive_row, "secret", now=datetime(2022, 1, 15, 13, 0, 0)
    )


def test_register__unauth(client):
    resp = client.get("/register")
    assert resp.status_code == 200
    assert ">Create an Ambuda account<" in resp.text


def test_register__unauth_post__ok(client):
    data = {
        "username": "krishna",
        "password": "narayana",
        "email": "krishna@mbh.org",
    }
    with client:
        resp = client.post("/register", data=data)
        assert resp.status_code == 302
        assert current_user.username == "krishna"


def test_register__auth(rama_client):
    resp = rama_client.get("/register")
    assert resp.status_code == 302


def test_sign_in__unauth(client):
    resp = client.get("/sign-in")
    assert ">Sign in to Ambuda<" in resp.text


def test_sign_in__unauth_post__ok(client):
    resp = client.post(
        "/sign-in",
        data={
            "username": "ramacandra",
            "password": "maithili",
        },
    )
    assert resp.status_code == 302


def test_sign_in__unauth_post__bad_username(client):
    resp = client.post(
        "/sign-in",
        data={
            "username": "ravana",
            "password": "maithili",
        },
    )
    assert "Invalid username or password" in resp.text


def test_sign_in__unauth_post__bad_password(client):
    resp = client.post(
        "/sign-in",
        data={
            "username": "ramacandra",
            "password": "dasharatha",
        },
    )
    assert "Invalid username or password" in resp.text


def test_sign_in__auth(rama_client):
    resp = rama_client.get("/sign-in")
    assert resp.status_code == 302


def test_sign_out__unauth(client):
    with client:
        resp = client.get("/sign-out")
        assert resp.status_code == 302
        assert current_user.is_anonymous


def test_sign_out__auth(rama_client):
    with rama_client:
        resp = rama_client.get("/sign-out")
        assert resp.status_code == 302
        assert current_user.is_anonymous
