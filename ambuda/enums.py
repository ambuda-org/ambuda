from enum import Enum


class SiteRole(str, Enum):
    """Defines user roles on Ambuda."""

    #: Can mark pages as yellow
    P1 = "p1"
    #: Can mark pages as green
    P2 = "p2"
    #: Administrator rights
    ADMIN = "admin"


class SitePageStatus(str, Enum):
    """Defines page statuses."""

    #: Needs more work
    R0 = "reviewed-0"
    #: Proofread once.
    R1 = "reviewed-1"
    #: Proofread twice.
    R2 = "reviewed-2"
    #: Not relevant.
    SKIP = "skip"
