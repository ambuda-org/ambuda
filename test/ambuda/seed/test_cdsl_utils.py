import pytest
from ambuda.dict_utils import standardize_key, standardize_apte_key


@pytest.mark.parametrize(
    ["before", "after"],
    [
        # No change
        ("nara", "nara"),
        # Basic changes
        ("aMga", "aNga"),
        ("saMcaya", "saYcaya"),
        ("aMqa", "aRqa"),
        ("aMte", "ante"),
        ("aMbu", "ambu"),
        # Multiple changes
        ("laMbaMte", "lambante"),
    ],
)
def test_standardize_key(before, after):
    assert standardize_key(before) == after


@pytest.mark.parametrize(
    ["before", "after"],
    [
        ("naraH", "nara"),
        ("vanaM", "vana"),
        ("agniH", "agni"),
        ("guruH", "guru"),
        ("vadhUH", "vadhU"),
        ("manas", "manas"),
    ],
)
def test_standardize_apte_key(before, after):
    assert standardize_apte_key(before) == after
