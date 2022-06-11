import pytest

from ambuda.seed import sandhi_utils


@pytest.mark.parametrize(
    ["first", "second", "result"],
    [
        # ac
        ("aMSa", "aMSa", "aMSAMSa"),
        ("mahA", "aMga", "mahAMga"),
        ("eka", "eka", "ekEka"),
        ("aDara", "ozWa", "aDarOzWa"),
        ("agni", "Alaya", "agnyAlaya"),
        # hal
        ("tvac", "indriya", "tvagindriya"),
        ("diS", "kara", "dikkara"),
        # visarga
        ("manas", "hara", "manohara"),
    ],
)
def test_apply(first, second, result):
    assert sandhi_utils.apply(first, second) == result
