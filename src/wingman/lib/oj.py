"""Fast JSON with stdlib semantics."""

import orjson

OPT_INDENT = orjson.OPT_INDENT_2


def dumps(obj: object, *, indent: int | None = None) -> str:
    """Serialize to JSON string (not bytes)."""
    opts = OPT_INDENT if indent else 0
    return orjson.dumps(obj, option=opts).decode("utf-8")


def loads(s: str | bytes) -> object:
    """Deserialize JSON string or bytes."""
    return orjson.loads(s)
