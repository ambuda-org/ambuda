from unittest.mock import MagicMock, patch

import ambuda.database as db
from ambuda.tasks.uncovered_reports import (
    REPORT_LOCK_TTL,
    maybe_rerun_report,
    run_report_inner,
)
from ambuda.queries import get_engine, get_session


def test_maybe_rerun_report_acquires_lock_and_dispatches():
    mock_redis = MagicMock()
    mock_redis.set.return_value = True

    with patch("ambuda.tasks.uncovered_reports.run_report") as mock_task:
        result = maybe_rerun_report(7, "testing", redis_client=mock_redis)

    assert result is True
    mock_redis.set.assert_called_once_with(
        db.ProjectUncoveredReport.rerun_lock_key(7),
        "1",
        nx=True,
        ex=REPORT_LOCK_TTL,
    )
    mock_task.apply_async.assert_called_once_with(args=(7, "testing"))


def test_maybe_rerun_report_noop_when_lock_held():
    mock_redis = MagicMock()
    mock_redis.set.return_value = False

    with patch("ambuda.tasks.uncovered_reports.run_report") as mock_task:
        result = maybe_rerun_report(7, "testing", redis_client=mock_redis)

    assert result is False
    mock_task.apply_async.assert_not_called()


def test_run_report_inner_writes_report_and_clears_lock(flask_app):
    """Running the inner task creates a ProjectUncoveredReport and clears the lock."""
    with flask_app.app_context():
        session = get_session()
        from sqlalchemy import select

        project = session.execute(
            select(db.Project).filter_by(slug="test-project")
        ).scalar_one()

        # Make sure no stale report from a previous test.
        session.execute(
            db.ProjectUncoveredReport.__table__.delete().where(
                db.ProjectUncoveredReport.project_id == project.id
            )
        )
        session.commit()

        engine = get_engine()
        mock_redis = MagicMock()

        run_report_inner(
            project.id,
            flask_app.config["AMBUDA_ENVIRONMENT"],
            engine=engine,
            redis_client=mock_redis,
        )

        report = session.execute(
            select(db.ProjectUncoveredReport).filter_by(project_id=project.id)
        ).scalar_one()
        assert report.generated_at is not None
        assert "blocks" in report.payload
        assert "total_proofed_blocks" in report.payload

        mock_redis.delete.assert_called_once_with(
            db.ProjectUncoveredReport.rerun_lock_key(project.id)
        )

        # Cleanup
        session.delete(report)
        session.commit()
