import io
import os
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError


DEFAULT_MAX_IMAGE_SIZE = 10 * 1024 * 1024
ALLOWED_IMAGE_FORMATS = {
    "JPEG": "jpg",
    "PNG": "png",
    "WEBP": "webp",
    "GIF": "gif",
}


def resolve_upload_path(upload_root: Path, subpath: str) -> Path:
    """Resolve a public upload path without allowing it to escape upload_root."""
    root = upload_root.resolve()
    candidate = (root / subpath).resolve()
    if candidate == root or root not in candidate.parents:
        raise HTTPException(status_code=404, detail="File not found")
    return candidate


def save_validated_image(
    upload: UploadFile,
    destination: Path,
    filename_stem: str | None = None,
) -> str:
    """Validate an image by size and decoded content, then save it safely."""
    max_size = int(os.getenv("MAX_IMAGE_SIZE_BYTES", str(DEFAULT_MAX_IMAGE_SIZE)))
    content = upload.file.read(max_size + 1)
    if len(content) > max_size:
        raise HTTPException(status_code=413, detail="Image is too large")
    if not content:
        raise HTTPException(status_code=400, detail="Image is empty")

    try:
        with Image.open(io.BytesIO(content)) as image:
            image.verify()
            image_format = (image.format or "").upper()
    except (UnidentifiedImageError, OSError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid image file") from None

    extension = ALLOWED_IMAGE_FORMATS.get(image_format)
    if not extension:
        raise HTTPException(status_code=400, detail="Unsupported image format")

    destination.mkdir(parents=True, exist_ok=True)
    stem = filename_stem or str(uuid.uuid4())
    filename = f"{stem}.{extension}"
    target = (destination / filename).resolve()
    if destination.resolve() not in target.parents:
        raise HTTPException(status_code=400, detail="Invalid image filename")
    target.write_bytes(content)
    return filename
