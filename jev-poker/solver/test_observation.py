"""G8 tests: protocol snapshots and executable action gate."""

from solver.observation import (
    ObservationSnapshot,
    allowed_from_mask,
    snapshot_from_protocol,
    validate_executable_action,
    validate_snapshot,
)


def snapshot(**overrides):
    values = dict(
        street="flop", board=("Ah", "Kd", "7c"), pot=1000, to_call=300,
        hero_stack=5000, allowed_actions=("fold", "call", "raise"),
        min_raise=600, committed=0, gross_contributions=1000,
    )
    values.update(overrides)
    return ObservationSnapshot(**values)


def test_allowed_mask_is_explicit() -> None:
    assert allowed_from_mask(1 | 4 | 8) == ("fold", "call", "raise")


def test_protocol_event_maps_to_snapshot() -> None:
    s = snapshot_from_protocol(
        {"call_value": 300, "cash": 5000, "raise_value": 600, "committed": 0},
        pot=1000, board=("Ah", "Kd", "7c"), allowed_mask=13,
    )
    assert s.street == "flop"
    assert s.allowed_actions == ("fold", "call", "raise")
    assert validate_snapshot(s)["valid"] is True


def test_valid_snapshot_and_legal_raise() -> None:
    report = validate_snapshot(snapshot())
    assert report["valid"] is True
    action = validate_executable_action(snapshot(), "raise", requested_size=600)
    assert action["valid"] is True
    assert action["actual_size"] == 600


def test_rejects_street_board_mismatch_and_unknown_mask() -> None:
    report = validate_snapshot(snapshot(street="turn"))
    assert report["valid"] is False
    assert "board_street_mismatch" in report["errors"]
    try:
        allowed_from_mask(16)
    except ValueError as exc:
        assert "неизвестные" in str(exc)
    else:
        raise AssertionError("unknown action bit accepted")


def test_rejects_illegal_action_and_raise_under_minimum() -> None:
    assert validate_executable_action(snapshot(), "check")["valid"] is False
    report = validate_executable_action(snapshot(), "raise", requested_size=100)
    assert report["valid"] is False
    assert "raise_below_legal_minimum" in report["errors"]


def test_free_check_does_not_allow_fold() -> None:
    report = validate_snapshot(snapshot(to_call=0, allowed_actions=("fold", "check")))
    assert report["valid"] is False
    assert "fold_without_bet_allowed" in report["errors"]
