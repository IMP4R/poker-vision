"""Read-only bridge: protocol snapshot -> policy candidates -> line-EV report.

The bridge is intentionally not wired to clicks. It validates the snapshot,
then attaches a finite-line report to the existing preflop/postflop candidates.
"""

from __future__ import annotations

from solver.line_ev import ContinuationNode, LineLeaf, compare_lines
from solver.observation import ObservationSnapshot, validate_snapshot
from solver.postflop import postflop_candidates
from solver.preflop import PreflopContext, preflop_plan


def _candidate_line(action: str, ev: float, *, entry_cost: float) -> LineLeaf:
    # Convert a candidate EV into an auditable terminal line without inventing
    # hidden payouts: the candidate remains a scenario estimate, not exact EV.
    return LineLeaf(1.0, payout=max(0.0, ev + entry_cost), future_cost=max(0.0, -ev), label=action)


def advise_snapshot(
    snapshot: ObservationSnapshot,
    hole: tuple[str, str],
    *,
    opponent_vpip: float | None = None,
    opponents: int = 1,
    position: str = "unknown",
    trials: int = 500,
    seed: int = 0,
) -> dict:
    """Produce a validated, no-click decision report from one protocol snapshot."""
    validation = validate_snapshot(snapshot)
    if not validation["valid"]:
        return {"valid": False, "validation": validation, "precision": "invalid_snapshot"}
    if snapshot.street == "preflop":
        policy = preflop_plan(
            hole,
            PreflopContext(
                pot=snapshot.pot,
                call=snapshot.to_call,
                hero_stack=snapshot.hero_stack,
                effective_stack=snapshot.hero_stack,
                position=position,
                opponents=opponents,
                opponent_vpip=opponent_vpip,
            ),
            trials=trials,
            seed=seed,
        )
    else:
        policy = postflop_candidates(
            hole,
            snapshot.board,
            pot=snapshot.pot,
            to_call=snapshot.to_call,
            stack=snapshot.hero_stack,
            opponent_vpip=opponent_vpip,
            opponents=opponents,
            position=position,
            trials=trials,
            seed=seed,
        )
    entry = snapshot.to_call
    lines = {
        candidate["action"]: _candidate_line(candidate["action"], float(candidate.get("ev", 0.0)), entry_cost=entry)
        for candidate in policy["candidates"]
        if candidate["action"] in snapshot.allowed_actions or candidate["action"] in {"fold", "check"}
    }
    if not lines:
        return {"valid": False, "validation": validation, "error": "no legal policy candidates", "precision": "error_fallback"}
    line_report = compare_lines(lines, entry_cost=entry)
    chosen = line_report["chosen"]
    # Never allow the abstract line model to override protocol legality.
    if chosen not in snapshot.allowed_actions:
        legal = [a for a in snapshot.allowed_actions if a in line_report["lines"]]
        chosen = max(legal, key=lambda a: line_report["lines"][a]["ev"]) if legal else snapshot.allowed_actions[0]
    return {
        "valid": True,
        "validation": validation,
        "policy": policy,
        "line_ev": line_report,
        "chosen": chosen,
        "precision": "finite_tree_over_scenario_candidates",
    }
