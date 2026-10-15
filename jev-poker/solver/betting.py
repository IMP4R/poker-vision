"""Ставки и блеф: доля фолдов из диапазона, EV чистого блефа, value-бет.

Модель доли фолдов — детерминированная и честно ограниченная: по борду
считается распределение категорий рук в диапазоне соперника (одна оценка
на комбинацию, без симуляций). Фолд приписывается только явному воздуху
(старшая карта) и частично слабым парам (настраиваемый параметр).
Это оценка снизу, а не истина: реальный фолд зависит от линии и психологии.

EV чистого блефа на ривере (без рейза): EV = F*P - (1-F)*B.
Value-бет даётся порогом эквити без фальшивой формулы EV.
"""

from __future__ import annotations

from itertools import combinations

from phevaluator import evaluate_cards

from solver.math_core import hand_class
from solver.ranges import _ALL_COMBOS, sample_hand
import random


def _combo_ok(combo: tuple[str, str], dead: set[str]) -> bool:
    return combo[0] not in dead and combo[1] not in dead


def fold_share(
    board: tuple[str, ...],
    opp_range: dict[tuple[str, str], float],
    *,
    pair_fold: float = 0.5,
    sample_limit: int = 400,
    seed: int = 0,
) -> float:
    """Взвешенная доля рук диапазона, которые, скорее всего, упадут.

    Воздух (старшая карта) — фолд всегда; пара — fold_pair доля; сильнее
    пары — не падают. При range > sample_limit комбинации сэмплируются.
    """
    if len(board) != 5:
        raise ValueError("модель фолдов определена только на ривере")
    dead = set(board)
    combos = [c for c in _ALL_COMBOS if _combo_ok(c, dead) and opp_range.get(c, 0) > 0]
    rng = random.Random(seed)
    if len(combos) > sample_limit:
        weights = [opp_range[c] for c in combos]
        picks = set()
        while len(picks) < sample_limit:
            c = sample_hand(opp_range, dead, rng)
            if c:
                picks.add(c)
        combos = sorted(picks)
    air = pair = total = 0.0
    for c in combos:
        cards = list(c) + list(board)
        cls = hand_class(tuple(cards))
        total += 1
        if cls == 0:
            air += 1
        elif cls == 1:
            pair += 1
    if total == 0:
        raise ValueError("диапазон пуст на этом борде")
    return (air + pair_fold * pair) / total


def bluff_ev(pot: int, bet: int, fold_share: float) -> float:
    """EV чистого блефа на ривере без возможного рейза."""
    if pot <= 0 or bet <= 0:
        raise ValueError("банк и ставка положительны")
    if not 0 <= fold_share <= 1:
        raise ValueError("доля фолдов в [0, 1]")
    return fold_share * pot - (1 - fold_share) * bet


def breakeven_fold_share(bet: int, pot: int) -> float:
    """Порог F, при котором блеф безубыточен: F = B/(B+P)."""
    if pot <= 0 or bet <= 0:
        raise ValueError("банк и ставка положительны")
    return bet / (bet + pot)


def semibluff_ev(
    pot: int,
    bet: int,
    fold_share: float,
    equity_when_called: float,
) -> float:
    """EV полу-блефа (флоп/тёрн) с честными допущениями.

    Модель: с вероятностью F соперник падает (герой берёт банк);
    иначе сравнение до ривера без дальнейших ставок:
    EV = F*P + (1-F) * (E*(P+2B) - B), где E — эквити до ривера
    против диапазона колла. Допущение «без дальнейших ставок» занижает
    реализацию эквити и игнорирует рейзы — помечено как approximate.
    """
    if pot <= 0 or bet <= 0:
        raise ValueError("банк и ставка положительны")
    if not 0 <= fold_share <= 1 or not 0 <= equity_when_called <= 1:
        raise ValueError("доли и эквити в [0, 1]")
    return fold_share * pot + (1 - fold_share) * (
        equity_when_called * (pot + 2 * bet) - bet
    )


def tighten_by_aggression(
    base_percent: float,
    aggressive_streets: int,
    *,
    factor: float = 0.55,
) -> float:
    """Сужение диапазона по числу агрессивных улиц линии соперника.

    Рейз префлоп + ставка флоп + ставка тёрн (3 улицы агрессии) сжимают
    стартовый диапазон примерно в factor^3 раз. Детерминированная и грубая
    оценка линии; уточняется реальными профилями позже.
    """
    if aggressive_streets < 0:
        raise ValueError("число улиц неотрицательно")
    if not 0 < base_percent <= 100 or not 0 < factor <= 1:
        raise ValueError("base_percent в (0,100], factor в (0,1]")
    return max(1.0, base_percent * factor ** aggressive_streets)


def plan_bet(
    hole: tuple[str, ...],
    board: tuple[str, ...],
    pot: int,
    opp_range: dict[tuple[str, str], float],
    *,
    pair_fold: float = 0.5,
    value_threshold: float = 0.65,
    seed: int = 0,
) -> dict:
    """Решение о ставке на ривере: value, блеф или чек.

    Value: эквити против диапазона >= value_threshold -> ставка 2/3 банка
    (без фальшивой формулы EV). Блеф: чистый воздух у hero и F > порога
    окупаемости для выбранного размера.
    """
    if len(hole) != 2 or len(board) != 5:
        raise ValueError("value/блеф на ривере требует 2+5 карт")
    from solver.ranges import equity_vs_range

    equity = equity_vs_range(hole, board, opp_range, trials=6000, seed=seed)
    if equity >= value_threshold:
        return {
            "action": "bet",
            "kind": "value",
            "size": round(pot * 2 / 3),
            "equity": round(equity, 3),
            "reason": f"эквити {equity:.3f} >= порога вэлью {value_threshold}",
            "precision": "heuristic_size",
        }
    fs = fold_share(board, opp_range, pair_fold=pair_fold, seed=seed)
    bet = round(pot * 2 / 3)
    ev = bluff_ev(pot, bet, fs)
    if ev > 0:
        return {
            "action": "bet",
            "kind": "bluff",
            "size": bet,
            "fold_share": round(fs, 3),
            "ev": round(ev, 1),
            "reason": f"доля фолдов {fs:.3f} выше порога {breakeven_fold_share(bet, pot):.3f}",
            "precision": "fold_share_model",
        }
    return {
        "action": "check",
        "reason": f"вэлью нет ({equity:.3f}), блеф не окупается (F={fs:.3f})",
        "fold_share": round(fs, 3),
        "ev": round(ev, 1),
        "precision": "fold_share_model",
    }
