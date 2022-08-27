"""Utilities for creating a GitHub-style calendar heatmap of user activity."""

import calendar
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional


#: ISO weekday correspanding to Sunday.
ISO_SUNDAY = 7
#: Number of days per week.
DAYS_PER_WEEK = 7

#: Classes for each month span.
#: A month always takes at least 4 weeks and at most 5 weeks.
CLASSES = {
    4: "w-[3rem] bg-red",
    5: "w-[3.75rem] bg-red",
}


@dataclass
class MonthLabel:
    name: str
    offset: int


@dataclass
class HeatmapData:
    weeks: list[list[date]]
    month_labels: list[MonthLabel]
    counts: dict[date, int]


def count_revisions_per_day(revisions) -> dict[datetime, int]:
    counts = {}
    for r in sorted(revisions, key=lambda x: x.created):
        key = r.created.date()
        if key not in counts:
            counts[key] = 1
        else:
            counts[key] += 1
    return counts


def create_calendar_dates(last_date: Optional[date] = None) -> list[date]:
    """Return a year's worth of dates up to and including `last_date`.

    We construct a year's worth of dates then backfill until the first date is
    on a Sunday.

    :param `last_date`: the last date to include.
    """
    last_date = last_date or datetime.now().date()

    # Round start date to nearest Sunday.
    first_date = last_date - timedelta(days=365)
    if first_date.isoweekday() != ISO_SUNDAY:
        first_date -= timedelta(days=first_date.isoweekday())

    num_days = (last_date - first_date).days
    return [first_date + timedelta(days=i) for i in range(num_days)]


def create_month_labels(dates: list[date]) -> list[MonthLabel]:
    """Create column-aligned month labels for the heatmap.

    :param dates: a continuous list of calendar dates whose first date is
        on a Sunday.
    """
    if not dates:
        return []

    cur_month = None

    num_weeks = len(dates) // DAYS_PER_WEEK + (1 if len(dates) % DAYS_PER_WEEK else 0)

    # Find each month and where it starts in the grid.
    labels = []
    for i in range(num_weeks):
        sunday = dates[i * DAYS_PER_WEEK]
        print(i, sunday, flush=True)
        if sunday.month != cur_month:
            cur_month = sunday.month
            # Skip partial months
            if sunday.day > 7:
                continue

            if sunday.day == 1:
                offset = i
            else:
                offset = i - 1

            labels.append(
                MonthLabel(name=calendar.month_abbr[sunday.month], offset=offset)
            )
            cur_month = sunday.month
    return labels


def group_by_week(dates: list[date]) -> list[list[date]]:
    weeks = []
    row = []
    for d in dates:
        if d.isoweekday() == 7:
            if row:
                weeks.append(row)
            row = []
        row.append(d)
    if row:
        weeks.append(row)
    return weeks


def create(date_counts: dict[date, int]) -> HeatmapData:
    dates = create_calendar_dates()
    weeks = group_by_week(dates)
    month_labels = create_month_labels(dates)

    return HeatmapData(
        weeks=weeks,
        month_labels=month_labels,
        counts=date_counts,
    )
