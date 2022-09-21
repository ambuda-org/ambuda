from datetime import datetime

from flask_login import current_user

from ambuda import database as db
from ambuda import queries as q
from ambuda.views import auth


def _cleanup(session, *objects):
    for object in objects:
        session.delete(object)
    session.commit()


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
    r = client.get("/register")
    assert r.status_code == 200
    assert "Create an Ambuda account" in r.text


def test_register__unauth_post__ok(client):
    data = {
        "username": "krishna",
        "password": "narayana",
        "email": "krishna@mbh.org",
    }
    with client:
        r = client.post("/register", data=data)
        assert r.status_code == 302
        assert current_user.username == "krishna"


def test_register__auth(rama_client):
    r = rama_client.get("/register")
    assert r.status_code == 302


def test_sign_in__unauth(client):
    r = client.get("/sign-in")
    assert ">Sign in to Ambuda<" in r.text


def test_sign_in__unauth_post__ok(client):
    r = client.post(
        "/sign-in",
        data={
            "username": "ramacandra",
            "password": "maithili",
        },
    )
    assert r.status_code == 302


def test_sign_in__unauth_post__bad_username(client):
    r = client.post(
        "/sign-in",
        data={
            "username": "ravana",
            "password": "maithili",
        },
    )
    assert "Invalid username or password" in r.text


def test_sign_in__unauth_post__bad_password(client):
    r = client.post(
        "/sign-in",
        data={
            "username": "ramacandra",
            "password": "dasharatha",
        },
    )
    assert "Invalid username or password" in r.text


def test_sign_in__auth(rama_client):
    r = rama_client.get("/sign-in")
    assert r.status_code == 302


def test_sign_out__unauth(client):
    with client:
        r = client.get("/sign-out")
        assert r.status_code == 302
        assert current_user.is_anonymous


def test_sign_out__auth(rama_client):
    with rama_client:
        r = rama_client.get("/sign-out")
        assert r.status_code == 302
        assert current_user.is_anonymous


def test_get_reset_password_token__get(client):
    r = client.get("/reset-password")
    assert "Reset your password" in r.text


def test_reset_password_from_token(client):
    with client:
        user = q.user("u-admin")

    user_id = user.id
    raw_token = auth._create_reset_token(user_id)

    r = client.get("/reset-password/u-admin/bad_token")
    assert r.status_code == 302

    r = client.get(f"/reset-password/bad-user/{raw_token}")
    assert r.status_code == 302

    r = client.get(f"/reset-password/u-admin/{raw_token}")
    assert "Change password for" in r.text


def test_change_password(rama_client):
    r = rama_client.get("/change-password")
    assert ">Change" in r.text


def test_change_password__unauth(client):
    r = client.get("/change-password")
    assert r.status_code == 302
