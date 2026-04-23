#!/usr/bin/env python3

from __future__ import annotations

import sys
import time
from collections import deque
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse
from urllib.request import Request, urlopen


BASE_URL = "https://toptica.github.io/python-lasersdk/"
OUTPUT_DIR = Path("toptica.github.io/python-lasersdk")
ALLOWED_HOST = "toptica.github.io"
ALLOWED_PREFIX = "/python-lasersdk/"


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        if tag == "a":
            href = attrs_dict.get("href")
            if href:
                self.links.add(href)
        elif tag in {"link", "script", "img", "source"}:
            for key in ("href", "src", "srcset"):
                value = attrs_dict.get(key)
                if value:
                    if key == "srcset":
                        for item in value.split(","):
                            part = item.strip().split(" ")[0]
                            if part:
                                self.links.add(part)
                    else:
                        self.links.add(value)


def normalize(url: str) -> str | None:
    full = urldefrag(url)[0]
    parsed = urlparse(full)

    if parsed.scheme and parsed.scheme not in {"http", "https"}:
        return None

    if not parsed.netloc:
        full = urljoin(BASE_URL, full)
        parsed = urlparse(full)

    if parsed.netloc != ALLOWED_HOST:
        return None

    if not parsed.path.startswith(ALLOWED_PREFIX):
        return None

    return full


def local_path(url: str) -> Path:
    parsed = urlparse(url)
    rel = parsed.path.lstrip("/")
    path = Path(rel)
    if path.suffix:
        return Path(path)
    return Path(path) / "index.html"


def fetch(url: str) -> tuple[bytes, str]:
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urlopen(req) as resp:
                content = resp.read()
                content_type = resp.headers.get_content_type()
            return content, content_type
        except Exception as exc:
            last_error = exc
            time.sleep(0.5 * (attempt + 1))
    assert last_error is not None
    raise last_error


def should_parse(content_type: str, target: Path) -> bool:
    return content_type == "text/html" or target.suffix in {"", ".html"}


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    queue: deque[str] = deque([BASE_URL])
    seen: set[str] = set()

    while queue:
        url = queue.popleft()
        if url in seen:
            continue
        seen.add(url)

        try:
            body, content_type = fetch(url)
        except Exception as exc:
            print(f"failed: {url} -> {exc}", file=sys.stderr)
            continue

        target = OUTPUT_DIR.parent / local_path(url)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
        print(f"saved {url} -> {target}")

        if should_parse(content_type, target):
            parser = LinkParser()
            try:
                parser.feed(body.decode("utf-8", errors="ignore"))
            except Exception:
                continue
            for link in parser.links:
                normalized = normalize(urljoin(url, link))
                if normalized and normalized not in seen:
                    queue.append(normalized)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
