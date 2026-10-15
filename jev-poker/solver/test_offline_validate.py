"""G7 tests: fixed replay, street prefixes and AB report shape."""

from solver.offline_validate import validate_hands


def hand(history, board=("7h", "3c", "2d", "9s", "Tc")):
    return {"match": "m", "cards": ["As", "Kd"], "board": list(board), "history": history}


def test_replay_never_uses_future_cards() -> None:
    h = hand([
        {"id": "hero", "type": 1, "street": "preflop", "add": 0, "blind": False},
        {"id": "hero", "type": 2, "street": "flop", "add": 0, "blind": False},
        {"id": "hero", "type": 2, "street": "turn", "add": 0, "blind": False},
        {"id": "hero", "type": 2, "street": "river", "add": 0, "blind": False},
    ])
    report = validate_hands([h], trials=100, seed=1)
    rows = report["rows"]
    assert [r["board_cards"] for r in rows] == [0, 3, 4, 5]


def test_report_has_per_street_and_precision() -> None:
    h = hand([
        {"id": "hero", "type": 2, "street": "preflop", "add": 0, "blind": False},
        {"id": "hero", "type": 2, "street": "flop", "add": 0, "blind": False},
    ])
    report = validate_hands([h], trials=100, seed=2)
    assert report["decisions"] == 2
    assert set(report["by_street"]) == {"preflop", "flop", "turn", "river"}
    assert report["assumptions"]["precision"] == "assumed_stack_and_scenario_approximate"
    assert all(isinstance(r["agreed"], bool) for r in report["rows"])
