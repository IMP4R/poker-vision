"""Shadow replay tests, explicitly no-click."""

from solver.shadow_replay import shadow_replay


def test_shadow_replay_keeps_street_prefixes() -> None:
    hand = {
        "match": "m", "cards": ["As", "Kd"],
        "board": ["7h", "3c", "2d", "9s", "Tc"],
        "history": [
            {"id": "hero", "type": 2, "street": "preflop", "add": 0, "blind": False},
            {"id": "hero", "type": 2, "street": "flop", "add": 0, "blind": False},
            {"id": "hero", "type": 2, "street": "turn", "add": 0, "blind": False},
            {"id": "hero", "type": 2, "street": "river", "add": 0, "blind": False},
        ],
    }
    report = shadow_replay([hand], trials=80, seed=3)
    assert report["decisions"] == 4
    assert report["precision"] == "shadow_replay_scenario_approximate"
    assert all("line_ev" in row for row in report["rows"])


def test_shadow_replay_is_not_a_live_runner() -> None:
    report = shadow_replay([], trials=10)
    assert report["decisions"] == 0
    assert report["rows"] == []
