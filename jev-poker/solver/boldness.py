"""Этап 4: график наглости игрока.

Кривая строится по наблюдаемой агрессии (число агрессивных улиц и их
тяжеловесность в больших блайндах), с базовой линией (долгий средний) и
затухающим краткосрочным смещением (EWMA с настраиваемым полураспадом).

Реакция «после выигрыша наглеет / после проигрыша тише» НЕ задаётся
общим правилом: модуль умеет проверять её только там, где журнал даёт
исход (пока только hero). Для оппонентов исход руки неизвестен — это
зафиксированный пробел данных.
"""

from __future__ import annotations

import math

STREETS = ("preflop", "flop", "turn", "river")


def hand_boldness(history: list[dict], pid: str, bb: int) -> float:
    """Наглость в одной раздаче: сумма агрессивных взносов в bb.

    Веса улиц растут (префлоп 1, флоп 1.2, тёрн 1.4, ривер 1.6): давление
    на поздних улицах дороже и смелее. Блайнды не считаются агрессией.
    """
    weight = {"preflop": 1.0, "flop": 1.2, "turn": 1.4, "river": 1.6}
    if bb <= 0:
        raise ValueError("bb должен быть положительным")
    total = 0.0
    for e in history:
        if e.get("id") != pid:
            continue
        if e.get("type") != 8 or e.get("blind") or int(e.get("add", 0) or 0) <= 0:
            continue
        total += weight.get(e.get("street", "preflop"), 1.0) * int(e["add"]) / bb
    return round(total, 4)


def boldness_series(hands: list[dict], pid: str, bb: int) -> list[tuple[str, float]]:
    """Хронологическая кривая: [(время раздачи, наглость)] по порядку журнала."""
    out = []
    for h in hands:
        history = h.get("history", [])
        if not any(e.get("id") == pid for e in history):
            continue
        out.append((h.get("at", ""), hand_boldness(history, pid, bb)))
    return out


def decayed_state(
    series: list[tuple[str, float]],
    half_life: float = 8.0,
) -> dict:
    """EWMA наглости против базовой линии.

    baseline — среднее по всей кривой; state — затухающее среднее с
    полураспадом half_life рук; shift — (state - baseline), нормированный
    на стандартное отклонение кривой (z-подобная мера «наглеет/тише»).
    """
    if not series:
        return {"n": 0, "baseline": 0.0, "state": 0.0, "shift_z": 0.0}
    alpha = 1 - math.pow(0.5, 1.0 / half_life) if half_life > 0 else 1.0
    values = [v for _, v in series]
    baseline = sum(values) / len(values)
    ewma = values[0]
    for v in values[1:]:
        ewma = ewma + alpha * (v - ewma)
    var = sum((v - baseline) ** 2 for v in values) / len(values)
    std = math.sqrt(var)
    shift = (ewma - baseline) / std if std > 1e-9 else 0.0
    return {
        "n": len(series),
        "baseline": round(baseline, 3),
        "state": round(ewma, 3),
        "shift_z": round(shift, 3),
    }


def reaction_after_outcome(
    hands: list[dict],
    pid: str,
    bb: int,
    half_life: float = 8.0,
) -> dict:
    """Проверка реакции на исход.

    Работает только для hero (его выигрыши известны). Возвращает среднюю
    наглость раздач после выигранных и после проигранных рук. Вывод:
    корреляция по конкретному игроку, не общее правило.
    """
    series = boldness_series(hands, pid, bb)
    by_time = dict(series)
    ordered = [t for t, _ in series]
    after_win, after_loss = [], []
    for i, t in enumerate(ordered[:-1]):
        h = next(h for h in hands if h.get("at", "") == t)
        won = bool(h.get("result", {}).get("won"))
        nxt = by_time[ordered[i + 1]]
        (after_win if won else after_loss).append(nxt)
    mean = lambda xs: round(sum(xs) / len(xs), 3) if xs else None  # noqa: E731
    return {
        "player": pid,
        "after_win_n": len(after_win),
        "after_win_bold": mean(after_win),
        "after_loss_n": len(after_loss),
        "after_loss_bold": mean(after_loss),
        "hypothesis": "после выигрыша наглеет" if after_win and after_loss and mean(after_win) > mean(after_loss) else "данных мало или обратно",
        "caveat": "исходы известны только у hero; для оппонентов нужен журнал вскрытий и победителей",
        "half_life": half_life,
    }
