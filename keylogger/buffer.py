"""
Buffer module for the keylogger.
Provides thread-safe keystroke buffering with rate limiting.
"""

import threading
from typing import Optional


class KeyBuffer:
    """Thread-safe buffer for keystrokes with rate limiting."""

    def __init__(self, max_chars_per_interval: int = 10000) -> None:
        self._buffer: list[str] = []
        self._lock = threading.RLock()
        self._max_chars = max_chars_per_interval
        self._char_count = 0

    def add(self, text: str) -> bool:
        """Add text to buffer. Returns True if added, False if rate limited."""
        with self._lock:
            if self._char_count + len(text) > self._max_chars:
                return False
            self._buffer.append(text)
            self._char_count += len(text)
            return True

    def get_and_clear(self) -> str:
        """Get all buffered text and clear buffer."""
        with self._lock:
            text = "".join(self._buffer)
            self._buffer.clear()
            self._char_count = 0
            return text

    def __len__(self) -> int:
        with self._lock:
            return self._char_count

    def peek(self) -> str:
        """Get buffered text without clearing."""
        with self._lock:
            return "".join(self._buffer)

    def clear(self) -> None:
        """Clear the buffer without returning content."""
        with self._lock:
            self._buffer.clear()
            self._char_count = 0