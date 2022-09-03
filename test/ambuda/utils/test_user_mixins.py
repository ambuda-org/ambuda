from ambuda import database as db
from ambuda.utils.user_mixins import AmbudaAnonymousUser, AmbudaUserMixin


def test_anonymous_user():
    u = AmbudaAnonymousUser()
    assert not u.is_p1
    assert not u.is_p2
    assert not u.is_proofreader
    assert not u.is_moderator
    assert not u.is_admin


def test_new_authenticated_user():
    u = db.User()
    assert not u.is_p1
    assert not u.is_p2
    assert not u.is_proofreader
    assert not u.is_moderator
    assert not u.is_admin
