"""Busy guard that drops hotkey presses while a conversion is running."""

from __future__ import annotations

import threading
from enum import Enum


class State(Enum):
    """Whether a conversion is in progress."""
    IDLE = "idle"
    BUSY = "busy"


class StateMachine:
    """Thread-safe IDLE/BUSY guard.

    Callers act on the result of ``try_begin`` rather than reading ``state``
    and deciding separately, which would race.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state = State.IDLE

    @property
    def state(self) -> State:
        with self._lock:
            return self._state

    def try_begin(self) -> bool:
        """Move from IDLE to BUSY; return False if a conversion is already running."""
        with self._lock:
            if self._state is State.IDLE:
                self._state = State.BUSY
                return True
            return False

    def reset_to_idle(self) -> None:
        """Return to IDLE; called from ``finally`` so an error can't leave the guard BUSY."""
        with self._lock:
            self._state = State.IDLE
