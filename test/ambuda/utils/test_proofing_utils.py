from ambuda.utils import proofing_utils as pu


def test_iter_blocks():
    blobs = [
        "\n".join(
            [
                "Here",
                "  are",
                " ",
                "three  ",
                "blocks",
            ]
        ),
        "\n".join(["   over", "three", "", "", "pages!"]),
    ]
    assert list(pu.iter_blocks(blobs)) == [
        ["Here", "are"],
        ["three", "blocks", "over", "three"],
        ["pages!"],
    ]


def test_create_plain_text_block():
    lines = ["An", "exam-", "ple", "paragraph."]
    pu.create_plain_text_block(lines) == "An example paragraph."


def test_create_xml_block():
    lines = ["An", "exam-", "ple", "paragraph."]
    pu.create_plain_text_block(lines) == "<p>An example paragraph.</p>"
