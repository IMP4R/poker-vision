"""Этап 3: профили соперников из журнала.

Важно про идентичность: в свежих записях журнала оппоненты обозначены
местами P1..P5, где нумерация назначается заново в каждой раздаче. Такой
меткой нельзя связывать раздачи между руками. Стабильны только сырые id
вида '147502575_ABC'. Поэтому профили строим по сырым id; записи с меткой
места попадают только в агрегат по столам за одну раздачу.

Метрики считаются по возможностям, где журнал это позволяет, и честно
помечают пробелы (карты оппонентов на вскрытии в журнал не пишутся).
"""

from __future__ import annotations

import json
import math
import re

MOVE_FOLD, MOVE_CHECK, MOVE_CALL, MOVE_AGGRO = 1, 2, 4, 8
STABLE_ID = re.compile(r"^\d+_[A-Z0-9]+$")


def load_finished(path: str) -> list[dict]:
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if e.get("type") == "own_hand_finished" and "history" in e:
                out.append(e)
    return out


def _new_stats() -> dict:
    return {
        "hands": 0,
        "vpip_opps": 0,
        "vpip": 0,
        "pfr": 0,
        "postflop_aggr": 0,
        "postflop_calls": 0,
        "fold_postflop": 0,
        "raise_then_fold": 0,
        "went_to_river": 0,
    }


def wilson_lower(successes: int, trials: int, z: float = 1.96) -> float:
    """Нижняя граница Вильсона: консервативная оценка частоты."""
    if trials <= 0:
        return 0.0
    p = successes / trials
    denom = 1 + z * z / trials
    centre = p + z * z / (2 * trials)
    margin = z * math.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials))
    return max(0.0, (centre - margin) / denom)


def _is_aggressive(entry: dict) -> bool:
    return entry.get("type") == MOVE_AGGRO and not entry.get("blind") and int(entry.get("add", 0) or 0) > 0


def profile_hand(history: list[dict], players: set[str]) -> dict[str, dict]:
    """Статистика одной раздачи для перечисленных стабильных id."""
    stats = {p: _new_stats() for p in players}
    saw_flop = any(e.get("street") in ("flop", "turn", "river") for e in history)
    for p in players:
        s = stats[p]
        s["hands"] = 1
        entries = [e for e in history if e.get("id") == p]
        if not entries:
            continue
        preflop_voluntary = any(
            e.get("street", "preflop") == "preflop"
            and e.get("type") in (MOVE_CALL, MOVE_AGGRO)
            and not e.get("blind")
            and int(e.get("add", 0) or 0) > 0
            for e in entries
        )
        if preflop_voluntary:
            s["vpip"] = 1
        # возможность войти: игрок не сфолдил до первого добровольного шанса
        first_action = next((e for e in history if e.get("id") == p), None)
        if first_action is not None and first_action.get("type") != MOVE_FOLD:
            s["vpip_opps"] = 1
        s["pfr"] = int(
            any(
                e.get("street", "preflop") == "preflop" and _is_aggressive(e)
                for e in entries
            )
        )
        s["postflop_aggr"] = sum(1 for e in entries if e.get("street") in ("flop", "turn", "river") and _is_aggressive(e))
        s["postflop_calls"] = sum(1 for e in entries if e.get("street") in ("flop", "turn", "river") and e.get("type") == MOVE_CALL)
        folds = [e for e in entries if e.get("type") == MOVE_FOLD and e.get("street") in ("flop", "turn", "river")]
        s["fold_postflop"] = len(folds)
        # агрессия, за которой последовал фолд при продолжавшейся торговле:
        # признак «агрессивный трус», карты не нужны.
        aggro_idx = [i for i, e in enumerate(history) if e.get("id") == p and _is_aggressive(e)]
        fold_idx = [i for i, e in enumerate(history) if e.get("id") == p and e.get("type") == MOVE_FOLD]
        if any(a < f for a in aggro_idx for f in fold_idx):
            s["raise_then_fold"] = 1
        if saw_flop and not folds:
            s["went_to_river"] = 1
    return stats


def merge(dst: dict, src: dict) -> None:
    for player, s in src.items():
        slot = dst.setdefault(player, {k: 0 for k in _new_stats()})
        for k, v in s.items():
            slot[k] += v


def build_profiles(hands: list[dict]) -> dict[str, dict]:
    """Профили по стабильным id; метки P1..P5 в профили не попадают."""
    out: dict[str, dict] = {}
    for h in hands:
        history = h.get("history", [])
        stable = {
            e["id"]
            for e in history
            if e.get("id") != "hero" and STABLE_ID.match(str(e.get("id", "")))
        }
        merge(out, profile_hand(history, stable))
    return out


def summarize(profile: dict) -> dict:
    """Сводка: частоты и нижние границы Вильсона."""
    hands = profile["hands"]
    vpip = profile["vpip"]
    pfr = profile["pfr"]
    aggr = profile["postflop_aggr"]
    calls = profile["postflop_calls"]
    af = round(aggr / calls, 2) if calls else None
    return {
        "hands": hands,
        "vpip": round(vpip / hands, 2) if hands else None,
        "vpip_wilson_lo": round(wilson_lower(vpip, hands), 2) if hands else None,
        "pfr": round(pfr / hands, 2) if hands else None,
        "aggression_factor": af,
        "postflop_aggr": aggr,
        "postflop_calls": calls,
        "fold_postflop": profile["fold_postflop"],
        "raise_then_fold": profile["raise_then_fold"],
        "went_to_river": profile["went_to_river"],
    }


def vpip_to_range_percent(vpip: float) -> float:
    """Связка профиля с диапазоном: VPIP 0.6 -> примерно топ-60% чарта.

    Это первая, грубая оценка ширины диапазона по данным, не по табличке.
    """
    if not 0 < vpip <= 1:
        raise ValueError("vpip в (0, 1]")
    return max(5.0, min(100.0, vpip * 100))
