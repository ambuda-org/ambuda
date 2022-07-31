from pathlib import Path

from flask import current_app


def _get_image_filesystem_path(project_slug: str, page_slug: str) -> Path:
    """Get the location of the given image on disk."""
    image_dir = Path(current_app.config["UPLOAD_FOLDER"]) / project_slug
    return image_dir / (page_slug + ".jpg")
