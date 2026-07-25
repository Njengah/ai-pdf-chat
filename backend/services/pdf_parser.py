from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader


@dataclass
class PageText:
    page: int
    text: str


def extract_text_from_pdf(source: Path | bytes | BytesIO) -> list[PageText]:
    """Extract plain text per page from a PDF file or bytes."""
    if isinstance(source, Path):
        reader = PdfReader(str(source))
    elif isinstance(source, bytes):
        reader = PdfReader(BytesIO(source))
    else:
        reader = PdfReader(source)

    pages: list[PageText] = []
    for index, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if text:
            pages.append(PageText(page=index, text=text))
    return pages


def page_count(source: Path | bytes) -> int:
    if isinstance(source, Path):
        reader = PdfReader(str(source))
    else:
        reader = PdfReader(BytesIO(source))
    return len(reader.pages)
