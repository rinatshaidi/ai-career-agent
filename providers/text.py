from __future__ import annotations

from html import unescape
from html.parser import HTMLParser


class _TextExtractor(HTMLParser):
    _BLOCK_TAGS = {
        "br",
        "div",
        "h1",
        "h2",
        "h3",
        "h4",
        "li",
        "p",
        "section",
        "ul",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def html_to_text(value: str) -> str:
    """Convert feed HTML into compact plain text suitable for AI analysis."""
    parser = _TextExtractor()
    parser.feed(value)
    parser.close()
    lines = (" ".join(line.split()) for line in unescape("".join(parser.parts)).splitlines())
    return "\n".join(line for line in lines if line)
