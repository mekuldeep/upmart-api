import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException, UploadFile
from PIL import Image

from utils.file_security import resolve_upload_path, save_validated_image


def image_bytes(image_format="PNG"):
    buffer = io.BytesIO()
    Image.new("RGB", (2, 2), color="red").save(buffer, format=image_format)
    return buffer.getvalue()


class UploadSecurityTests(unittest.TestCase):
    def test_resolve_upload_path_rejects_parent_traversal(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(HTTPException) as context:
                resolve_upload_path(Path(directory), "../.env")
            self.assertEqual(context.exception.status_code, 404)

    def test_resolve_upload_path_allows_a_file_inside_uploads(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            expected = base / "products" / "photo.png"
            self.assertEqual(
                resolve_upload_path(base, "products/photo.png"),
                expected.resolve(),
            )

    def test_save_validated_image_uses_detected_format(self):
        with tempfile.TemporaryDirectory() as directory:
            upload = UploadFile(
                filename="misleading.jpg",
                file=io.BytesIO(image_bytes("PNG")),
                headers={"content-type": "image/png"},
            )
            filename = save_validated_image(upload, Path(directory))
            self.assertTrue(filename.endswith(".png"))
            self.assertTrue((Path(directory) / filename).is_file())

    def test_save_validated_image_rejects_non_image_content(self):
        with tempfile.TemporaryDirectory() as directory:
            upload = UploadFile(
                filename="payload.png",
                file=io.BytesIO(b"not an image"),
                headers={"content-type": "image/png"},
            )
            with self.assertRaises(HTTPException) as context:
                save_validated_image(upload, Path(directory))
            self.assertEqual(context.exception.status_code, 400)

    def test_save_validated_image_enforces_size_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            upload = UploadFile(
                filename="large.png",
                file=io.BytesIO(image_bytes("PNG")),
                headers={"content-type": "image/png"},
            )
            with patch.dict(os.environ, {"MAX_IMAGE_SIZE_BYTES": "1"}):
                with self.assertRaises(HTTPException) as context:
                    save_validated_image(upload, Path(directory))
            self.assertEqual(context.exception.status_code, 413)


if __name__ == "__main__":
    unittest.main()
