from datetime import UTC, datetime


def utc_now():
    """Replaces `datetime.utcnow`, which is deprecated."""
    return datetime.now(UTC)
