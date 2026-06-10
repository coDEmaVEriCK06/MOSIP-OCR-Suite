"""Layout-aware spatial field extraction.

OCR gives us words with bounding boxes. This module reconstructs text lines
geometrically (clustering words by vertical overlap, ordering left-to-right)
and associates labels with their values *by position* — handling both inline
layouts ("Name: X" on one line) and stacked layouts (label on one line, value
on the line below, as real PAN/passport cards are printed).

This is the line that separates document understanding from regex on a
flattened blob: on an identity card, geometry carries meaning, so we use it.
Pattern-based fields (ID numbers, dates) are still better handled by regex on
the line text — a distinctive format is the right signal there.
"""

from typing import List, Optional, Sequence

from app.models.common import BoundingBox
from app.models.extraction import Word


class Line:
    """A reconstructed text line: words sharing vertical extent, ordered by x."""

    def __init__(self, words: List[Word]):
        self.words: List[Word] = sorted(words, key=lambda w: w.bbox.x)
        self.page: int = words[0].page
        self.top: int = min(w.bbox.y for w in words)
        self.bottom: int = max(w.bbox.y + w.bbox.height for w in words)

    @property
    def text(self) -> str:
        return " ".join(w.text for w in self.words)

    @property
    def y_center(self) -> float:
        return (self.top + self.bottom) / 2


def reconstruct_lines(words: Sequence[Word]) -> List[Line]:
    """Group words into lines by vertical overlap, per page, top-to-bottom."""
    lines: List[Line] = []
    for page in sorted({w.page for w in words}):
        page_words = sorted(
            [w for w in words if w.page == page], key=lambda w: w.bbox.y
        )
        buckets: List[List[Word]] = []
        for w in page_words:
            wc = w.bbox.y + w.bbox.height / 2
            placed = False
            for b in buckets:
                top = min(x.bbox.y for x in b)
                bottom = max(x.bbox.y + x.bbox.height for x in b)
                center = (top + bottom) / 2
                tol = max(w.bbox.height, bottom - top) * 0.6
                if abs(wc - center) <= tol:
                    b.append(w)
                    placed = True
                    break
            if not placed:
                buckets.append([w])
        page_lines = sorted((Line(b) for b in buckets), key=lambda ln: ln.top)
        lines.extend(page_lines)
    return lines


def _norm(s: str) -> str:
    return "".join(ch for ch in s.lower() if ch.isalnum())


def _has_alnum(s: str) -> bool:
    return any(ch.isalnum() for ch in s)


def value_words_for_label(
    lines: List[Line],
    label_variants: Sequence[str],
    max_label_words: int = 3,
) -> Optional[List[Word]]:
    """Find a label, then return the value's source Word objects (with geometry).

    Tries inline first (value on the same line, right of the label), then
    stacked (value on the next line, horizontally aligned under the label).
    Returns the words that make up the value, so callers keep both the text
    and the exact bounding boxes it came from.
    """
    variants = {_norm(v) for v in label_variants}
    for i, line in enumerate(lines):
        toks = line.words
        # Match the label only at the START of a line, longest phrase first.
        # This stops "name" from matching the "Name" inside "Father's Name".
        for span in range(min(max_label_words, len(toks)), 0, -1):
            phrase = _norm("".join(t.text for t in toks[:span]))
            if phrase not in variants:
                continue
            label_words = toks[:span]
            label_x_start = min(t.bbox.x for t in label_words)
            label_x_end = max(t.bbox.x + t.bbox.width for t in label_words)

            # Inline: words on the same line, to the right of the label.
            right = [
                t for t in toks[span:]
                if t.bbox.x >= label_x_end - 3 and _has_alnum(t.text)
            ]
            if right:
                return right

            # Stacked: next line, horizontally aligned under the label.
            if i + 1 < len(lines):
                below = lines[i + 1]
                aligned = [
                    t for t in below.words
                    if t.bbox.x + t.bbox.width >= label_x_start - 8 and _has_alnum(t.text)
                ]
                if aligned:
                    return aligned
            break  # label matched at start; move to the next line
    return None


def find_label_value(
    lines: List[Line],
    label_variants: Sequence[str],
    max_label_words: int = 3,
) -> Optional[str]:
    """Text-only convenience wrapper over value_words_for_label."""
    words = value_words_for_label(lines, label_variants, max_label_words)
    if not words:
        return None
    value = " ".join(w.text for w in words).strip(": ").strip()
    return value or None


def locate_value_boxes(value: str, words: Sequence[Word]) -> List[BoundingBox]:
    """Best-effort reverse lookup: which word boxes make up this value.

    Used for pattern-extracted fields (ID numbers, dates, gender) where the
    value came from regex on the text blob rather than from specific words.
    Matches whole OCR tokens (length >= 3) whose normalized text appears in
    the normalized value, which handles spaced IDs like "2341 2341 2346".
    """
    nv = _norm(value)
    if not nv:
        return []
    return [w.bbox for w in words if len(_norm(w.text)) >= 3 and _norm(w.text) in nv]
