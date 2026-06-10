"""TD3 (passport) Machine-Readable-Zone parsing and check-digit validation.

The MRZ is the two 44-character lines at the bottom of a passport. Each key
field carries an ICAO 9303 check digit (weighted 7-3-1, mod 10), plus a final
composite check digit over the second line. This validates all of them and
exposes the parsed fields — a fully specified algorithm implemented from
scratch, independent of how the characters were recognized.
"""

from typing import Dict, Optional

_WEIGHTS = (7, 3, 1)


def _char_value(c: str) -> int:
    if c.isdigit():
        return int(c)
    if "A" <= c <= "Z":
        return ord(c) - ord("A") + 10
    return 0  # filler '<' and anything unexpected


def check_digit(s: str) -> int:
    return sum(_char_value(c) * _WEIGHTS[i % 3] for i, c in enumerate(s)) % 10


def _digit(c: str) -> Optional[int]:
    return int(c) if c.isdigit() else None


def parse_td3(line1: str, line2: str) -> Dict:
    line1 = line1.ljust(44, "<")[:44]
    line2 = line2.ljust(44, "<")[:44]

    surname, _, given = line1[5:44].partition("<<")
    fields = {
        "document_type": line1[0],
        "issuing_country": line1[2:5],
        "surname": surname.replace("<", " ").strip(),
        "given_names": given.replace("<", " ").strip(),
        "passport_number": line2[0:9].rstrip("<"),
        "nationality": line2[10:13],
        "date_of_birth": line2[13:19],
        "sex": line2[20],
        "expiration_date": line2[21:27],
    }

    composite_src = line2[0:10] + line2[13:20] + line2[21:43]
    checks = {
        "passport_number": check_digit(line2[0:9]) == _digit(line2[9]),
        "date_of_birth": check_digit(line2[13:19]) == _digit(line2[19]),
        "expiration_date": check_digit(line2[21:27]) == _digit(line2[27]),
        "composite": check_digit(composite_src) == _digit(line2[43]),
    }
    return {"fields": fields, "checks": checks, "all_valid": all(checks.values())}


def detect_mrz_lines(text: str):
    """Find the two MRZ lines in OCR text. Returns (line1, line2) or None."""
    candidates = []
    for ln in text.splitlines():
        s = ln.strip().replace(" ", "")
        if len(s) >= 28 and s.count("<") >= 3:
            candidates.append(s)
    if len(candidates) >= 2:
        return candidates[-2], candidates[-1]
    return None
