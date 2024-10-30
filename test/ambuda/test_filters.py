from datetime import datetime, UTC

import pytest

import ambuda.filters as f


def test_devanagari():
    assert f.devanagari("saMskRtam") == "संस्कृतम्"


def test_roman():
    assert f.roman("saMskRtam") == "saṃskṛtam"


@pytest.mark.parametrize(
    "then,expected",
    [
        (datetime(2022, 6, 2, 6, 0, 0), "now"),
        (datetime(2022, 6, 2, 5, 59, 59), "1 second ago"),
        (datetime(2022, 6, 2, 5, 59, 1), "59 seconds ago"),
        (datetime(2022, 6, 2, 5, 59, 0), "1 minute ago"),
        (datetime(2022, 6, 2, 5, 0, 1), "59 minutes ago"),
        (datetime(2022, 6, 2, 5, 0, 0), "1 hour ago"),
        (datetime(2022, 6, 1, 6, 0, 1), "23 hours ago"),
        (datetime(2022, 6, 1, 6, 0, 0), "1 day ago"),
        (datetime(2022, 5, 3, 6, 0, 0), "30 days ago"),
        (datetime(2022, 5, 1, 6, 0, 0), "1 month ago"),
        (datetime(2021, 7, 2, 6, 0, 0), "11 months ago"),
        (datetime(2021, 6, 2, 6, 0, 0), "1 year ago"),
        (datetime(2019, 6, 2, 6, 0, 0), "3 years ago"),
    ],
)
def test_time_ago(then, expected):
    now = datetime(2022, 6, 2, 6, 0, 0, tzinfo=UTC)
    assert f.time_ago(then, now=now) == expected


def test_markdown():
    assert f.markdown("*test*") == "<p><em>test</em></p>\n"
