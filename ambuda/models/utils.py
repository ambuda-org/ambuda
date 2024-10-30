from datetime import datetime, UTC

def utc_now():
    """Replaces `datetime.utcnow`, which is deprecated."""
    return datetime.now(UTC)
