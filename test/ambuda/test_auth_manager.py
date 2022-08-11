from ambuda.auth import AmbudaAnonymousUser


def test_unauth_user_has_no_permissions():
    unauth = AmbudaAnonymousUser()
    assert not unauth.is_admin
    assert not unauth.is_proofreader
