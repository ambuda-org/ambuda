from ambuda.utils.google_ocr import post_process


def test_post_process():
    text = """हरिः |
हरिः ||
हरिः ।।
“Hello world”
‘Hello world’"""
    assert (
        post_process(text)
        == """हरिः ।
हरिः ॥
हरिः ॥
"Hello world"
'Hello world'"""
    )
