"""Мост: состояние раздачи -> локальный советник -> JSON-решение.

Читает JSON из stdin, печатает JSON. Никакого Jev/NanoGPT: только
solver.advisor поверх phevaluator. ОшибкиAdvisor отдаются как
{"action":"fold","error":...} — падение математики не должно
останавливать контроллер, но помечается в журнале.
"""

from __future__ import annotations

import json
import sys

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from solver.advisor import advise
from solver.preflop import PreflopContext, preflop_plan


def main() -> None:
    req = json.load(sys.stdin)
    hole = tuple(req["hole"])
    board = tuple(req.get("board", []))
    to_call = int(req.get("to_call", 0))
    stack = int(req.get("stack", 0))
    clamped = False
    if to_call > stack and stack > 0:
        to_call = stack  # олл-ин: советник считает по доступной сумме
        clamped = True
    try:
        if len(board) == 0:
            plan = preflop_plan(
                hole,
                PreflopContext(
                    pot=max(int(req.get("pot", 0)), 1),
                    call=to_call,
                    hero_stack=stack,
                    effective_stack=max(0, int(req.get("effective_stack", stack))),
                    position=str(req.get("position", "unknown")),
                    players_behind=max(0, int(req.get("players_behind", 0))),
                    aggressive_players_behind=max(0, int(req.get("aggressive_players_behind", 0))),
                    opponents=max(1, int(req.get("opponents", 1))),
                    opponent_vpip=req.get("opponent_vpip"),
                    active_mode=bool(req.get("active_mode", True)),
                    session_budget=max(0, int(req.get("session_budget", 0))),
                    active_budget=max(0, int(req.get("active_budget", 0))),
                ),
                trials=int(req.get("trials", 2500)),
                seed=int(req.get("seed", 0)),
            )
            chosen = plan["chosen"]
            advice = {
                "action": chosen["action"],
                "reason": (
                    f"wide-entry {plan['hand']['category']}: EV {chosen['ev']:+.1f}, "
                    f"implied {plan['implied_bonus']:+.1f}, immediate {plan['immediate_ev']:+.1f}"
                ),
                "ev": chosen["ev"],
                "equity": plan["equity"],
                "required": plan["required_immediate_equity"],
                "implied_bonus": plan["implied_bonus"],
                "reverse_implied_cost": plan["reverse_implied_cost"],
                "hand_category": plan["hand"]["category"],
                "kind": "wide_entry",
                "size": chosen.get("size"),
                "precision": plan["precision"],
                "candidates": plan["candidates"],
            }
        else:
            advice = advise(
                hole, board,
                pot_before=max(int(req.get("pot", 0)), 1),
                to_call=to_call,
                stack=stack,
                opponent_vpip=req.get("opponent_vpip"),
                opponent_aggressive_streets=int(req.get("aggressive_streets", 0)),
                opponents=max(1, int(req.get("opponents", 1))),
                trials=int(req.get("trials", 6000)),
                seed=int(req.get("seed", 0)),
            )
        advice["clamped_allin"] = clamped
    except Exception as exc:  # noqa: BLE001 — мост обязан отвечать всегда
        advice = {"action": "fold", "error": str(exc), "precision": "error_fallback"}
    print(json.dumps(advice, ensure_ascii=False))


if __name__ == "__main__":
    main()
