"""G3/G5/G6 integration: expected value of a complete continuation line.

The caller supplies mutually exclusive chance/action branches. This module does
not invent hidden cards; it makes future payout, fold equity, opponent response,
and future investment explicit and auditable.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class LineLeaf:
    probability: float
    payout: float = 0.0
    future_cost: float = 0.0
    folded_opponents: int = 0
    showdown: bool = False
    label: str = "leaf"

    def net(self, entry_cost: float) -> float:
        return self.payout - entry_cost - self.future_cost


@dataclass(frozen=True)
class ContinuationNode:
    street: str
    actor: str
    branches: tuple[tuple[str, float, "ContinuationNode | LineLeaf"], ...] = field(default_factory=tuple)


def _validate_probability(probability: float, label: str) -> None:
    if not 0 <= probability <= 1:
        raise ValueError(f"{label}: probability в [0,1]")


def evaluate_line(
    node: ContinuationNode | LineLeaf,
    *,
    entry_cost: float = 0.0,
    probability: float = 1.0,
) -> dict:
    """Рекурсивно посчитать EV всей линии до терминального исхода."""
    if entry_cost < 0 or probability < 0:
        raise ValueError("entry_cost/probability неотрицательны")
    if isinstance(node, LineLeaf):
        _validate_probability(node.probability, node.label)
        weight = probability * node.probability
        value = node.net(entry_cost)
        return {
            "ev": weight * value,
            "probability": weight,
            "leaves": [{
                "label": node.label,
                "probability": weight,
                "net": value,
                "payout": node.payout,
                "future_cost": node.future_cost,
                "folded_opponents": node.folded_opponents,
                "showdown": node.showdown,
            }],
        }
    if not node.branches:
        raise ValueError(f"пустой узел {node.street}/{node.actor}")
    total = sum(branch[1] for branch in node.branches)
    if abs(total - 1.0) > 1e-9:
        raise ValueError(f"вероятности узла {node.street} не суммируются в 1: {total}")
    ev = 0.0
    leaves = []
    for label, branch_probability, child in node.branches:
        _validate_probability(branch_probability, label)
        result = evaluate_line(child, entry_cost=entry_cost, probability=probability * branch_probability)
        ev += result["ev"]
        for leaf in result["leaves"]:
            leaf["path"] = f"{node.actor}:{label}" + (f"/{leaf['path']}" if leaf.get("path") else "")
            leaves.append(leaf)
    return {"ev": ev, "probability": probability, "leaves": leaves}


def summarize_line(result: dict) -> dict:
    """Декомпозировать полный EV по выплате, затратам и fold equity."""
    leaves = result.get("leaves", [])
    payout = sum(x["probability"] * x["payout"] for x in leaves)
    future_cost = sum(x["probability"] * x["future_cost"] for x in leaves)
    fold_probability = sum(x["probability"] for x in leaves if x["folded_opponents"] > 0)
    showdown_probability = sum(x["probability"] for x in leaves if x["showdown"])
    return {
        "ev": round(result["ev"], 6),
        "expected_payout": round(payout, 6),
        "expected_future_cost": round(future_cost, 6),
        "entry_cost": round(result["probability"] and (payout - future_cost - result["ev"]) / result["probability"], 6),
        "fold_equity_probability": round(fold_probability, 6),
        "showdown_probability": round(showdown_probability, 6),
        "leaves": len(leaves),
        "precision": "finite_continuation_tree",
    }


def compare_lines(lines: dict[str, ContinuationNode | LineLeaf], *, entry_cost: float = 0.0) -> dict:
    """Сравнить fold/call/bet/raise complete-line EV."""
    if not lines:
        raise ValueError("нет линий")
    evaluated = {}
    for action, line in lines.items():
        evaluated[action] = summarize_line(evaluate_line(line, entry_cost=entry_cost))
    chosen = max(evaluated, key=lambda action: evaluated[action]["ev"])
    return {"chosen": chosen, "lines": evaluated, "precision": "finite_continuation_tree"}
