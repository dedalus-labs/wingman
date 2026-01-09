"""Image handling and caching."""

import base64
import mimetypes
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlparse

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
MAX_IMAGE_SIZE = 20 * 1024 * 1024  # 20MB


@dataclass
class CachedImage:
    """Image data cached immediately on detection."""

    name: str
    data_url: str


def _normalize_path(text: str) -> list[str]:
    """Generate candidate paths from various terminal paste formats."""
    candidates = [text]

    # Handle file:// URLs (some apps paste these)
    if text.startswith("file://"):
        parsed = urlparse(text)
        # URL-decode the path (%20 -> space, etc.)
        decoded = unquote(parsed.path)
        candidates.append(decoded)

    # Handle backslash-escaped spaces (zsh/bash: /path/to\ file.png)
    if "\\ " in text:
        unescaped = text.replace("\\ ", " ")
        candidates.append(unescaped)

    # Handle URL-encoded paths without file:// prefix
    if "%" in text:
        candidates.append(unquote(text))

    return candidates


def is_image_path(text: str) -> Path | None:
    """Check if text is a valid image file path.

    Handles various terminal paste formats:
    - Plain paths: /path/to/image.png
    - Quoted paths: '/path/to/image.png' or "/path/to/image.png"
    - Backslash-escaped: /path/to\\ image.png (zsh/bash)
    - file:// URLs: file:///path/to%20image.png
    - macOS screenshots with narrow no-break space before AM/PM
    """
    # Strip whitespace and surrounding quotes
    text = text.strip().strip("'\"")
    if not text:
        return None

    # Quick check: does it look like it ends with an image extension?
    # (check before normalization for URL-encoded extensions like .png)
    text_lower = text.lower()
    has_image_ext = any(
        text_lower.endswith(ext) or f"{ext}%" in text_lower or ext in text_lower
        for ext in IMAGE_EXTENSIONS
    )
    if not has_image_ext:
        return None

    # Try each normalized candidate
    for candidate in _normalize_path(text):
        path = Path(candidate).expanduser()
        if path.exists() and path.is_file():
            return path

        # macOS screenshots use narrow no-break space (\u202f) before AM/PM
        # Terminals may strip this or replace with regular space, so try fixing it
        # Pattern handles both "10AM" and "10 AM" -> "10\u202fAM"
        fixed = re.sub(r"(\d)\s?(AM|PM)", "\\1\u202f\\2", candidate, flags=re.IGNORECASE)
        if fixed != candidate:
            path = Path(fixed).expanduser()
            if path.exists() and path.is_file():
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
