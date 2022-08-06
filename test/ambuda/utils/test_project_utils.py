import pytest

import ambuda.utils.project_utils as pu


@pytest.mark.parametrize(
    "n,expected",
    [
        (1, "i"),
        (2, "ii"),
        (3, "iii"),
        (4, "iv"),
        (5, "v"),
        (6, "vi"),
        (7, "vii"),
        (8, "viii"),
        (9, "ix"),
        (10, "x"),
        (11, "xi"),
        (14, "xiv"),
        (15, "xv"),
        (16, "xvi"),
        (19, "xix"),
        (20, "xx"),
        (21, "xxi"),
        (30, "xxx"),
        (40, "xl"),
        (50, "l"),
        (60, "lx"),
        (90, "xc"),
        (100, "c"),
    ],
)
def test_int_to_roman(n, expected):
    assert pu.int_to_roman(n) == expected


def test_parse_page_number_spec():
    assert pu.parse_page_number_spec("1 = -") == [pu.Rule(1, "-")]
    assert pu.parse_page_number_spec("3 = title") == [pu.Rule(3, "title")]


@pytest.mark.parametrize(
    "rules,expected",
    [
        ([], "1 2 3 4 5"),
        ([pu.Rule(1, "-")], "- - - - -"),
        ([pu.Rule(1, "2")], "2 3 4 5 6"),
        ([pu.Rule(2, "i")], "1 i ii iii iv"),
        ([pu.Rule(1, "i"), pu.Rule(3, "2")], "i ii 2 3 4"),
    ],
)
def test_apply_rules(rules, expected):
    assert pu.apply_rules(5, rules) == expected.split()
