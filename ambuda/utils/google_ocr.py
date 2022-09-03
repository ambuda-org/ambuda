# TODO:
# input: PDF by url or file path
# output: structured text for proofreading

# API example: https://cloud.google.com/vision/docs/fulltext-annotations
# Return format: https://cloud.google.com/vision/docs/reference/rest/v1/images/annotate#TextAnnotation
# Billing: https://console.cloud.google.com/billing/


import dataclass
import io
import json
import logging
from pathlib import Path

from google.cloud import vision
from google.protobuf.json_format import MessageToDict
from google.cloud.vision_v1 import AnnotateImageResponse


@dataclass
class OcrResponse:
    text_content: str
    # Lists of 5-tuples (x1, x2, y1, y2, text)
    bounding_boxes: list[tuple[int, int, int, int, str]]


def post_process(text: str) -> str:
    """Post process OCR text."""
    return (
        text
        # Danda and double danda
        .replace("||", "॥")
        .replace("|", "।")
        .replace("।।", "॥")
        # Remove curly quotes
        .replace("‘", "'")
        .replace("’", "'")
        .replace("“", '"')
        .replace("”", '"')
    )


def prepare_image(file_path):
    with io.open(file_path, "rb") as file_path:
        content = file_path.read()
    return vision.Image(content=content)


def run(file_path: Path) -> str:
    """Detects document features in the file located in Google Cloud
    Storage."""
    logging.debug("Starting full text annotation: {}".format(file_path))

    client = vision.ImageAnnotatorClient()
    image = prepare_image(file_path)

    # Disable the language hint. It produced identical Devanagari output while
    # making English noticeably worse.
    # context = vision.ImageContext(language_hints=['sa'])
    response = client.document_text_detection(image=image)  # , image_context=context)

    document = response.full_text_annotation

    # print("Writing as json")
    # with open("out.json", "w") as f:
    #     f.write(AnnotateImageResponse.to_json(response))

    buf = []
    boxes = []
    for page in document.pages:
        for block in page.blocks:
            for p in block.paragraphs:
                for w in p.words:
                    vertices = w.boundingBox.vertices
                    xs = [v["x"] for v in vertices]
                    ys = [v["y"] for v in vertices]
                    word = "".join(s.text for s in w.symbols)
                    boxes.append((min(xs), min(ys), max(xs), max(ys), word))

                    for s in w.symbols:
                        buf.append(s.text)
                        break_type = s.property.detected_break.type

                        # BreakType.SPACE
                        # BreakType.SURE_SPACE
                        # End of word.
                        if break_type in (1, 2):
                            buf.append(" ")

                        # BreakType.EOL_SURE_SPACE
                        # End of line.
                        if break_type == 3:
                            buf.append("\n")

                        # BreakType.HYPHEN:
                        # Hyphenated end-of-line.
                        elif break_type == 4:
                            buf.append("-\n")

                        # BreakType.LINE_BREAK
                        # Clean end of region.
                        elif break_type == 5:
                            buf.append("\n\n")

    text_content = post_process("".join(buf))
    return OcrResponse(text_content=text_content, bounding_boxes=bounding_boxes)
