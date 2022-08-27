from datetime import date

from ambuda.utils import heatmap


def test_count_per_date():
    dates = [
        date(2022, 1, 1),
        date(2022, 1, 1),
        date(2022, 1, 2),
        date(2022, 1, 3),
    ]
    counts = heatmap._count_per_date(dates)
    assert counts == {
        date(2022, 1, 1): 2,
        date(2022, 1, 2): 1,
        date(2022, 1, 3): 1,
    }


def test_create_calendar_dates():
    last_date = date(2022, 6, 1)
    dates = heatmap._create_calendar_dates(last_date)

    assert len(dates) >= 365
    assert dates[-1] == last_date
    for i, d1 in enumerate(dates[:-1]):
        d2 = dates[i + 1]
        assert (d2 - d1).days == 1


def test_group_by_week():
    dates = [
        date(2022, 1, 2),  # Sunday
        date(2022, 1, 3),
        date(2022, 1, 4),
        date(2022, 1, 5),
        date(2022, 1, 6),
        date(2022, 1, 7),
        date(2022, 1, 8),
        date(2022, 1, 9),
        date(2022, 1, 10),
    ]
    groups = heatmap._group_by_week(dates)
    assert len(groups) == 2
    assert groups == [
        [
            date(2022, 1, 2),
            date(2022, 1, 3),
            date(2022, 1, 4),
            date(2022, 1, 5),
            date(2022, 1, 6),
            date(2022, 1, 7),
            date(2022, 1, 8),
        ],
        [
            date(2022, 1, 9),
            date(2022, 1, 10),
        ],
    ]
