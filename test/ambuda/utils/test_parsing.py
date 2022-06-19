import pytest

from ambuda.utils.parsing import readable_parse


@pytest.mark.parametrize(
    ["raw", "expected"],
    [
        ("n-m-1-s", "noun, masculine nominative singular"),
        ("a-m-1-s", "adjective, masculine nominative singular"),
        ("v-3-s-lat", "verb, third-person singular present"),
    ],
)
def test_readable_parse(raw, expected):
    assert readable_parse(raw) == expected
