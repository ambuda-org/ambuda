from ambuda.utils import proofing_utils as pu


def test_create_plain_text_block():
    lines = ["An", "exam-", "ple", "paragraph."]
    pu.create_plain_text_block(lines) == "An example paragraph."


def test_create_xml_block():
    lines = ["An", "exam-", "ple", "paragraph."]
    pu.create_plain_text_block(lines) == "<p>An example paragraph.</p>"
