"""Этап 5-6: советник «профиль → диапазон → EV» без кликов.

Действия:
- to_call == 0            -> check / value-bet / блеф / полу-блеф;
- закрывающий колл        -> call / fold по equity против диапазона.

Точность честная: на ривере формулы точны; до ривера — approximate
(реализация эквити и будущие ставки не моделируются). Никаких кликов:
чистая функция состояния.
"""

from __future__ import annotations

from solver.betting import (
    breakeven_fold_share,
    fold_share,
    semibluff_ev,
    tighten_by_aggression,
)
from solver.ranges import equity_vs_range, top_percent_range


def _range_percent(vpip: float | None, pot_bb_ratio: float) -> float:
    """Ширина диапазона: базовая из VPIP, сужение на крупные ставки.

    Размер ставки — главный сигнал о силе диапазона: овербет почти размера
    банка не ставит «любые две карты», поэтому диапазон сужается
    градуированно, а не только по счётчику агрессивных улиц.
    """
    base = 100.0 if vpip is None else vpip * 100.0
    if pot_bb_ratio >= 0.9:
        base *= 0.18
    elif pot_bb_ratio >= 0.66:
        base *= 0.32
    elif pot_bb_ratio >= 0.4:
        base *= 0.8
    return max(5.0, min(100.0, base))


def _drawness(hole: tuple[str, ...], board: tuple[str, ...]) -> float:
    """Грубая мера дро: 0..1. Флеш-дро 4 карты масти + открытые концы стрита."""
    suits = [c[1] for c in hole] + [c[1] for c in board]
    flush_draw = max(suits.count(s) for s in set(suits)) == 4
    hole_ranks = sorted("23456789TJQKA".index(c[0]) for c in hole)
    straight_draw = hole_ranks[1] - hole_ranks[0] <= 3
    return (0.5 if flush_draw else 0.0) + (0.3 if straight_draw else 0.0)


def advise(
    hole: tuple[str, ...],
    board: tuple[str, ...],
    pot_before: int,
    to_call: int,
    stack: int,
    *,
    opponent_vpip: float | None = None,
    opponent_aggressive_streets: int = 0,
    opponents: int = 1,
    trials: int = 12000,
    seed: int = 0,
) -> dict:
    """Рекомендация для ситуации с закрытой торговлей (колл) или без ставки."""
    if len(hole) != 2 or not 0 <= len(board) <= 5:
        raise ValueError("нужны 2 карты hero и 0-5 карт борда")
    if pot_before <= 0 or to_call < 0 or stack < 0:
        raise ValueError("некорректные суммы")
    if to_call > stack:
        raise ValueError("колл больше стэка")
    pot_bb_ratio = max(to_call, 1) / pot_before
    percent = _range_percent(opponent_vpip, pot_bb_ratio)
    percent = tighten_by_aggression(percent, opponent_aggressive_streets)
    opp_range = top_percent_range(percent)

    if to_call == 0:
        return _advise_bet(
            hole, board, pot_before, opp_range, percent,
            opponent_vpip, opponent_aggressive_streets, opponents, trials, seed,
        )
    return _advise_call(
        hole, board, pot_before, to_call, stack, opp_range, percent,
        opponent_vpip, opponents, trials, seed,
    )


def _advise_call(
    hole, board, pot_before, to_call, stack, opp_range, percent,
    opponent_vpip, opponents, trials, seed,
) -> dict:
    equity = equity_vs_range(hole, board, opp_range, opponents=opponents, trials=trials, seed=seed)
    required = to_call / (pot_before + to_call)
    # Крупные ставки требуют запаса: диапазон по VPIP/размеру приблизителен,
    # а будущие улицы могут потребовать дополнительных вложений (reverse implied).
    bet_ratio = to_call / pot_before
    required_margin = 0.03 if bet_ratio >= 0.9 else 0.02 if bet_ratio >= 0.66 else 0.0
    ev = equity * (pot_before + to_call) - to_call
    precision = "exact" if len(board) == 5 else "approximate"
    margin = equity - required
    if ev > 0 and margin > 0.02 + required_margin:
        action, reason = "call", f"equity {equity:.3f} > required {required:.3f} с запасом"
    elif ev <= 0 and margin < -0.02:
        action, reason = "fold", f"equity {equity:.3f} < required {required:.3f}"
    else:
        action, reason = "fold", f"запас {margin:+.3f} слишком мал для плюсового колла"
    return {
        "action": action,
        "reason": reason,
        "equity": round(equity, 3),
        "required": round(required, 3),
        "ev": round(ev, 1),
        "range_percent": round(percent, 1),
        "precision": precision,
        "opponent_known": opponent_vpip is not None,
    }


def _advise_bet(
    hole, board, pot, opp_range, percent,
    opponent_vpip, aggro_streets, opponents, trials, seed,
) -> dict:
    """Без ставки перед героем: чек / вэлью / блеф / полу-блеф.

    На ривере блеф считается по fold_share; до ривера — полу-блеф с
    эквити против диапазона колла (суженного вдвое: колят сильнее, чем
    открывают).
    """
    from solver.ranges import equity_vs_range

    if len(board) == 5:
        equity = equity_vs_range(hole, board, opp_range, trials=min(trials, 8000), seed=seed)
        if equity >= 0.65:
            return _bet("value", pot * 2 // 3, equity=round(equity, 3),
                        reason=f"вэлью: эквити {equity:.3f} >= 0.65", precision="heuristic_size")
        fs = fold_share(board, opp_range, seed=seed)
        size = pot * 2 // 3
        ev = fs * pot - (1 - fs) * size
        if ev > 0:
            return _bet("bluff", size, fold_share=round(fs, 3), ev=round(ev, 1),
                        reason=f"блеф: доля фолдов {fs:.3f} > порога {breakeven_fold_share(size, pot):.3f}",
                        precision="fold_share_model")
        return {"action": "check", "reason": f"вэлью нет ({equity:.3f}), блеф не окупается (F={fs:.3f})",
                "equity": round(equity, 3), "fold_share": round(fs, 3), "ev": round(ev, 1), "precision": "fold_share_model"}

    # флоп/тёрн: полу-блеф, если есть дро, либо вэлью при сильной руке
    equity = equity_vs_range(hole, board, opp_range, opponents=opponents, trials=min(trials, 8000), seed=seed)
    if equity >= 0.65:
        return _bet("value", pot * 2 // 3, equity=round(equity, 3),
                    reason=f"вэлью: эквити {equity:.3f} >= 0.65", precision="approximate")
    draw = _drawness(hole, board)
    call_range = top_percent_range(max(1.0, percent * 0.5))
    eq_called = equity_vs_range(hole, board, call_range, trials=min(trials, 8000), seed=seed + 1)
    size = pot * 2 // 3
    fs = 0.5 if opponent_vpip is None else min(0.9, 0.35 + 0.3 * (opponent_vpip))
    ev = semibluff_ev(pot, size, fs, eq_called)
    if draw >= 0.5 and ev > 0:
        return _bet("semibluff", size, equity=round(eq_called, 3), ev=round(ev, 1),
                    reason=f"полу-блеф: дро {draw:.1f}, F~{fs:.2f}, EV {ev:+.0f}",
                    precision="approximate")
    return {"action": "check", "reason": f"вэлью {equity:.3f} < 0.65, дро {draw:.1f}, полу-блеф EV {ev:+.0f}",
            "equity": round(equity, 3), "ev": round(ev, 1), "precision": "approximate"}


def _bet(kind, size, **extra) -> dict:
    out = {"action": "bet", "kind": kind, "size": int(size), **extra}
    return out
