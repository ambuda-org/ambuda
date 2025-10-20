from enum import Enum


class SiteRole(str, Enum):
    """Defines user roles."""

    #: Basic proofer. Can mark pages as yellow and upload simple projects.
    P1 = "p1"
    #: Advanced proofer. Can mark pages as green, upload arbitrary PDFs, and
    #: run operations across an entire project.
    P2 = "p2"
    #: Moderator. Can delete projects, promote and ban users, and run
    #: operations across the entire proofing effort.
    MODERATOR = "moderator"
    #: Administrator. Has full access to the database.
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

class TextGenre(str, Enum):
    """Define text genres."""

    ITIHASA = "Itihasa"
    UPANISHAT = "Upanishat"
    KAVYA = "Kavya"
    ANYE = "Anye"
