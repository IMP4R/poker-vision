"""Integration tests for read-only protocol-to-policy bridge."""

from solver.decision_bridge import advise_snapshot
from solver.observation import ObservationSnapshot


def snap(**changes):
    data = dict(
        street="flop", board=("Ah", "Kd", "7c"), pot=1000, to_call=300,
        hero_stack=5000, allowed_actions=("fold", "call", "raise"),
        min_raise=600, gross_contributions=1000,
    )
    data.update(changes)
    return ObservationSnapshot(**data)


def test_valid_snapshot_produces_line_ev_report() -> None:
    result = advise_snapshot(snap(), ("As", "Ad"), opponent_vpip=0.8, trials=250, seed=1)
    assert result["valid"] is True
    assert "line_ev" in result
    assert result["chosen"] in {"fold", "call", "raise"}
    assert result["line_ev"]["precision"] == "finite_continuation_tree"


def test_invalid_snapshot_fails_closed_before_solver() -> None:
    result = advise_snapshot(snap(street="turn"), ("As", "Ad"), trials=100)
    assert result["valid"] is False
    assert "board_street_mismatch" in result["validation"]["errors"]


def test_bridge_never_returns_illegal_action() -> None:
    result = advise_snapshot(
        snap(allowed_actions=("fold", "call"), min_raise=None),
        ("7c", "2d"), opponent_vpip=0.5, trials=150, seed=2,
    )
    assert result["valid"] is True
    assert result["chosen"] in {"fold", "call"}
