import pytest
from ambuda.dict_utils import standardize_key, expand_apte_keys


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
        ("nara", ["nara", "naraH", "naraM"]),
        ("agni", ["agni", "agniH"]),
        ("guru", ["guru", "guruH"]),
        ("lakzmI", ["lakzmI", "lakzmIH"]),
        ("vaDU", ["vaDU", "vaDUH"]),
        ("idAnIm", ["idAnIm", "idAnIM"]),
    ],
)
def test_expand_apte_keys(before, after):
    assert expand_apte_keys(before) == after