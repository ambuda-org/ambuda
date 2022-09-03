from flask_login import AnonymousUserMixin, UserMixin
from ambuda.enums import SiteRole


class AmbudaAnonymousUser(AnonymousUserMixin):
    """An anonymous user with limited permissions."""

    def has_role(self, *a):
        return False

    @property
    def is_p1(self) -> bool:
        return False

    @property
    def is_p2(self) -> bool:
        return False

    @property
    def is_proofreader(self) -> bool:
        return False

    @property
    def is_moderator(self) -> bool:
        return False

    @property
    def is_admin(self) -> bool:
        return False


class AmbudaUserMixin(UserMixin):
    def has_role(self, role: SiteRole) -> bool:
        return role.value in {r.name for r in self.roles}

    @property
    def is_p1(self) -> bool:
        return self.has_role(SiteRole.P1)

    @property
    def is_p2(self) -> bool:
        return self.has_role(SiteRole.P2)

    @property
    def is_proofreader(self) -> bool:
        return self.has_role(SiteRole.P1) or self.has_role(SiteRole.P2)

    @property
    def is_moderator(self) -> bool:
        return self.has_role(SiteRole.MODERATOR)

    @property
    def is_admin(self) -> bool:
        return self.has_role(SiteRole.ADMIN)
