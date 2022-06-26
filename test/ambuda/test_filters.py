import ambuda.filters as f


def test_devanagari():
    assert f.devanagari("saMskRtam") == "संस्कृतम्"


def test_roman():
    assert f.roman("saMskRtam") == "saṃskṛtam"
