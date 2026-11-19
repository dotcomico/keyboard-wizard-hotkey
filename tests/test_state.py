"""Unit tests for StateMachine, the IDLE/BUSY guard that drops overlapping presses."""

from __future__ import annotations

import threading

from kbwizard.app.state import State, StateMachine


def test_starts_idle():
    assert StateMachine().state is State.IDLE


def test_second_begin_is_refused_until_reset():
    sm = StateMachine()
    assert sm.try_begin() is True
    assert sm.try_begin() is False
    sm.reset_to_idle()
    assert sm.try_begin() is True


def test_exactly_one_of_many_concurrent_begins_wins():
    sm = StateMachine()
    barrier = threading.Barrier(50)
    wins = []

    def worker():
        barrier.wait()
        if sm.try_begin():
            wins.append(1)

    threads = [threading.Thread(target=worker) for _ in range(50)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(wins) == 1
