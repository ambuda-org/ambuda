import os
import logging
import tempfile
import zipfile
import json

from sarvamai import SarvamAI

from ambuda import database as db
from ambuda.utils import s3
from ambuda.utils.s3 import S3Path
from ambuda.utils.google_ocr import OcrResponse, post_process

# Todo: For now this is hacked together for Sarvam. Ideally we would download the image locally then 
# upload to Sarvam since that is what the API requires
def get_image_bytes(
    page: db.Page, s3_bucket: str | None, cloudfront_base_url: str | None
) -> bytes | None:    
    s3_bucket = 'data'
    if s3.is_local() and s3_bucket:
        image = S3Path(bucket='/app/data', key=f"assets/1.jpg")
        return image.read_bytes()
    # Todo: needs to be implemented
    elif cloudfront_base_url:
        return None
    else:
        return None

# Todo: maybe down the line we can implement an OCR base class with different adapters for Google vs 
# Sarvam for better code reuse
def run(
    page: db.Page, s3_bucket: str | None, cloudfront_base_url: str | None
) -> OcrResponse:
    """Run Sarvam OCR over the given image.

    :return: an OCR response containing the image's text content and
        bounding boxes.
    """
    logging.debug(f"Starting full text annotation for page {page.id}")
    client = SarvamAI(
        api_subscription_key=os.getenv("SARVAM_API_KEY")
    )
    image_bytes = get_image_bytes(page, s3_bucket, cloudfront_base_url)
    if not image_bytes:
        return OcrResponse(text_content="", bounding_boxes=[])
    
    buf = []
    bounding_boxes = []
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp_input_zip:
        tmp_input_zip_path = tmp_input_zip.name
        # Use writestr to put the bytes directly into the zip without an intermediate file
        with zipfile.ZipFile(tmp_input_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("image.jpg", image_bytes)
    
        job = client.document_intelligence.create_job(
            output_format='md'
        )
        job.upload_file(tmp_input_zip_path)
        job.start()
        job.wait_until_complete()
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp_output_zip:
            job.download_output(tmp_output_zip.name)        
            with zipfile.ZipFile(tmp_output_zip.name, 'r') as output_zip:
                metadata_path = next(filter(lambda x: x.endswith('.json'), output_zip.namelist()), None)
                if metadata_path:
                    with output_zip.open(metadata_path) as f:
                        data = json.load(f)
                        sorted_blocks = sorted(data.get('blocks', []), key=lambda x: x['block_id'])

                        for block in sorted_blocks:
                            text = block['text']
                            coordinates = block['coordinates']
                            x1, y1, x2, y2 = coordinates
                            text = post_process(text).strip()
                            buf.append(text)
                            bounding_boxes.append((x1, y1, x2, y2, text))

    text_content = post_process("\n".join(buf)).strip()
    return OcrResponse(text_content=text_content, bounding_boxes=bounding_boxes)