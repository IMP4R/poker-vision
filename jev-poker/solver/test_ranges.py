"""Тесты взвешенных диапазонов."""

import collections
import random

from solver.ranges import (
    N_COMBOS,
    equity_vs_range,
    equity_vs_ranges,
    full_range,
    sample_hand,
    top_percent_range,
    update_range,
)


def test_combo_count_is_1326() -> None:
    assert N_COMBOS == 1326
    assert len(full_range()) == 1326


def test_top_percent_sizes() -> None:
    assert len(top_percent_range(100)) == 1326
    top10 = top_percent_range(10)
    assert 120 <= len(top10) <= 140, len(top10)
    # старшие пары точно внутри топ-10%
    assert ("As", "Ad") in top10 and ("Ks", "Kh") in top10
    # мусор вне
    assert ("2c", "7d") not in top10 and ("2h", "3s") not in top10


def test_update_normalizes_and_zeroes() -> None:
    fr = full_range()
    # сильные руки правдоподобны на рейз, остальные — почти нет
    like = {c: (1.0 if c in top_percent_range(15) else 0.01) for c in fr}
    upd = update_range(fr, like)
    assert abs(sum(upd.values()) - 1.0) < 1e-9
    strong = upd[("As", "Ad")]
    weak = upd[("2c", "7d")]
    assert strong > weak * 50
    try:
        update_range(fr, {c: 0.0 for c in fr})
    except ValueError as exc:
        assert "обнулил" in str(exc)
    else:
        raise AssertionError("обнуление не поймано")


def test_sample_respects_dead_cards_and_weights() -> None:
    fr = full_range()
    rand = random.Random(11)
    counts = collections.Counter()
    for _ in range(3000):
        hand = sample_hand(fr, {"As", "Ad", "Ah"}, rand)
        assert hand is not None
        assert "As" not in hand and "Ad" not in hand and "Ah" not in hand
        counts[hand] += 1
    # экслюзивные карты исключены, выборка распределена по 1325 комбинациям
    assert len(counts) > 1000
    # узкий диапазон: только пары AA/KK — выборка только из них
    narrow = {("As", "Ad"): 1.0, ("Ks", "Kh"): 1.0}
    for _ in range(200):
        hand = sample_hand(narrow, {"As"}, rand)
        # As мёртв -> остаётся KK и AA на живых картах? AA требует As — вся
        # комбинация ("As","Ad") запрещена из-за As.
        assert hand == ("Ks", "Kh")
    assert sample_hand(narrow, {"As", "Ks"}, rand) is None


def test_equity_vs_tight_range_is_lower_than_vs_random() -> None:
    # KK на сухом борде: против топ-10% эквити заметно ниже, чем против всех.
    hole = ("Ks", "Kd")
    board = ("7h", "3c", "2d")
    eq_random = equity_vs_range(hole, board, full_range(), trials=3000, seed=1)
    eq_tight = equity_vs_range(hole, board, top_percent_range(10), trials=3000, seed=1)
    assert eq_tight < eq_random - 0.05, (eq_tight, eq_random)


def test_separate_ranges_and_stderr() -> None:
    result = equity_vs_ranges(
        ("As", "Ad"),
        ("7h", "3c", "2d"),
        (top_percent_range(10), full_range()),
        trials=1200,
        seed=19,
    )
    assert 0 < result["equity"] < 1
    assert result["opponents"] == 2
    assert result["stderr"] > 0
    assert result["precision"] == "monte_carlo"


def test_separate_ranges_respect_cross_opponent_card_removal() -> None:
    # Оба диапазона требуют одну и ту же карту; второму игроку не остаётся
    # допустимой комбинации — функция обязана остановиться, а не клонировать As.
    impossible = {("As", "Kd"): 1.0}
    try:
        equity_vs_ranges(("2c", "3c"), (), (impossible, impossible), trials=1, seed=1)
    except ValueError as exc:
        assert "card removal" in str(exc)
    else:
        raise AssertionError("одна карта была выдана двум соперникам")


def test_heads_up_tie_gets_half_share() -> None:
    # На готовом Broadway hero и конкретный оппонент делят лучший board hand.
    hole = ("As", "Kd")
    board = ("Ah", "Kh", "Qh", "Jh", "Th")
    fr = {("Ac", "Kc"): 1.0}
    eq = equity_vs_range(hole, board, fr, opponents=1, trials=200, seed=3)
    assert abs(eq - 0.5) < 1e-12, eq


def test_equity_blockers_respected() -> None:
    # Hero держит туз флеша: у оппонента из диапазона с AhA? нет — карты мертвы.
    hole = ("Ah", "Kh")
    board = ("Qh", "Jh", "2c")
    fr = full_range()
    eq = equity_vs_range(hole, board, fr, trials=2000, seed=2)
    # монстр-дро против случайной руки сильное, но не 1.0
    assert 0.4 < eq < 0.95, eq
