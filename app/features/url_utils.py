from __future__ import annotations

import re
from urllib.parse import urlparse

URL_PATTERN = re.compile(
    r"https?://[^\s<>\"']+|www\.[^\s<>\"']+",
    re.IGNORECASE,
)


def extract_urls(content: str) -> tuple[str, ...]:
    if not content:
        return ()
    seen: set[str] = set()
    urls: list[str] = []
    for match in URL_PATTERN.finditer(content):
        raw = match.group(0).rstrip(".,);]")
        if raw not in seen:
            seen.add(raw)
            urls.append(raw)
    return tuple(urls)


def extract_domain(url: str) -> str | None:
    normalized = url if "://" in url else f"https://{url}"
    try:
        parsed = urlparse(normalized)
        host = parsed.netloc or parsed.path.split("/")[0]
        return host.lower().lstrip("www.") or None
    except ValueError:
        return None
