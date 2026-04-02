from unittest.mock import MagicMock, patch

import ambuda.database as db
from ambuda.tasks.text_validation import (
    maybe_rerun_report,
    run_report_inner,
    REPORT_LOCK_TTL,
)
from ambuda.queries import get_engine, get_session


def test_maybe_rerun_report_acquires_lock_and_dispatches():
    """First call acquires the lock and dispatches the task."""
    mock_redis = MagicMock()
    mock_redis.set.return_value = True  # lock acquired

    with patch("ambuda.tasks.text_validation.run_report") as mock_task:
        result = maybe_rerun_report(42, "testing", redis_client=mock_redis)

    assert result is True
    mock_redis.set.assert_called_once_with(
        db.TextReport.rerun_lock_key(42), "1", nx=True, ex=REPORT_LOCK_TTL
    )
    mock_task.apply_async.assert_called_once_with(args=(42, "testing"))


def test_maybe_rerun_report_noop_when_lock_held():
    """Second call is a no-op when the lock is already held."""
    mock_redis = MagicMock()
    mock_redis.set.return_value = False  # lock NOT acquired

    with patch("ambuda.tasks.text_validation.run_report") as mock_task:
        result = maybe_rerun_report(42, "testing", redis_client=mock_redis)

    assert result is False
    mock_task.apply_async.assert_not_called()


def test_maybe_rerun_report_reacquires_after_expiry():
    """After lock expiry, a new call can acquire and dispatch again."""
    mock_redis = MagicMock()
    mock_redis.set.side_effect = [True, False, True]

    with patch("ambuda.tasks.text_validation.run_report") as mock_task:
        assert maybe_rerun_report(42, "testing", redis_client=mock_redis) is True
        assert maybe_rerun_report(42, "testing", redis_client=mock_redis) is False
        assert maybe_rerun_report(42, "testing", redis_client=mock_redis) is True

    assert mock_task.apply_async.call_count == 2


def test_run_report_inner_clears_lock(flask_app):
    """run_report_inner clears the Redis lock after committing."""
    with flask_app.app_context():
        session = get_session()
        text = db.Text(slug="test-lock-clear", title="Test Lock Clear", stage="public")
        session.add(text)
        session.flush()

        section = db.TextSection(text_id=text.id, slug="1", title="Section 1")
        session.add(section)
        session.flush()

        block = db.TextBlock(
            text_id=text.id,
            section_id=section.id,
            slug="1.1",
            xml="<lg><l>rAmaH</l></lg>",
            n=1,
        )
        session.add(block)
        session.commit()

        engine = get_engine()
        mock_redis = MagicMock()

        run_report_inner(
            text.id,
            flask_app.config["AMBUDA_ENVIRONMENT"],
            engine=engine,
            redis_client=mock_redis,
        )

        mock_redis.delete.assert_called_once_with(db.TextReport.rerun_lock_key(text.id))
