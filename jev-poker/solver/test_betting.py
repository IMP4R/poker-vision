"""Тесты ставок: доля фолдов, EV блефа, value/блеф/чек."""

import pytest

from solver.betting import (
    bluff_ev,
    breakeven_fold_share,
    fold_share,
    plan_bet,
    semibluff_ev,
    tighten_by_aggression,
)
from solver.ranges import full_range, top_percent_range


def test_bluff_ev_formula() -> None:
    assert bluff_ev(100, 50, 1.0) == 100.0
    assert bluff_ev(100, 50, 0.0) == -50.0
    assert abs(bluff_ev(100, 50, breakeven_fold_share(50, 100))) < 1e-9
    with pytest.raises(ValueError):
        bluff_ev(0, 50, 0.5)
    with pytest.raises(ValueError):
        bluff_ev(100, 50, 1.5)


def test_breakeven_threshold() -> None:
    assert abs(breakeven_fold_share(50, 100) - 1 / 3) < 1e-9
    assert breakeven_fold_share(100, 100) == 0.5


def test_fold_share_river_only() -> None:
    with pytest.raises(ValueError):
        fold_share(("7h", "3c", "2d"), full_range())


def test_fold_share_is_higher_vs_tight_range() -> None:
    board = ("7h", "3c", "2d", "9s", "Kc")  # сухой борд: много воздуха
    fs_wide = fold_share(board, full_range(), seed=1)
    fs_tight = fold_share(board, top_percent_range(10), seed=1)
    assert 0 < fs_tight < fs_wide < 1, (fs_tight, fs_wide)


def test_fold_share_low_on_coordinated_board() -> None:
    # Флешовый и спаренный борд: воздух почти нет, все "руки" живые.
    board = ("7h", "8h", "9h", "8d", "7d")
    fs = fold_share(board, full_range(), seed=2)
    assert fs < 0.35, fs


def test_plan_bet_bluffs_dry_board_with_air() -> None:
    hero = ("2c", "7d")  # воздух на сухом борде
    board = ("4h", "9s", "Kd", "3c", "8d")
    r = plan_bet(hero, board, pot=1000, opp_range=top_percent_range(60), seed=3)
    assert r["action"] in ("bet", "check")
    if r["action"] == "bet":
        assert r["kind"] == "bluff"
        assert r["fold_share"] > breakeven_fold_share(r["size"], 1000)


def test_plan_bet_value_with_nuts() -> None:
    hero = ("Ah", "Kh")  # натсовый флеш
    board = ("Qh", "Jh", "2h", "5d", "9s")
    r = plan_bet(hero, board, pot=1000, opp_range=full_range(), seed=4)
    assert r["action"] == "bet" and r["kind"] == "value"
    assert r["size"] == round(1000 * 2 / 3)


def test_plan_bet_needs_river() -> None:
    with pytest.raises(ValueError):
        plan_bet(("Ah", "Kh"), ("Qh", "Jh", "2h"), 1000, full_range())


def test_semibluff_ev_signs_and_bounds() -> None:
    # Частый фолд + хорошее дро -> плюс; редкий фолд + мусор -> минус.
    ev_good = semibluff_ev(1000, 600, 0.6, 0.45)
    ev_bad = semibluff_ev(1000, 600, 0.2, 0.15)
    assert ev_good > 0 > ev_bad
    # Границы согласованы с чистым блефом и чистым коллом.
    assert semibluff_ev(1000, 600, 1.0, 0.9) == 1000.0
    pure_call = 0.45 * (1000 + 1200) - 600
    assert abs(semibluff_ev(1000, 600, 0.0, 0.45) - pure_call) < 1e-9
    with pytest.raises(ValueError):
        semibluff_ev(1000, 600, 1.2, 0.5)


def test_tighten_by_aggression_monotone() -> None:
    assert tighten_by_aggression(80, 0) == 80.0
    t1, t2, t3 = (tighten_by_aggression(80, k) for k in (1, 2, 3))
    assert 1.0 < t3 < t2 < t1 < 80.0
    assert t3 == pytest.approx(80 * 0.55 ** 3, abs=1e-9)
    with pytest.raises(ValueError):
        tighten_by_aggression(80, -1)
    with pytest.raises(ValueError):
        tighten_by_aggression(0, 1)
