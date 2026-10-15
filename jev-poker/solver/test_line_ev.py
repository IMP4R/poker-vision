"""Tests for complete continuation-line EV."""

import pytest

from solver.line_ev import ContinuationNode, LineLeaf, compare_lines, evaluate_line, summarize_line


def test_future_cost_and_payout_are_probability_weighted() -> None:
    line = ContinuationNode(
        "flop", "hero", (
            ("fold", 0.40, LineLeaf(1.0, payout=0, future_cost=0, folded_opponents=1, label="steal")),
            ("continue", 0.60, ContinuationNode(
                "turn", "villain", (
                    ("pay", 0.50, LineLeaf(1.0, payout=2400, future_cost=900, showdown=True, label="showdown_win")),
                    ("pressure", 0.50, LineLeaf(1.0, payout=0, future_cost=200, folded_opponents=1, label="exit")),
                ),
            )),
        ),
    )
    result = evaluate_line(line, entry_cost=400)
    summary = summarize_line(result)
    assert summary["ev"] == pytest.approx(-10.0)
    assert summary["expected_payout"] == pytest.approx(720.0)
    assert summary["expected_future_cost"] == pytest.approx(330.0)
    assert summary["fold_equity_probability"] == pytest.approx(0.7)
    assert summary["showdown_probability"] == pytest.approx(0.3)


def test_probabilities_must_sum_at_each_node() -> None:
    with pytest.raises(ValueError):
        evaluate_line(ContinuationNode("flop", "hero", (("a", .2, LineLeaf(1, label="a")),)))


def test_compare_complete_lines_prefers_future_profitable_call() -> None:
    fold = LineLeaf(1.0, payout=0, label="fold")
    call = ContinuationNode("flop", "hero", (
        ("hit", .25, LineLeaf(1, payout=4000, future_cost=800, showdown=True, label="hit")),
        ("miss", .75, LineLeaf(1, payout=0, future_cost=100, label="miss")),
    ))
    report = compare_lines({"fold": fold, "call": call}, entry_cost=400)
    assert report["chosen"] == "call"
    assert report["lines"]["call"]["ev"] > report["lines"]["fold"]["ev"]


def test_multiway_fold_equity_is_explicit() -> None:
    line = ContinuationNode("flop", "villains", (
        ("one_folds", .5, LineLeaf(1, payout=300, folded_opponents=1, label="one")),
        ("both_fold", .5, LineLeaf(1, payout=500, folded_opponents=2, label="both")),
    ))
    summary = summarize_line(evaluate_line(line, entry_cost=100))
    assert summary["fold_equity_probability"] == pytest.approx(1.0)
    assert summary["ev"] == pytest.approx(300.0)
