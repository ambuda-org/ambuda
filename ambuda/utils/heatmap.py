"""Utilities for creating a GitHub-style calendar heatmap of user activity.

Known issues:
- This logic is not timezone-sensitive and treats all dates as UTC.
- This logic is not locale-sensitive and uses English day and month names.
"""

import calendar
import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional, Iterator

#: ISO weekday correspanding to Sunday.
ISO_SUNDAY = 7
#: Number of days per week.
DAYS_PER_WEEK = 7


@dataclass
class MonthLabel:
    #: The label for this month
    name: str
    #: The 0-indexed week offset for this month against some list of dates.
    offset: int


@dataclass
class HeatmapData:
    #: A list of 7-day blocks each starting with Sunday.
    weeks: list[list[date]]
    #: A list of month labels with column offsets.
    month_labels: list[MonthLabel]
    #: The counts per date.
    counts: dict[date, int]


def _count_per_date(iter_date: Iterator[date]) -> dict[date, int]:
    """Create a simple histogram over the given dates."""
    counts = {}
    for d in sorted(iter_date):
        if d not in counts:
            counts[d] = 1
        else:
            counts[d] += 1
    return counts


def _create_calendar_dates(last_date: Optional[date] = None) -> list[date]:
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
    return [first_date + timedelta(days=i) for i in range(num_days + 1)]


def _create_month_labels(dates: list[date]) -> list[MonthLabel]:
    """Create column-aligned month labels for the heatmap.

    :param dates: a continuous list of calendar dates whose first date is
        on a Sunday.
    """

    num_weeks = math.ceil(len(dates) / DAYS_PER_WEEK)
    labels = []
    cur_month = None
    for i in range(num_weeks):
        sunday = dates[i * DAYS_PER_WEEK]
        # Start of new month.
        if sunday.month != cur_month:
            cur_month = sunday.month
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


def _group_by_week(dates: list[date]) -> list[list[date]]:
    """Group the given dates by week. Each week starts on Sunday.

    :param dates: a sorted list of dates.
    """
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


def create(date_iter: Iterator[date]) -> HeatmapData:
    """Create the data needed to render a calendar heatmap.

    :param date_iter: an iterator of date events. The more date appear, the
        more intense its heatmap color will be.
    """
    counts = _count_per_date(date_iter)
    dates = _create_calendar_dates()
    weeks = _group_by_week(dates)
    month_labels = _create_month_labels(dates)

    return HeatmapData(
        weeks=weeks,
        month_labels=month_labels,
        counts=counts,
    )
