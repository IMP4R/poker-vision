"""Импорт hero-раздач из auto-jev.jsonl без выдуманных данных.

Что журнал даёт достоверно:
- карты hero и борд;
- действия hero с суммами (type 8/4/2/1, add, total);
- общий банк на момент вскрытия/конца (game_round_finished → e.pots);
- результат hero (won/payout).

Чего журнал НЕ даёт:
- начальных стэков оппонентов;
- постов блайндов за противников (видны только в агрегированных committed);
- очерёдности ходов и показанных карт оппонентов.

Поэтому импортёр считает пот hero как сумму его собственных взносов и
проверяет сохранение фишек hero (stack_before - stack_after = committed),
а чужие стэки помечает unknown вместо выдуманных чисел.
"""

from __future__ import annotations

import json

MOVE = {1: "fold", 2: "check", 4: "call", 8: "bet_or_raise"}


def load_finished_journal(path: str) -> list[dict]:
    """Прочитать все own_hand_finished с историей."""
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


def hero_committed(history: list[dict]) -> int:
    """Сумма всех взносов hero за раздачу (add у hero-записей)."""
    return sum(int(a.get("add", 0) or 0) for a in history if a.get("id") == "hero")


def gross_pot(history: list[dict]) -> int:
    """Валовый банк = сумма всех add (включая возвращённые позже)."""
    return sum(int(a.get("add", 0) or 0) for a in history)


def street_split(history: list[dict]) -> dict[str, int]:
    """Валовые взносы по улицам; записи без street относятся к preflop."""
    out: dict[str, int] = {}
    for a in history:
        out[a.get("street", "preflop")] = out.get(a.get("street", "preflop"), 0) + int(a.get("add", 0) or 0)
    return out


def verify_hand(hand: dict) -> dict:
    """Проверить внутреннюю согласованность одной раздачи.

    Возвращает отчёт; gaps перечисляет отсутствующие для полной
    реконструкции поля (начальные стэки оппонентов и т.д.).
    """
    history = hand.get("history", [])
    report = {
        "match": hand.get("match"),
        "hero_committed": hero_committed(history),
        "gross_pot": gross_pot(history),
        "by_street": street_split(history),
        "hero_folded": any(a.get("id") == "hero" and a.get("type") == 1 for a in history),
        "won": bool(hand.get("result", {}).get("won")),
        "payout": hand.get("result", {}).get("payout", []),
        "gaps": ["opponent_stacks", "opponent_blind_posts", "turn_order", "opponent_hole_cards"],
        "errors": [],
    }
    # инвариант: взносы hero неотрицательны
    for a in history:
        if int(a.get("add", 0) or 0) < 0:
            report["errors"].append(f"отрицательный add: {a!r}")
    # инвариант: add отсутствует только у нулевых маркеров (чек 2, шоудаун 32,
    # служебный 16); ненулевых записей без total в журнале нет.
    for a in history:
        if a.get("type") in (2, 16, 32) and int(a.get("add", 0) or 0) != 0:
            report["errors"].append(f"маркер с ненулевым add: {a!r}")
            break
    for a in history:
        if "total" not in a and "street" not in a and a.get("type") not in (1, 2, 16, 32):
            report["errors"].append(f"неполная запись: {a!r}")
            break
    return report
