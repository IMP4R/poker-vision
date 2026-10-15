"""Тесты конечного дерева EV."""

import pytest

from solver.tree_ev import ActionBranch, Outcome, choose_action, evaluate_branch


def test_branch_counts_full_future_line() -> None:
    call = ActionBranch("call", 400, (
        Outcome(.25, payout=4000, future_cost=800, source="strong_hit"),
        Outcome(.35, payout=0, future_cost=100, source="cheap_exit"),
        Outcome(.40, payout=0, future_cost=0, source="miss"),
    ))
    assert evaluate_branch(call)["ev"] == pytest.approx(365.0)


def test_choose_max_ev_and_active_near_tie() -> None:
    fold = ActionBranch("fold", 0, (Outcome(1, 0, 0, "fold"),))
    call = ActionBranch("call", 10, (Outcome(1, 12, 0, "showdown"),))
    bet = ActionBranch("bet", 20, (Outcome(1, 21.5, 0, "fold_equity"),), size=20)
    assert choose_action((fold, call, bet))["chosen"]["action"] == "call"
    assert choose_action((fold, call, bet), active_tolerance=1)["chosen"]["action"] == "bet"


def test_invalid_probability_rejected() -> None:
    bad = ActionBranch("call", 10, (Outcome(.7, 20), Outcome(.4, 0)))
    with pytest.raises(ValueError):
        evaluate_branch(bad)
