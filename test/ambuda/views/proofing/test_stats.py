from ambuda.views.proofing.stats import _calculate_stats_for_strings


def test_calculate_stats():
    strings = [
        "Test",
        "अहम्",
        "astyuttarasyāṃ diśi devatātmā",
        "foo bar baz",
    ]
    stats = _calculate_stats_for_strings(strings)
    assert stats.num_pages == 4
    assert stats.num_words == 8
    assert stats.num_aksharas == 2
    # 4 + (29 - 2) + (11 - 2) = 40
    assert stats.num_roman_characters == 40
