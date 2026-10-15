"""G4 tests: starting-hand classes and broad-entry scenarios."""

from solver.preflop import PreflopContext, classify_starting_hand, preflop_plan


def test_starting_hand_classes() -> None:
    assert classify_starting_hand(("As", "Ks"))["potential"] == "nut_flush_and_pair"
    assert classify_starting_hand(("7c", "7d"))["potential"] == "set_mining"
    assert classify_starting_hand(("9h", "8h"))["category"] == "suited_connector"
    assert classify_starting_hand(("As", "3c"))["category"] == "offsuit_ace"
    assert classify_starting_hand(("7c", "2d"))["category"] == "offsuit_trash"


def test_deep_position_can_price_speculative_entry() -> None:
    ctx = PreflopContext(600, 400, 40000, 20000, position="button", players_behind=0,
                         opponents=2, opponent_vpip=1.0)
    result = preflop_plan(("9h", "8h"), ctx, trials=800, seed=2)
    assert result["hand"]["category"] == "suited_connector"
    assert result["implied_bonus"] > 0
    assert result["future_cap"] > 0
    assert {x["action"] for x in result["candidates"]} == {"fold", "call", "raise"}


def test_squeeze_risk_penalizes_passive_entry() -> None:
    base = dict(pot=600, call=400, hero_stack=40000, effective_stack=20000,
                position="button", players_behind=2, aggressive_players_behind=1,
                opponents=2, opponent_vpip=1.0)
    safe = preflop_plan(("9h", "8h"), PreflopContext(**{**base, "players_behind": 1, "aggressive_players_behind": 0}), trials=600, seed=3)
    risky = preflop_plan(("9h", "8h"), PreflopContext(**base), trials=600, seed=3)
    assert risky["squeeze_penalty"] > safe["squeeze_penalty"]
    assert risky["candidates"][1]["ev"] <= safe["candidates"][1]["ev"]


def test_active_mode_is_visible_not_hidden() -> None:
    result = preflop_plan(("7c", "2d"), PreflopContext(600, 0, 40000, 20000,
                            position="button", opponents=1, active_mode=True), trials=500, seed=4)
    assert result["active_mode"] is True
    assert result["chosen"]["action"] in {"check", "raise"}


def test_active_mode_calls_cheap_offsuit_ace() -> None:
    result = preflop_plan(
        ("2h", "Ac"),
        PreflopContext(600, 400, 54800, 16000, opponents=3,
                       opponent_vpip=1.0, active_mode=True),
        trials=2500, seed=0,
    )
    assert result["chosen"]["action"] == "call"
    assert result["active_override"] is True


def test_active_mode_does_not_call_expensive_or_trash_entry() -> None:
    expensive = preflop_plan(
        ("2h", "Ac"), PreflopContext(600, 4000, 54800, 16000,
        opponents=3, opponent_vpip=1.0, active_mode=True), trials=500, seed=1)
    trash = preflop_plan(
        ("7c", "2d"), PreflopContext(600, 400, 54800, 16000,
        opponents=3, opponent_vpip=1.0, active_mode=True), trials=500, seed=1)
    assert expensive["chosen"]["action"] == "fold"
    assert trash["chosen"]["action"] == "fold"
