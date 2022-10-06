from ambuda.utils.url_converters import ListConverter


def test_list_converter__to_python():
    lc = ListConverter(None)
    assert lc.to_python("a,b,c") == ["a", "b", "c"]
    assert lc.to_python("a+b+c") == ["a", "b", "c"]


def test_list_converter__to_url():
    lc = ListConverter(None)
    assert lc.to_url(["a", "b", "c"]) == "a,b,c"
