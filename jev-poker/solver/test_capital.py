"""Тесты модели капитала."""

import pytest

from solver.capital import CapitalState


def test_effective_stack_and_collectable_cap() -> None:
    c = CapitalState(1000, 10000, {"tight": 3000, "deep": 20000}, 50000, 2000)
    assert c.effective_stack("tight") == 3000
    assert c.effective_stack("deep") == 10000
    assert c.max_collectable(("tight", "deep")) == 14000


def test_price_context_separates_all_capital_scales() -> None:
    c = CapitalState(600, 40000, {"v": 20000}, 100000, 5000)
    p = c.price_context(400, "v")
    assert p["pot_fraction"] == pytest.approx(2 / 3)
    assert p["hero_stack_fraction"] == pytest.approx(0.01)
    assert p["effective_stack_fraction"] == pytest.approx(0.02)
    assert p["session_fraction"] == pytest.approx(0.004)


def test_unknown_stack_fails_closed() -> None:
    c = CapitalState(100, 1000, {}, 5000)
    with pytest.raises(KeyError):
        c.effective_stack("missing")
