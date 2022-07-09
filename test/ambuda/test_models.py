import ambuda.database as db
from ambuda.queries import get_engine, get_session


def test_user__set_and_check_password(client):
    session = get_session()
    user = db.User(username="test", email="test@ambuda.org")
    user.set_password("my-password")
    session.add(user)
    session.commit()

    assert user.check_password("my-password")
    assert not user.check_password("my-password2")
