"""Regression: overbet sizing must narrow villain range before equity compare."""

from solver.advisor import _range_percent, advise


def test_range_percent_narrows_graduated_by_bet_size() -> None:
    assert _range_percent(1.0, 0.3) == 100.0
    assert _range_percent(1.0, 0.5) == 80.0
    assert _range_percent(1.0, 0.74) == 32.0
    assert _range_percent(1.0, 0.91) == 18.0


def test_kk_folds_overbet_into_ace_board() -> None:
    """KK on A-high board vs pot-sized overbet: range ~10% → equity below required+margin."""
    result = advise(
        ("Ks", "Kd"), ("3d", "Ad", "6h"),
        pot_before=34000, to_call=31000, stack=148000,
        opponent_vpip=1.0, opponent_aggressive_streets=1, opponents=2,
        trials=9000, seed=7,
    )
    assert result["range_percent"] <= 12.0
    assert result["action"] == "fold"


def test_kk_folds_turn_overbet_into_ace_board() -> None:
    """Same discipline on the turn: overbet raise demands margin."""
    result = advise(
        ("Ks", "Kd"), ("3d", "Ad", "6h", "3s"),
        pot_before=130000, to_call=96000, stack=116000,
        opponent_vpip=1.0, opponent_aggressive_streets=2, opponents=2,
        trials=9000, seed=7,
    )
    assert result["action"] == "fold"


def test_kk_still_calls_small_bet_into_ace_board() -> None:
    """Small bet keeps wide range; KK has equity vs missed hands."""
    result = advise(
        ("Ks", "Kd"), ("3d", "Ad", "6h"),
        pot_before=34000, to_call=6000, stack=148000,
        opponent_vpip=1.0, opponent_aggressive_streets=1, opponents=2,
        trials=9000, seed=7,
    )
    assert result["action"] in {"call", "check"}
