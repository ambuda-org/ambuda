from ambuda.views.proofing.stats import _calculate_stats_for_strings


def test_calculate_stats():
    strings = [
        "Test",
        "अहम्",
        "foo bar baz",
    ]
    stats = _calculate_stats_for_strings(strings)
    assert stats.num_pages == 3
    assert stats.num_words == 5
    assert stats.num_aksharas == 2
    assert stats.num_roman_characters == 13
