"""SHA-256-keyed LRU cache for extraction results.

Identical uploads (same bytes, same OCR-affecting settings) produce identical
results, so we hash the input and serve a stored response on a repeat, skipping
the expensive OCR + analysis work entirely. The cache is in-process and bounded
(LRU eviction); a multi-process or persistent deployment would swap this for a
shared store like Redis, but the interface would stay the same.
"""

import hashlib
import threading
from collections import OrderedDict
from typing import List, Optional

from app.models.extraction import ExtractionResponse


class ExtractionCache:
    def __init__(self, max_size: int = 128):
        self._max_size = max_size
        self._store: "OrderedDict[str, ExtractionResponse]" = OrderedDict()
        self._lock = threading.Lock()

    @staticmethod
    def key_for(contents: bytes, lang: str, steps: List[str]) -> str:
        h = hashlib.sha256()
        h.update(contents)
        h.update(b"\x00")
        h.update(lang.encode())
        h.update(b"\x00")
        h.update(",".join(steps).encode())
        return h.hexdigest()

    def get(self, key: str) -> Optional[ExtractionResponse]:
        with self._lock:
            if key not in self._store:
                return None
            self._store.move_to_end(key)
            return self._store[key]

    def set(self, key: str, value: ExtractionResponse) -> None:
        with self._lock:
            self._store[key] = value
            self._store.move_to_end(key)
            while len(self._store) > self._max_size:
                self._store.popitem(last=False)

    def __len__(self) -> int:
        with self._lock:
            return len(self._store)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()
