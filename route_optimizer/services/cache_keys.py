from __future__ import annotations

from hashlib import sha256


def stable_cache_key(prefix: str, value: str) -> str:
    digest = sha256(value.encode("utf-8")).hexdigest()
    return f"{prefix}:{digest}"
