"""Тесты implied-odds сценариев и бюджетного фильтра."""

import pytest

from solver.entry import EntryScenario, entry_budget_gate, speculative_entry_ev


def test_future_bank_can_make_entry_profitable() -> None:
    result = speculative_entry_ev(
        400,
        (
            EntryScenario(0.25, payout=4000, future_cost=800, label="strong_hit"),
            EntryScenario(0.35, payout=0, future_cost=100, label="cheap_exit"),
        ),
        miss_payout=0,
        miss_future_cost=0,
    )
    # 25% сценарий большого банка учитывается, а не теряется в pot odds.
    assert result["ev"] == pytest.approx(365.0)
    assert result["miss_probability"] == pytest.approx(0.4)


def test_entry_rejects_probabilities_over_one() -> None:
    with pytest.raises(ValueError):
        speculative_entry_ev(100, (EntryScenario(0.8, 100), EntryScenario(0.3, 100)))


def test_normal_mode_requires_positive_ev_and_limits() -> None:
    allowed = entry_budget_gate(
        ev=100, entry_cost=400, stack=40_000,
        effective_stack=20_000, session_budget=100_000,
    )
    assert allowed["allowed"] is True
    denied = entry_budget_gate(
        ev=-1, entry_cost=400, stack=40_000,
        effective_stack=20_000, session_budget=100_000,
    )
    assert denied["allowed"] is False


def test_active_mode_allows_only_small_budget_loss() -> None:
    result = entry_budget_gate(
        ev=-80, entry_cost=400, stack=40_000,
        effective_stack=20_000, session_budget=100_000,
        active_mode=True,
    )
    assert result["allowed"] is True and result["exploratory"] is True
    too_expensive = entry_budget_gate(
        ev=-80, entry_cost=3000, stack=40_000,
        effective_stack=20_000, session_budget=100_000,
        active_mode=True,
    )
    assert too_expensive["allowed"] is False
