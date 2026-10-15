"""Этап 2: математика рук — категории, equity, EV закрывающего колла."""

from __future__ import annotations

import random
from itertools import combinations

from phevaluator import evaluate_cards

RANKS = "23456789TJQKA"
SUITS = "shdc"
DECK = tuple(r + s for r in RANKS for s in SUITS)

# phevaluator: 1 = стрит-флеш ... 7462 = старшая карта.
# Пороги сверены реальными значениями: роял=1, каре=11, фулл=167,
# флеш=323, стрит=1600, пара=3326, старшая=6311.
CATEGORY_NAMES = [
    "high_card",
    "pair",
    "two_pair",
    "trips",
    "straight",
    "flush",
    "full_house",
    "quads",
    "straight_flush",
]

_CLASS_BREAKS = (6185, 3325, 2467, 1609, 1599, 322, 166, 10)


def hand_class(cards: tuple[str, ...]) -> int:
    """0 = старшая карта ... 8 = стрит-флеш."""
    score = evaluate_cards(*cards)
    if score <= 10:
        return 8
    if score <= 166:
        return 7
    if score <= 322:
        return 6
    if score <= 1599:
        return 5
    if score <= 1609:
        return 4
    if score <= 2467:
        return 3
    if score <= 3325:
        return 2
    if score <= 6185:
        return 1
    return 0


def uses_hole_cards(hole: tuple[str, ...], board: tuple[str, ...]) -> bool:
    """Участвует ли хотя бы одна карта hero в лучшей пятёрке.

    Нужна, чтобы не считать «пару на борде» силой hero (ошибка старого
    анализатора).
    """
    all_cards = hole + board
    best = None
    for five in combinations(all_cards, 5):
        score = evaluate_cards(*five)
        if best is None or score < best:
            best = score
    for five in combinations(all_cards, 5):
        if evaluate_cards(*five) == best and any(c in five for c in hole):
            return True
    return False


def equity_montecarlo(
    hole: tuple[str, ...],
    board: tuple[str, ...],
    opponents: int,
    *,
    trials: int = 3000,
    seed: int = 0,
) -> float:
    """Доля банка hero против `opponents` случайных рук.

    Известные карты исключаются из колоды; борд добирается до пяти карт.
    Возвращает оценку эквити в [0, 1].
    """
    if len(hole) != 2 or not 0 <= len(board) <= 5:
        raise ValueError("нужны 2 карты hero и 0-5 карт борда")
    known = set(hole) | set(board)
    deck = [c for c in DECK if c not in known]
    rng = random.Random(seed)
    need_board = 5 - len(board)
    if len(deck) < need_board + 2 * opponents:
        raise ValueError("недостаточно карт для раздачи")
    wins = ties = 0
    for _ in range(trials):
        rng.shuffle(deck)
        idx = 0
        full_board = list(board)
        for i in range(need_board):
            full_board.append(deck[idx])
            idx += 1
        hero_score = evaluate_cards(*hole, *full_board)
        best = None
        tie = False
        for o in range(opponents):
            o1, o2 = deck[idx + 2 * o], deck[idx + 2 * o + 1]
            score = evaluate_cards(o1, o2, *full_board)
            if best is None or score < best:
                best, tie = score, False
            elif score == best:
                tie = True
        if hero_score < best:
            wins += 1
        elif hero_score == best and tie:
            ties += 1
    return (wins + ties * 0.5) / trials


def ev_call(equity: float, pot_before: int, call: int) -> float:
    """EV закрывающего колла: без рейка, побочных банков и будущих ставок.

    EV = equity * (P + C) - C, где P — банк до колла, C — стоимость колла.
    """
    if call <= 0:
        raise ValueError("колл должен быть положительным")
    return equity * (pot_before + call) - call


def required_equity(pot_before: int, call: int) -> float:
    """Порог эквити, ниже которого закрывающий колл убыточен."""
    if pot_before <= 0 or call <= 0:
        raise ValueError("банк и колл должны быть положительными")
    return call / (pot_before + call)
