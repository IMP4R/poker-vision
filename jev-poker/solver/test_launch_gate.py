"""G9 launch gate tests."""

from solver.launch_gate import LaunchRequest, authorize_launch, can_take_action


def request(**overrides):
    values = dict(
        human_authorized=True, jev_disabled=True, purchases_disabled=True,
        tournaments_disabled=True, g8_snapshot_confirmed=True,
        solver_tests_passed=True, controllers_stopped=True,
        play_money_only=True, max_hands=10, active_budget=1000,
    )
    values.update(overrides)
    return LaunchRequest(**values)


def test_complete_gate_authorizes_only_limited_play_money() -> None:
    gate = authorize_launch(request())
    assert gate["authorized"] is True
    assert gate["mode"] == "g9_play_money"
    assert can_take_action(gate=gate, action="check")["allowed"] is True


def test_missing_human_authorization_blocks() -> None:
    gate = authorize_launch(request(human_authorized=False))
    assert gate["authorized"] is False
    assert "human_authorized" in gate["failures"]
    assert can_take_action(gate=gate, action="check")["allowed"] is False


def test_purchases_and_tournaments_are_always_forbidden() -> None:
    gate = authorize_launch(request())
    assert can_take_action(gate=gate, action="call", purchase=True)["allowed"] is False
    assert can_take_action(gate=gate, action="call", tournament=True)["allowed"] is False


def test_invalid_action_is_blocked() -> None:
    gate = authorize_launch(request())
    result = can_take_action(gate=gate, action="buy_chips")
    assert result["allowed"] is False
    assert "unknown_game_action" in result["errors"]
