"""Image handling and caching."""

import base64
import mimetypes
from dataclasses import dataclass
from pathlib import Path

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
MAX_IMAGE_SIZE = 20 * 1024 * 1024  # 20MB


@dataclass
class CachedImage:
    """Image data cached immediately on detection."""
    name: str
    data_url: str


def is_image_path(text: str) -> Path | None:
    """Check if text is a valid image file path."""
    text = text.strip().strip("'\"")
    if not text:
        return None
    path = Path(text).expanduser()
    if path.exists() and path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
        return path
    return None


def encode_image_to_base64(path: Path) -> tuple[str, str] | None:
    """Encode image file to base64 data URL."""
    try:
        if path.stat().st_size > MAX_IMAGE_SIZE:
            return None
        mime_type, _ = mimetypes.guess_type(str(path))
        if not mime_type or not mime_type.startswith("image/"):
            mime_type = "image/png"
        b64 = base64.b64encode(path.read_bytes()).decode()
        return f"data:{mime_type};base64,{b64}", mime_type
    except Exception:
        return None


def cache_image_immediately(path: Path) -> CachedImage | None:
    """Read and cache image data immediately."""
    result = encode_image_to_base64(path)
    if result:
        return CachedImage(name=path.name, data_url=result[0])
    return None


def create_image_message_from_cache(text: str, images: list[CachedImage]) -> dict:
    """Create a multi-part message from cached image data."""
    content = []
    if text:
        content.append({"type": "text", "text": text})
    for img in images:
        content.append({"type": "image_url", "image_url": {"url": img.data_url}})
    return {"role": "user", "content": content}
