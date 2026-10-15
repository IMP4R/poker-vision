"""Human-gated G9 launch policy.

This module only authorizes a run when all safety conditions are explicit. It
never starts Node, opens a browser, clicks, buys chips, or joins tournaments.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LaunchRequest:
    human_authorized: bool
    jev_disabled: bool
    purchases_disabled: bool
    tournaments_disabled: bool
    g8_snapshot_confirmed: bool
    solver_tests_passed: bool
    controllers_stopped: bool
    play_money_only: bool = True
    max_hands: int = 0
    active_budget: int = 0


def authorize_launch(request: LaunchRequest) -> dict:
    checks = {
        "human_authorized": request.human_authorized,
        "jev_disabled": request.jev_disabled,
        "purchases_disabled": request.purchases_disabled,
        "tournaments_disabled": request.tournaments_disabled,
        "g8_snapshot_confirmed": request.g8_snapshot_confirmed,
        "solver_tests_passed": request.solver_tests_passed,
        "controllers_stopped": request.controllers_stopped,
        "play_money_only": request.play_money_only,
        # Play-money: 0 означает «без искусственного лимита».
        "max_hands_valid": request.max_hands >= 0,
        "active_budget_valid": request.active_budget >= 0,
    }
    failures = [name for name, ok in checks.items() if not ok]
    return {
        "authorized": not failures,
        "checks": checks,
        "failures": failures,
        "mode": "g9_play_money" if not failures else "blocked",
        "precision": "explicit_safety_gate",
    }


def can_take_action(*, gate: dict, action: str, purchase: bool = False, tournament: bool = False) -> dict:
    """Fail closed on every action unless launch gate and hard restrictions pass."""
    errors = []
    if not gate.get("authorized"):
        errors.append("launch_gate_not_authorized")
    if purchase:
        errors.append("chip_purchase_forbidden")
    if tournament:
        errors.append("tournament_forbidden")
    if action not in {"fold", "check", "call", "raise"}:
        errors.append("unknown_game_action")
    return {"allowed": not errors, "errors": errors, "action": action, "precision": "explicit_safety_gate"}
