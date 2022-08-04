from enum import Enum


class SiteRole(Enum):
    """Defines user roles on Ambuda."""

    #: Can mark pages as yellow
    P1 = "p1"
    #: Can mark pages as green
    P2 = "p2"
    #: Administrator rights
    ADMIN = "admin"
