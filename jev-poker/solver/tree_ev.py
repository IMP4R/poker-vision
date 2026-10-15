"""Минимальный универсальный EV-узел ограниченного дерева действий."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class Outcome:
    probability: float
    payout: float
    future_cost: float = 0.0
    source: str = "showdown"

    @property
    def net(self) -> float:
        return self.payout - self.future_cost


@dataclass(frozen=True)
class ActionBranch:
    action: str
    immediate_cost: float
    outcomes: tuple[Outcome, ...]
    size: int | None = None
    precision: str = "scenario_approximate"


def evaluate_branch(branch: ActionBranch) -> dict:
    if branch.immediate_cost < 0:
        raise ValueError("immediate_cost неотрицателен")
    total_p = sum(o.probability for o in branch.outcomes)
    if any(not 0 <= o.probability <= 1 for o in branch.outcomes):
        raise ValueError("вероятности в [0,1]")
    if abs(total_p - 1.0) > 1e-9:
        raise ValueError("исходы ветки должны суммироваться в 1")
    expected_payout = sum(o.probability * o.payout for o in branch.outcomes)
    expected_future_cost = sum(o.probability * o.future_cost for o in branch.outcomes)
    ev = expected_payout - branch.immediate_cost - expected_future_cost
    by_source: dict[str, float] = {}
    for o in branch.outcomes:
        by_source[o.source] = by_source.get(o.source, 0.0) + o.probability * o.net
    return {
        "action": branch.action,
        "size": branch.size,
        "ev": round(ev, 6),
        "expected_payout": round(expected_payout, 6),
        "expected_future_cost": round(expected_future_cost, 6),
        "immediate_cost": branch.immediate_cost,
        "by_source": {k: round(v, 6) for k, v in by_source.items()},
        "precision": branch.precision,
    }


def choose_action(branches: Iterable[ActionBranch], *, active_tolerance: float = 0.0) -> dict:
    """Выбрать max-EV; при близких EV предпочесть более активную ветку.

    active_tolerance — абсолютная допустимая потеря EV. Активность задаётся
    только порядком действий, но точное EV каждой ветки остаётся видимым.
    """
    evaluated = [evaluate_branch(b) for b in branches]
    if not evaluated:
        raise ValueError("нет ветвей")
    best_ev = max(x["ev"] for x in evaluated)
    candidates = [x for x in evaluated if x["ev"] >= best_ev - active_tolerance]
    activity = {"fold": 0, "check": 1, "call": 2, "bet": 3, "raise": 4, "allin": 5}
    chosen = max(candidates, key=lambda x: (activity.get(x["action"], 0), x["ev"]))
    return {
        "chosen": chosen,
        "best_ev": best_ev,
        "active_tolerance": active_tolerance,
        "branches": sorted(evaluated, key=lambda x: x["ev"], reverse=True),
        "precision": "finite_scenario_tree",
    }
