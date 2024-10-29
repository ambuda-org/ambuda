from ambuda.utils import diff


def test_split_graphemes():
    split = list("उत्क्रामन्तं")
    assert split == [
        "उ",
        "त",
        "्",
        "क",
        "्",
        "र",
        "ा",
        "म",
        "न",
        "्",
        "त",
        "ं",
    ]
    assert split[0] == "उ"
    assert split[0:2] == ["उ", "त"]

    # In contrast:
    split = diff._split_graphemes("उत्क्रामन्तं")
    assert split == [
        "उ",
        "त्क्रा",
        "म",
        "न्तं",
    ]


def test_create_markup():
    markup = diff._create_markup("ins", "test")
    assert markup == ("<ins>", "test", "</ins>")

    markup = diff._create_markup("del", "\n")
    assert markup == ('<del class="block">', "\n", "</del>")


def test_revision_diff():
    d = diff.revision_diff("वापि", "वापिं")
    assert d == "वा<del>पि</del><ins>पिं</ins>"

    d = diff.revision_diff("पिहित", "पिहितः")
    assert d == "पिहि<del>त</del><ins>तः</ins>"

    d = diff.revision_diff("नमस्ते", "नम॑स्ते")
    assert d == "न<del>म</del><ins>म॑</ins>स्ते"

    d = diff.revision_diff("वापि", "वापि\n")
    assert d == 'वापि<ins class="block">\n</ins>'

    d = diff.revision_diff("\r\nवापि", "वापि\r\n")
    assert d == '<del class="block">\r\n</del>वापि<ins class="block">\r\n</ins>'
