"""Этап 2+: взвешенные диапазоны вместо случайных карт.

Диапазон — веса 1326 комбинаций. Выборка уважает веса, известные карты
(hero, борд, блокеры) исключаются. Обновление после действия — умножение
на правдоподобие действия из профиля соперника (механизм; профиль
наполняется позже этапом 3).
"""

from __future__ import annotations

import random

RANKS = "23456789TJQKA"
SUITS = "shdc"

_ALL_COMBOS: list[tuple[str, str]] = []
for _i, _r1 in enumerate(RANKS):
    for _r2 in RANKS[_i:]:
        if _r1 == _r2:
            for _a, _b in ((SUITS[k], SUITS[m]) for k in range(4) for m in range(k + 1, 4)):
                _ALL_COMBOS.append((_r1 + _a, _r1 + _b))
        else:
            for _s1 in SUITS:
                for _s2 in SUITS:
                    _ALL_COMBOS.append((_r1 + _s1, _r2 + _s2))
N_COMBOS = len(_ALL_COMBOS)
assert N_COMBOS == 1326


def full_range() -> dict[tuple[str, str], float]:
    """Равномерный диапазон: каждая комбинация с весом 1."""
    return {c: 1.0 for c in _ALL_COMBOS}


def top_percent_range(percent: float) -> dict[tuple[str, str], float]:
    """Грубый диапазон «верхние N% стартовых рук» по классической шкале чартов.

    Достаточно для оценки колла до появления реальных профилей: порядок рук
    фиксирован (пары старше, затем suited, затем offsuit), внутри пар вес
    каждой комбинации равный.
    """
    if not 0 < percent <= 100:
        raise ValueError("percent в (0, 100]")

    def key(combo: tuple[str, str]) -> tuple[int, int, int]:
        (a, b) = combo
        ra, rb = RANKS.index(a[0]), RANKS.index(b[0])
        hi, lo = max(ra, rb), min(ra, rb)
        suited = int(a[1] == b[1])
        pair = int(ra == rb)
        # порядок: пары, потом suited, потом offsuit; внутри — старшая карта
        return (0 if pair else 1 if suited else 2, -hi if pair else -hi, -lo)

    ranked = sorted(_ALL_COMBOS, key=key)
    take = max(1, round(N_COMBOS * percent / 100))
    return {c: 1.0 for c in ranked[:take]}


def update_range(
    rng_weights: dict[tuple[str, str], float],
    likelihood: dict[tuple[str, str], float],
) -> dict[tuple[str, str], float]:
    """Байесовское обновление: вес * P(действие | рука), затем нормировка."""
    if set(likelihood) - set(rng_weights):
        raise ValueError("правдоподобие содержит чужие комбинации")
    out = {c: rng_weights[c] * likelihood.get(c, 0.0) for c in rng_weights}
    total = sum(out.values())
    if total <= 0:
        raise ValueError("правдоподобие обнулило весь диапазон")
    return {c: w / total for c, w in out.items()}


def sample_hand(
    rng_weights: dict[tuple[str, str], float],
    dead: set[str],
    rand: random.Random,
) -> tuple[str, str] | None:
    """Выбрать комбинацию по весам из живых карт.

    Возвращает None, если не осталось допустимых комбинаций.
    """
    live = [
        (c, w) for c, w in rng_weights.items() if c[0] not in dead and c[1] not in dead and w > 0
    ]
    if not live:
        return None
    total = sum(w for _, w in live)
    x = rand.random() * total
    acc = 0.0
    for c, w in live:
        acc += w
        if x <= acc:
            return c
    return live[-1][0]


def equity_vs_ranges(
    hole: tuple[str, ...],
    board: tuple[str, ...],
    opponent_ranges: tuple[dict[tuple[str, str], float], ...],
    *,
    trials: int = 4000,
    seed: int = 0,
    rank_cards=None,
) -> dict:
    """Equity hero против отдельного диапазона каждого соперника.

    Комбинации выбираются последовательно с общим dead-card set, поэтому
    card removal действует между всеми игроками. Возвращает equity и
    стандартную ошибку доли банка, а не только среднее.
    """
    import math

    if rank_cards is None:
        from phevaluator import evaluate_cards

        rank_cards = evaluate_cards
    if len(hole) != 2 or not 0 <= len(board) <= 5:
        raise ValueError("нужны 2 карты hero и 0-5 карт борда")
    if not opponent_ranges:
        raise ValueError("нужен хотя бы один диапазон соперника")
    if trials <= 0:
        raise ValueError("trials положителен")
    rng = random.Random(seed)
    known = set(hole) | set(board)
    deck = [r + s for r in RANKS for s in SUITS if r + s not in known]
    need_board = 5 - len(board)
    shares: list[float] = []
    for _ in range(trials):
        dead = set(known)
        sampled = []
        for opp_range in opponent_ranges:
            hand = sample_hand(opp_range, dead, rng)
            if hand is None:
                raise ValueError("диапазон соперника пуст после card removal")
            sampled.append(hand)
            dead.update(hand)
        pool = [c for c in deck if c not in dead]
        rng.shuffle(pool)
        full_board = list(board) + pool[:need_board]
        hero_score = rank_cards(*hole, *full_board)
        scores = [rank_cards(*cards, *full_board) for cards in sampled]
        best = min([hero_score, *scores])
        winners = int(hero_score == best) + sum(score == best for score in scores)
        shares.append((1.0 / winners) if hero_score == best else 0.0)
    equity = sum(shares) / trials
    variance = sum((x - equity) ** 2 for x in shares) / trials
    return {
        "equity": equity,
        "stderr": math.sqrt(variance / trials),
        "trials": trials,
        "opponents": len(opponent_ranges),
        "precision": "monte_carlo",
    }


def equity_vs_range(
    hole: tuple[str, ...],
    board: tuple[str, ...],
    opponent_range: dict[tuple[str, str], float],
    opponents: int = 1,
    *,
    trials: int = 4000,
    seed: int = 0,
    rank_cards=None,
) -> float:
    """Эквити hero против соперника, выбирающего руки из взвешенного диапазона.

    При opponents > 1 остальные игроки получают случайные карты. Оценка рук
    делегируется rank_cards (по умолчанию phevaluator), чтобы диапазоны не
    тащили зависимость от бэкенда.
    """
    ranges = [opponent_range]
    if opponents > 1:
        ranges.extend(full_range() for _ in range(opponents - 1))
    return equity_vs_ranges(
        hole,
        board,
        tuple(ranges),
        trials=trials,
        seed=seed,
        rank_cards=rank_cards,
    )["equity"]
