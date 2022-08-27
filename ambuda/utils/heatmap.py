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
    span: int
    classes: str


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

    labels = []
    months_and_indices = []
    cur_month = None

    num_weeks = len(dates) // DAYS_PER_WEEK + (1 if len(dates) % DAYS_PER_WEEK else 0)

    # Find each month and where it starts in the grid.
    for i in range(num_weeks):
        sunday = dates[i * DAYS_PER_WEEK]
        if sunday.month != cur_month:
            cur_month = sunday.month
            # Skip partial months
            if sunday.day > 7:
                continue

            months_and_indices.append((sunday.month, i))
            cur_month = sunday.month

    months_and_indices.append((None, num_weeks + 1))

    # Convert indices to spans.
    labels = []
    for i, (month, index) in enumerate(months_and_indices[:-1]):
        next_index = months_and_indices[i + 1][1]
        width = next_index - index
        labels.append(
            MonthLabel(
                name=calendar.month_abbr[month], span=width, classes=CLASSES[width]
            )
        )

    return labels
