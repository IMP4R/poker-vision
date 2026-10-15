"""Наблюдательный режим: советы советника по журналу, ноль кликов.

Ретроспективный прогон: для каждого добровольного решения hero в журнале
восстанавливаем (банк, колл, улицу) из add/total до момента решения,
просим советника и сравниваем с фактически принятым действием.

Ограничения честности:
- противник в совете — агрегат «типичный соперник журнала» (VPIP медианный),
  а не конкретный игрок за столом в той раздаче;
- советы до ривера approximate.
"""

from __future__ import annotations

import json
import statistics

from solver.advisor import advise
from solver.profiles import build_profiles, load_finished, summarize

ACTION_NAME = {1: "fold", 2: "check", 4: "call", 8: "bet"}


def _median_vpip(hands: list[dict]) -> float | None:
    profiles = build_profiles(hands)
    vpips = [summarize(s)["vpip"] for s in profiles.values() if s["hands"] >= 5]
    return statistics.median(vpips) if vpips else None


def hero_decisions(hand: dict) -> list[dict]:
    """Точки решений hero: (street, pot, to_call, taken_type, add, total)."""
    history = hand.get("history", [])
    out = []
    for i, e in enumerate(history):
        if e.get("id") != "hero":
            continue
        typ = e.get("type")
        if typ not in (1, 2, 4, 8) or e.get("blind"):
            continue
        street = e.get("street", "preflop")
        pot = sum(int(x.get("add", 0) or 0) for x in history[:i])
        street_commits: dict[str, int] = {}
        for x in history[:i]:
            if x.get("street", "preflop") != street:
                continue
            street_commits[x.get("id", "")] = street_commits.get(x.get("id", ""), 0) + int(x.get("add", 0) or 0)
        target = max(street_commits.values(), default=0)
        hero_committed = street_commits.get("hero", 0)
        to_call = max(0, target - hero_committed)
        out.append({
            "at": hand.get("at", ""),
            "match": hand.get("match", ""),
            "street": street,
            "board_cards": sum(1 for x in hand.get("board", []) or []),
            "pot": pot,
            "to_call": to_call,
            "taken": ACTION_NAME.get(typ, str(typ)),
            "hero_add": int(e.get("add", 0) or 0),
        })
    return out


def replay(
    journal_path: str = "/home/user/jev-poker/auto-jev.jsonl",
    hands: list[dict] | None = None,
    trials: int = 4000,
    seed: int = 0,
) -> dict:
    """Прогнать советника по всем решениям hero в журнале."""
    if hands is None:
        hands = load_finished(journal_path)
    vpip = _median_vpip(hands)
    rows = []
    for h in hands:
        board_final = h.get("board") or []
        cards = h.get("cards") or []
        if len(cards) != 2:
            continue
        hole = (cards[0], cards[1])
        # Борд на момент решения = префикс финального борда по улице.
        # Будущие карты в совет не попадают никогда.
        street_to_board = {
            "preflop": (),
            "flop": tuple(board_final[:3]),
            "turn": tuple(board_final[:4]),
            "river": tuple(board_final[:5]),
        }
        for d in hero_decisions(h):
            board = street_to_board.get(d["street"])
            if board is None or len(board) < {"preflop": 0, "flop": 3, "turn": 4, "river": 5}[d["street"]]:
                continue  # пробел данных: улица не согласована с бордом
            try:
                advice = advise(
                    hole, board, max(d["pot"], 1), d["to_call"], 10**9,
                    opponent_vpip=vpip, trials=trials, seed=seed,
                )
            except ValueError:
                continue
            taken = d["taken"]
            advice_action = advice["action"]
            # 'bet' советника против фактического 'check'/'bet' hero
            agreed = taken == advice_action or (advice_action == "bet" and taken in ("bet", "check"))
            rows.append({**d, "board_cards": len(board), "advice": advice_action, "agreed": agreed,
                         "advice_ev": advice.get("ev"), "advice_kind": advice.get("kind")})
    agreed_n = sum(1 for r in rows if r["agreed"])
    return {
        "median_vpip": round(vpip, 2) if vpip else None,
        "decisions": len(rows),
        "agreed": agreed_n,
        "agreement": round(agreed_n / len(rows), 3) if rows else None,
        "rows": rows,
    }
