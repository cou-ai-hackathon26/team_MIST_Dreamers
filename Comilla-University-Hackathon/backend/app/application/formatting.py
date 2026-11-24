"""Pure text helpers: the SMS checklist (SRS 3.2) and the spoken-answer length limit (FR-AGT-08)."""

from app.domain.entities import Checklist, Service
from app.domain.policies import MAX_SMS_CHARS, MAX_SPEECH_WORDS, MAX_VOICE_SENTENCES

ELLIPSIS = "…"
_SENTENCE_ENDS = ("।", "?", "!", ".")
_TRAILING_PUNCT = ",;:।-– "

# Lines that may be shortened when the SMS is too long. Title and fee are never shortened.
_SHRINKABLE = ("who", "papers", "where", "source")


def _shorten(value: str) -> str:
    """Drops the last word and marks the cut with an ellipsis. Returns "" when nothing is left."""
    words = value.removesuffix(ELLIPSIS).split()
    if len(words) <= 1:
        return ""
    return " ".join(words[:-1]).rstrip(_TRAILING_PUNCT) + ELLIPSIS


def _render(service: Service, fields: dict[str, str]) -> str:
    lines = [f"এক কল: {service.sms_name}"]
    labels = {"who": "কারা", "papers": "লাগবে", "fee": "ফি", "where": "কোথায়", "source": "সূত্র"}
    for key, label in labels.items():
        if fields[key]:
            lines.append(f"{label}: {fields[key]}")
    return "\n".join(lines)


def format_sms(
    checklist: Checklist,
    service: Service,
    source: str | None = None,
    max_chars: int = MAX_SMS_CHARS,
) -> str:
    """Builds the SMS checklist in the fixed line order, shortened to at most `max_chars`.

    When too long, the longest shrinkable line loses words one at a time (marked with "…"),
    so lines are never cut mid-word and the title and fee always survive.
    """
    fields = {
        "who": checklist.who.strip(),
        "papers": ", ".join(p.strip() for p in checklist.papers if p.strip()),
        "fee": checklist.fee.strip(),
        "where": checklist.where.strip(),
        "source": (source or service.office_bn).strip(),
    }
    text = _render(service, fields)
    while len(text) > max_chars:
        candidates = [key for key in _SHRINKABLE if fields[key]]
        if not candidates:  # only title + fee left and still too long: hard cut as a last resort
            return text[: max_chars - 1] + ELLIPSIS
        longest = max(candidates, key=lambda key: len(fields[key]))
        fields[longest] = _shorten(fields[longest])
        text = _render(service, fields)
    return text


def trim_speech(text: str, max_words: int = MAX_SPEECH_WORDS) -> str:
    """Limits a spoken answer to `max_words`, preferring to stop at a sentence end.

    If the last complete sentence within the limit keeps at least half the words, cut there.
    Otherwise cut at the word limit and close the sentence with "।".
    """
    words = text.split()
    if len(words) <= max_words:
        return " ".join(words)
    kept = words[:max_words]
    for i in range(len(kept) - 1, -1, -1):
        if kept[i].endswith(_SENTENCE_ENDS):
            if i + 1 >= max_words // 2:
                return " ".join(kept[: i + 1])
            break
    return " ".join(kept).rstrip(_TRAILING_PUNCT) + "।"


def limit_sentences(text: str, max_sentences: int = MAX_VOICE_SENTENCES) -> str:
    """Keeps the first `max_sentences` sentences: a long phone answer is hard to follow."""
    words = text.split()
    sentences = 0
    for i, word in enumerate(words):
        if word.endswith(_SENTENCE_ENDS):
            sentences += 1
            if sentences == max_sentences:
                return " ".join(words[: i + 1])
    return " ".join(words)
