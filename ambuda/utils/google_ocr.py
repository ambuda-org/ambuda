# TODO:
# input: PDF by url or file path
# output: structured text for proofreading

# API example: https://cloud.google.com/vision/docs/fulltext-annotations
# Return format: https://cloud.google.com/vision/docs/reference/rest/v1/images/annotate#TextAnnotation
# Billing: https://console.cloud.google.com/billing/


import io
import json
from google.cloud import vision
from google.protobuf.json_format import MessageToDict
from google.cloud.vision_v1 import AnnotateImageResponse

import logging


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


def full_text_annotation(file_path):
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
    for page in document.pages:
        for block in page.blocks:
            for p in block.paragraphs:
                for w in p.words:
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
    return post_process("".join(buf))
