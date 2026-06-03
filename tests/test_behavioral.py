"""Offline tests for the judge's bias-control + parsing logic (no model call)."""

from atw.metrics.behavioral import _extract_json, _map_winner


def test_map_winner_no_swap():
    # not swapped: position 1 == arm A, position 2 == arm B
    assert _map_winner(1, swapped=False) == "A"
    assert _map_winner(2, swapped=False) == "B"
    assert _map_winner(0, swapped=False) == "tie"


def test_map_winner_swapped_inverts():
    # swapped: position 1 was actually arm B, position 2 was arm A
    assert _map_winner(1, swapped=True) == "B"
    assert _map_winner(2, swapped=True) == "A"
    assert _map_winner(0, swapped=True) == "tie"


def test_extract_json_from_noisy_text():
    assert _extract_json('Here: {"winner": 2, "reason": "ok"}') == {"winner": 2, "reason": "ok"}
    assert _extract_json("no json here") == {}
    assert _extract_json('{bad json}') == {}
