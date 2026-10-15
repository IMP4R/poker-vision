"""Shadow replay adapter for line-EV reports, no clicks."""

from __future__ import annotations

from collections import Counter

from solver.decision_bridge import advise_snapshot
from solver.observation import ObservationSnapshot
from solver.observe import hero_decisions
from solver.profiles import load_finished


def shadow_replay(hands: list[dict], *, trials: int = 200, seed: int = 0) -> dict:
    rows = []
    skipped = Counter()
    for hand in hands:
        cards = hand.get("cards") or []
        board = tuple(hand.get("board") or [])
        if len(cards) != 2:
            skipped["missing_cards"] += 1
            continue
        for d in hero_decisions(hand):
            prefix = {"preflop": 0, "flop": 3, "turn": 4, "river": 5}[d["street"]]
            current_board = board[:prefix]
            allowed = ("check",) if d["to_call"] == 0 else ("fold", "call")
            snapshot = ObservationSnapshot(
                street=d["street"], board=current_board, pot=max(1, d["pot"]),
                to_call=d["to_call"], hero_stack=100_000,
                allowed_actions=allowed, min_raise=None,
                gross_contributions=max(1, d["pot"]),
            )
            report = advise_snapshot(snapshot, (cards[0], cards[1]), trials=trials, seed=seed)
            if not report["valid"]:
                skipped["invalid_snapshot"] += 1
                continue
            rows.append({
                "match": d["match"], "street": d["street"],
                "actual": d["taken"], "chosen": report["chosen"],
                "line_ev": report["line_ev"], "validation": report["validation"],
            })
    return {
        "decisions": len(rows),
        "skipped": dict(skipped),
        "rows": rows,
        "chosen_counts": dict(Counter(r["chosen"] for r in rows)),
        "precision": "shadow_replay_scenario_approximate",
    }


def shadow_replay_journal(path: str = "/home/user/jev-poker/auto-jev.jsonl", **kwargs) -> dict:
    return shadow_replay(load_finished(path), **kwargs)
