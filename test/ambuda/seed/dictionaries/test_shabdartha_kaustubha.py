from ambuda.seed.dictionaries.shabdartha_kaustubha import create_entries


def test_create_entries():
    results = list(create_entries("pada", "some body"))
    assert len(results) == 1

    key, body = results[0]
    assert key == "pada"
    assert body == "<s>some body</s>"
