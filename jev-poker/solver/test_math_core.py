"""Тесты математического ядра: категории, equity, EV."""

from itertools import combinations

from phevaluator import evaluate_cards

from solver.math_core import (
    DECK,
    equity_montecarlo,
    ev_call,
    hand_class,
    required_equity,
    uses_hole_cards,
)


def test_hand_classes_known_hands() -> None:
    assert hand_class(("As", "Ks", "Qs", "Js", "Ts")) == 8  # роял = стрит-флеш
    assert hand_class(("Ah", "Ad", "Ac", "As", "Kd")) == 7  # каре
    assert hand_class(("Ah", "Ad", "Ac", "Ks", "Kd")) == 6  # фулл
    assert hand_class(("Ah", "Kh", "Qh", "Jh", "9h")) == 5  # флеш
    assert hand_class(("Ah", "Kd", "Qh", "Js", "Tc")) == 4  # стрит
    assert hand_class(("Ah", "Ad", "Ks", "Qd", "Jc")) == 1  # пара
    assert hand_class(("Ah", "Kd", "9s", "5d", "2c")) == 0  # старшая


def test_pair_on_board_is_not_hero_strength() -> None:
    # 42 на борде 8h Qc 6c Qh 9s: лучшая рука = пара дам борда, карты hero
    # (кикеры 4 и 2) не входят ни в одну лучшую пятёрку.
    hole = ("4d", "2c")
    board = ("8h", "Qc", "6c", "Qh", "9s")
    seven = hole + board
    best = min(evaluate_cards(*five) for five in combinations(seven, 5))
    board_only = min(evaluate_cards(*five) for five in combinations(board, 5))
    assert best == board_only == 3931
    assert uses_hole_cards(hole, board) is False


def test_pair_in_hand_uses_hole() -> None:
    assert uses_hole_cards(("Ah", "Ad"), ("Ks", "7d", "2c", "9h", "5s")) is True


def test_equity_aces_preflop_beats_random() -> None:
    eq = equity_montecarlo(("As", "Ad"), (), 1, trials=4000, seed=7)
    assert 0.75 < eq < 0.95, eq


def test_equity_degenerate() -> None:
    # 7-2 против одного: мало; против четырёх: ещё меньше.
    weak = equity_montecarlo(("7c", "2d"), (), 1, trials=3000, seed=3)
    weak4 = equity_montecarlo(("7c", "2d"), (), 4, trials=3000, seed=3)
    assert weak < 0.45
    assert weak4 < weak
    # готовый флеш на ривере бьёт случайные руки почти всегда.
    flush = equity_montecarlo(("Ah", "Kh"), ("Qh", "Jh", "2h", "5d", "9s"), 1, trials=2000, seed=1)
    assert flush > 0.9


def test_ev_call_sign() -> None:
    # equity 0.5 при pot 100, call 50: EV = 0.5*150 - 50 = +25.
    assert abs(ev_call(0.5, 100, 50) - 25.0) < 1e-9
    # порог: 50/150 = 1/3; ниже порога EV<0.
    assert required_equity(100, 50) < 0.33334
    assert ev_call(0.3, 100, 50) < 0 < ev_call(0.4, 100, 50)
