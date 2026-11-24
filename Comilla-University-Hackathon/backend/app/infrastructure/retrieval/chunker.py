"""Cuts official documents into passages for search (FR-DATA-03).

Rules:
- split on "## " headings first, so a passage never mixes two unrelated topics by accident;
- small neighbouring sections of the same document are packed together (a 2-word section such as
  "## বাস্তবায়নকারী দপ্তর / সমাজসেবা অধিদপ্তর" is useless on its own);
- a section longer than `max_words` is cut on paragraph boundaries, and a paragraph that is still
  too long is cut into word windows with `overlap` words repeated;
- every piece of a long section starts with its heading again, so it still makes sense alone.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from app.infrastructure.retrieval.documents import SourceDocument

# The SRS first said about 300 words. Measured on our documents, Bangla averages about 2.2 e5 tokens
# per word, so 300 words is about 650 tokens and e5 reads only the first 512 (the rest is ignored
# when embedding). 160 words stays under the limit with room for the title.
DEFAULT_MAX_WORDS = 160
DEFAULT_OVERLAP = 40


@dataclass(frozen=True)
class Chunk:
    chunk_id: str  # "<service_id>-<nnn>", numbered per service
    service_id: str
    title: str
    source_url: str
    heading: str  # heading(s) of the section(s) inside, joined with " | "
    text: str

    @property
    def word_count(self) -> int:
        return len(self.text.split())


@dataclass(frozen=True)
class _Block:
    heading: str
    text: str  # starts with "## heading" when there is one
    words: int
    whole_section: bool  # False for a piece of a long section (never packed with others)


def split_sections(body: str) -> list[tuple[str, str]]:
    """(heading, text) pairs. Text before the first heading gets heading ""; empty sections are dropped."""
    sections: list[tuple[str, list[str]]] = [("", [])]
    for line in body.splitlines():
        if line.startswith("## "):
            sections.append((line[3:].strip(), []))
        else:
            sections[-1][1].append(line)
    result = []
    for heading, lines in sections:
        text = "\n".join(lines).strip()
        if text:
            result.append((heading, text))
        elif heading:  # a heading with no text of its own still says something
            result.append((heading, ""))
    return result


def _paragraphs(text: str) -> list[str]:
    return [p.strip() for p in text.split("\n\n") if p.strip()]


def _word_windows(words: list[str], max_words: int, overlap: int) -> list[str]:
    step = max(1, max_words - overlap)
    pieces = []
    for start in range(0, len(words), step):
        pieces.append(" ".join(words[start : start + max_words]))
        if start + max_words >= len(words):
            break
    return pieces


def split_long_text(text: str, max_words: int, overlap: int) -> list[str]:
    """Pieces of at most `max_words` words; each piece after the first repeats `overlap` words."""
    pieces: list[str] = []
    current: list[str] = []  # paragraphs of the piece being built (may start with an overlap tail)
    count = 0
    has_new_text = False  # False while `current` holds only the tail repeated from the last piece

    def start_after(piece: str) -> None:
        nonlocal current, count, has_new_text
        tail = " ".join(piece.split()[-overlap:]) if overlap else ""
        current, count, has_new_text = ([tail] if tail else []), len(tail.split()), False

    for para in _paragraphs(text):
        words = para.split()
        if len(words) > max_words:  # one huge paragraph: cut it into word windows
            if has_new_text:
                pieces.append("\n\n".join(current))
            pieces.extend(_word_windows(words, max_words, overlap))
            start_after(pieces[-1])
            continue
        if has_new_text and count + len(words) > max_words:
            pieces.append("\n\n".join(current))
            start_after(pieces[-1])
        if count + len(words) > max_words:  # only the tail is there and it does not fit: drop it
            current, count = [], 0
        current.append(para)
        count += len(words)
        has_new_text = True
    if has_new_text:
        pieces.append("\n\n".join(current))
    return pieces


def _blocks(body: str, max_words: int, overlap: int) -> list[_Block]:
    blocks = []
    for heading, text in split_sections(body):
        head = f"## {heading}" if heading else ""
        head_words = len(head.split())
        if len(text.split()) + head_words <= max_words:
            full = f"{head}\n\n{text}".strip()
            blocks.append(_Block(heading, full, len(full.split()), whole_section=True))
            continue
        for piece in split_long_text(text, max_words - head_words, overlap):
            full = f"{head}\n\n{piece}".strip()
            blocks.append(_Block(heading, full, len(full.split()), whole_section=False))
    return blocks


def _pack(blocks: list[_Block], max_words: int) -> list[list[_Block]]:
    """Greedily puts neighbouring whole sections together while they fit."""
    groups: list[list[_Block]] = []
    for block in blocks:
        last = groups[-1] if groups else None
        if (
            last is not None
            and block.whole_section
            and all(b.whole_section for b in last)
            and sum(b.words for b in last) + block.words <= max_words
        ):
            last.append(block)
        else:
            groups.append([block])
    return groups


def chunk_documents(
    docs: Iterable[SourceDocument],
    max_words: int = DEFAULT_MAX_WORDS,
    overlap: int = DEFAULT_OVERLAP,
) -> list[Chunk]:
    """All passages of all documents. Documents are taken in path order so ids are stable."""
    if not 0 <= overlap < max_words:
        raise ValueError("overlap must be >= 0 and smaller than max_words")
    counters: dict[str, int] = {}
    chunks = []
    for doc in sorted(docs, key=lambda d: (d.service_id, d.path.as_posix())):
        for group in _pack(_blocks(doc.body, max_words, overlap), max_words):
            n = counters.get(doc.service_id, 0) + 1
            counters[doc.service_id] = n
            headings = [b.heading for b in group if b.heading]
            chunks.append(
                Chunk(
                    chunk_id=f"{doc.service_id}-{n:03d}",
                    service_id=doc.service_id,
                    title=doc.title,
                    source_url=doc.source_url,
                    heading=" | ".join(dict.fromkeys(headings)),
                    text="\n\n".join(b.text for b in group),
                )
            )
    return chunks
