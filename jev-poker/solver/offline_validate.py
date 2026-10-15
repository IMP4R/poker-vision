"""G7: воспроизводимая offline replay/AB-проверка политики.

Сравнивает baseline advisor с новой candidate-policy на фиксированном журнале.
Будущие карты отбрасываются по улице; неизвестные стэки явно заменяются
консервативным параметром и помечаются в отчёте.
"""

from __future__ import annotations

from collections import Counter

from solver.observe import hero_decisions
from solver.postflop import postflop_candidates
from solver.preflop import PreflopContext, preflop_plan
from solver.profiles import load_finished


def _action_matches(actual: str, chosen: str) -> bool:
    if actual == chosen:
        return True
    # check and bet are distinct decisions; only check/check and bet/bet agree.
    return False


def validate_hands(
    hands: list[dict],
    *,
    trials: int = 500,
    seed: int = 0,
    assumed_stack: int = 100_000,
    assumed_effective_stack: int = 20_000,
) -> dict:
    """Запустить новую policy по журналу без кликов и без будущих карт."""
    rows: list[dict] = []
    skipped = Counter()
    for hand in hands:
        cards = hand.get("cards") or []
        final_board = tuple(hand.get("board") or [])
        if len(cards) != 2:
            skipped["missing_hero_cards"] += 1
            continue
        hole = (cards[0], cards[1])
        prefixes = {"preflop": (), "flop": final_board[:3], "turn": final_board[:4], "river": final_board[:5]}
        for decision in hero_decisions(hand):
            street = decision["street"]
            board = tuple(prefixes.get(street, ()))
            required_cards = {"preflop": 0, "flop": 3, "turn": 4, "river": 5}.get(street, 99)
            if len(board) < required_cards:
                skipped["incomplete_board"] += 1
                continue
            try:
                if street == "preflop":
                    result = preflop_plan(
                        hole,
                        PreflopContext(
                            pot=max(1, decision["pot"]),
                            call=decision["to_call"],
                            hero_stack=assumed_stack,
                            effective_stack=assumed_effective_stack,
                            position="unknown",
                            opponents=1,
                        ),
                        trials=trials,
                        seed=seed,
                    )
                else:
                    result = postflop_candidates(
                        hole,
                        board,
                        pot=max(1, decision["pot"]),
                        to_call=decision["to_call"],
                        stack=assumed_stack,
                        trials=trials,
                        seed=seed,
                    )
            except (ValueError, KeyError):
                skipped["invalid_state"] += 1
                continue
            chosen = result["chosen"]["action"]
            rows.append({
                "match": decision["match"],
                "street": street,
                "board_cards": len(board),
                "actual": decision["taken"],
                "chosen": chosen,
                "agreed": _action_matches(decision["taken"], chosen),
                "ev": result["chosen"].get("ev"),
                "precision": result.get("precision"),
                "candidates": result.get("candidates", []),
            })
    agreement = sum(r["agreed"] for r in rows) / len(rows) if rows else None
    by_street: dict[str, dict] = {}
    for street in ("preflop", "flop", "turn", "river"):
        subset = [r for r in rows if r["street"] == street]
        by_street[street] = {
            "decisions": len(subset),
            "agreed": sum(r["agreed"] for r in subset),
            "agreement": sum(r["agreed"] for r in subset) / len(subset) if subset else None,
        }
    return {
        "decisions": len(rows),
        "agreed": sum(r["agreed"] for r in rows),
        "agreement": agreement,
        "by_street": by_street,
        "skipped": dict(skipped),
        "assumptions": {
            "stack": assumed_stack,
            "effective_stack": assumed_effective_stack,
            "precision": "assumed_stack_and_scenario_approximate",
        },
        "rows": rows,
    }


def validate_journal(path: str, **kwargs) -> dict:
    return validate_hands(load_finished(path), **kwargs)
