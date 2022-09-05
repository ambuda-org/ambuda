from ambuda.utils import google_ocr


def test_post_process():
    text = """हरिः |
हरिः ||
हरिः ।।
“Hello world”
‘Hello world’"""
    actual = google_ocr.post_process(text)
    assert (
        actual
        == """हरिः ।
हरिः ॥
हरिः ॥
"Hello world"
'Hello world'"""
    )


def test_serialize_bounding_boxes():
    boxes = [
        (0, 0, 100, 20, "word"),
        (120, 25, 300, 45, "another"),
    ]
    blob = "0\t0\t100\t20\tword\n120\t25\t300\t45\tanother"
    assert google_ocr.serialize_bounding_boxes(boxes) == blob
