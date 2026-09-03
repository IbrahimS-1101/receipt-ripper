"""Validation and normalization for user-supplied images."""

from __future__ import annotations

from io import BytesIO
from typing import Any

from PIL import Image, UnidentifiedImageError

MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000

# Prevent decompression-bomb images from consuming unbounded memory.
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS


class UploadValidationError(ValueError):
    """Raised when an uploaded image is invalid or exceeds safe limits."""


def read_safe_image(uploaded_file: Any) -> Image.Image:
    raw = uploaded_file.getvalue()
    if len(raw) > MAX_IMAGE_BYTES:
        raise UploadValidationError("This image is larger than 10 MB.")

    try:
        # Verify the container first, then reopen and fully decode it.
        with Image.open(BytesIO(raw)) as candidate:
            candidate.verify()

        with Image.open(BytesIO(raw)) as candidate:
            width, height = candidate.size
            if width * height > MAX_IMAGE_PIXELS:
                raise UploadValidationError(
                    "This image has too many pixels to process safely."
                )
            candidate.load()
            # Return a detached, metadata-free image for the model request.
            return candidate.convert("RGB")
    except UploadValidationError:
        raise
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
        raise UploadValidationError(
            "This file is not a valid, safely readable image."
        ) from error
