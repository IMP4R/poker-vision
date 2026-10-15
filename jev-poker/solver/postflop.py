"""G5: постфлоп-кандидаты и ограниченная оценка продолжения.

Модуль намеренно отделён от живого контроллера. Он возвращает прозрачные
approximate-кандидаты: полноценное дерево будущих действий G5+ подключается
позже, но здесь уже нет единственного call/fold-порога.
"""

from __future__ import annotations

from itertools import combinations

from phevaluator import evaluate_cards

from solver.math_core import DECK, hand_class
from solver.ranges import equity_vs_range, top_percent_range

RANKS = "23456789TJQKA"


def board_texture(board: tuple[str, ...]) -> dict:
    """Детерминированные признаки структуры борда."""
    if not 3 <= len(board) <= 5:
        raise ValueError("postflop требует 3-5 карт борда")
    ranks = [RANKS.index(c[0]) for c in board]
    counts = {r: ranks.count(r) for r in set(ranks)}
    suit_counts = {s: sum(c[1] == s for c in board) for s in set(c[1] for c in board)}
    max_suit = max(suit_counts.values())
    distinct = sorted(set(ranks))
    connected = any(b - a <= 2 for a, b in zip(distinct, distinct[1:]))
    return {
        "paired": max(counts.values()) >= 2,
        "trips_on_board": max(counts.values()) >= 3,
        "monotone": max_suit >= 3,
        "two_tone": max_suit == 2,
        "connected": connected,
        "high_card": RANKS[max(ranks)],
        "max_suit_count": max_suit,
        "wetness": round(
            (0.30 if max_suit >= 3 else 0.15 if max_suit == 2 else 0.0)
            + (0.25 if connected else 0.0)
            + (0.15 if max(counts.values()) >= 2 else 0.0),
            3,
        ),
    }


def _next_card_outs(hole: tuple[str, str], board: tuple[str, ...]) -> dict:
    """Сырые улучшения на одну следующую карту.

    Классифицируем только повышение категории made hand. Это не обещание
    чистоты аута: против диапазона соперника часть карт может дать ему более
    сильную комбинацию и должна быть дисконтирована на следующем уровне.
    """
    dead = set(hole) | set(board)
    current = hand_class(tuple(hole) + tuple(board))
    if len(board) == 5:
        return {"current_class": current, "outs": [], "by_class": {}, "count": 0}
    live = [c for c in DECK if c not in dead]
    improvements = [c for c in live if hand_class(tuple(hole) + tuple(board) + (c,)) > current]
    # hand_class: 0 high -> 8 straight flush, so greater is stronger.
    by_class: dict[str, list[str]] = {}
    for c in improvements:
        name = ["high_card", "pair", "two_pair", "trips", "straight", "flush", "full_house", "quads", "straight_flush"][
            hand_class(tuple(hole) + tuple(board) + (c,))
        ]
        by_class.setdefault(name, []).append(c)
    return {"current_class": current, "outs": improvements, "by_class": by_class, "count": len(improvements)}


def executable_size(requested: int, legal_min: int, legal_max: int | None = None) -> dict:
    """Сопоставить рассчитанный размер с реально разрешённым UI размером."""
    if requested <= 0 or legal_min <= 0:
        raise ValueError("размеры положительны")
    if legal_max is not None and legal_max < legal_min:
        raise ValueError("legal_max меньше legal_min")
    actual = max(requested, legal_min)
    if legal_max is not None:
        actual = min(actual, legal_max)
    return {
        "requested": requested,
        "actual": actual,
        "clamped": actual != requested,
        "precision": "clamped_to_legal_size" if actual != requested else "exact_legal_size",
    }


def postflop_candidates(
    hole: tuple[str, str],
    board: tuple[str, ...],
    *,
    pot: int,
    to_call: int,
    stack: int,
    opponent_vpip: float | None = None,
    opponents: int = 1,
    position: str = "unknown",
    fold_share: float | None = None,
    trials: int = 3000,
    seed: int = 0,
) -> dict:
    """Кандидаты postflop: fold/check/call/value/semi-bluff/bluff.

    Если ставка уже есть, call и raise-value сравниваются; если ставки нет,
    check и инициативные bet-кандидаты сравниваются. Будущие улицы ещё
    абстрагированы, поэтому результаты помечены approximate.
    """
    if len(hole) != 2 or not 3 <= len(board) <= 5:
        raise ValueError("нужны 2 hole-карты и 3-5 карт борда")
    if pot <= 0 or to_call < 0 or stack < 0 or to_call > stack:
        raise ValueError("некорректные pot/call/stack")
    texture = board_texture(board)
    draws = _next_card_outs(hole, board)
    percent = 100.0 if opponent_vpip is None else max(5.0, min(100.0, opponent_vpip * 100))
    opp_range = top_percent_range(percent)
    equity = equity_vs_range(hole, board, opp_range, opponents=opponents, trials=trials, seed=seed)
    current_class = draws["current_class"]
    required = to_call / (pot + to_call) if to_call else 0.0
    candidates = [{"action": "fold", "kind": "cheap_exit", "ev": 0.0, "size": 0}]
    if to_call:
        call_ev = equity * (pot + to_call) - to_call
        realization = 0.90 if position in {"button", "cutoff"} else 0.72
        call_ev *= realization
        kind = "bluff_catch" if current_class >= 1 and equity < 0.65 else "call"
        candidates.append({"action": "call", "kind": kind, "ev": round(call_ev, 4), "size": to_call,
                           "realization": realization})
        raise_size = max(to_call * 2, pot // 2, 1)
        raise_ev = equity * (pot + to_call + raise_size) - to_call - raise_size
        if equity >= 0.70:
            candidates.append({"action": "raise", "kind": "value", "ev": round(raise_ev, 4), "size": raise_size})
        elif draws["count"] >= 8 and (fold_share or 0.0) >= 0.35:
            semi_ev = (fold_share or 0.0) * pot + (1 - (fold_share or 0.0)) * raise_ev
            candidates.append({"action": "raise", "kind": "semi_bluff", "ev": round(semi_ev, 4), "size": raise_size})
    else:
        candidates.append({"action": "check", "kind": "pot_control", "ev": 0.0, "size": 0})
        bet_size = max(pot * 2 // 3, 1)
        if equity >= 0.65:
            candidates.append({"action": "bet", "kind": "value", "ev": round(equity * (pot + bet_size) - bet_size, 4), "size": bet_size})
        elif draws["count"] >= 8 and (fold_share or 0.0) >= 0.35:
            semi_ev = (fold_share or 0.0) * pot + (1 - (fold_share or 0.0)) * (equity * (pot + 2 * bet_size) - bet_size)
            candidates.append({"action": "bet", "kind": "semi_bluff", "ev": round(semi_ev, 4), "size": bet_size})
        elif current_class == 0 and (fold_share or 0.0) >= 0.55:
            bluff_ev = (fold_share or 0.0) * pot - (1 - (fold_share or 0.0)) * bet_size
            candidates.append({"action": "bet", "kind": "bluff", "ev": round(bluff_ev, 4), "size": bet_size})
    candidates.sort(key=lambda x: x["ev"], reverse=True)
    return {
        "chosen": candidates[0],
        "candidates": candidates,
        "texture": texture,
        "draws": draws,
        "equity": round(equity, 4),
        "required": round(required, 4),
        "precision": "approximate",
        "opponent_known": opponent_vpip is not None,
    }
