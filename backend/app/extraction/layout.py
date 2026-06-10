"""Layout-aware spatial field extraction.

OCR gives us words with bounding boxes. This module reconstructs text lines
geometrically (clustering words by vertical overlap, ordering left-to-right)
and associates labels with their values *by position* — handling both inline
layouts ("Name: X" on one line) and stacked layouts (label on one line, value
on the line below, as real PAN/passport cards are printed).

This is the line that separates document understanding from regex on a
flattened blob: on an identity card, geometry carries meaning, so we use it.
Pattern-based fields (ID numbers, dates) are still better handled by regex on
the line text — a distinctive format is the right signal there — so this
module deliberately covers only the label-anchored fields (name, father's
name, etc.) where position is what disambiguates the value.
"""

from typing import List, Optional, Sequence

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


_NOISE_TOKENS = {"", ":", "-", "|", "/"}


def _clean_value(tokens: List[str]) -> Optional[str]:
    parts = []
    for t in tokens:
        t = t.strip().lstrip(":").strip()
        if t and t not in _NOISE_TOKENS:
            parts.append(t)
    value = " ".join(parts).strip()
    return value or None


def find_label_value(
    lines: List[Line],
    label_variants: Sequence[str],
    max_label_words: int = 3,
) -> Optional[str]:
    """Find a label by text, then return its value to the right or just below.

    Tries inline first (value on the same line, right of the label), then
    stacked (value on the next line, horizontally aligned under the label).
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
            right = [t for t in toks[span:] if t.bbox.x >= label_x_end - 3]
            value = _clean_value([t.text for t in right])
            if value:
                return value

            # Stacked: next line, horizontally aligned under the label.
            if i + 1 < len(lines):
                below = lines[i + 1]
                aligned = [
                    t for t in below.words if t.bbox.x + t.bbox.width >= label_x_start - 8
                ]
                value = _clean_value([t.text for t in aligned])
                if value:
                    return value
            break  # label matched at start; move to the next line
    return None
