from ambuda import database as db
from ambuda import queries as q
from ambuda.enums import SiteRole
from ambuda.utils.user_mixins import AmbudaAnonymousUser, AmbudaUserMixin


def test_anonymous_user():
    u = AmbudaAnonymousUser()
    assert not u.is_p1
    assert not u.is_p2
    assert not u.is_proofreader
    assert not u.is_moderator
    assert not u.is_admin


def test_new_authenticated_user(client):
    u = db.User()
    session = q.get_session()
    p1 = session.query(db.Role).filter_by(name=SiteRole.P1).one()

    u.roles = [p1]
    assert u.is_p1
    assert not u.is_p2
    assert u.is_proofreader
    assert not u.is_moderator
    assert not u.is_admin
