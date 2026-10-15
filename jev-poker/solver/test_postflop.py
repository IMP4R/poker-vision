"""G5 tests: board texture, outs, postflop candidate families and legal sizes."""

import pytest

from solver.postflop import (
    board_texture,
    executable_size,
    postflop_candidates,
)


def test_board_texture_detects_wet_paired_board() -> None:
    t = board_texture(("Jh", "Th", "9c", "9d"))
    assert t["paired"] is True
    assert t["two_tone"] is True
    assert t["connected"] is True
    assert t["wetness"] > 0.3


def test_flush_draw_produces_improvement_outs() -> None:
    result = postflop_candidates(
        ("Ah", "Kh"), ("2h", "7h", "Qc"),
        pot=1000, to_call=0, stack=5000,
        opponent_vpip=0.8, fold_share=0.4, trials=600, seed=5,
    )
    assert result["draws"]["count"] > 0
    assert result["texture"]["two_tone"] is True
    assert result["precision"] == "approximate"


def test_monster_can_generate_value_action() -> None:
    result = postflop_candidates(
        ("Ah", "Kh"), ("Qh", "Jh", "2h"),
        pot=1200, to_call=0, stack=6000,
        opponent_vpip=0.8, trials=700, seed=6,
    )
    assert result["chosen"]["action"] == "bet"
    assert result["chosen"]["kind"] == "value"


def test_facing_bet_exposes_cheap_exit_and_call_candidates() -> None:
    result = postflop_candidates(
        ("Jh", "Qh"), ("7h", "Ts", "3c"),
        pot=5200, to_call=1000, stack=8000,
        opponent_vpip=1.0, fold_share=0.4, trials=700, seed=7,
    )
    actions = {x["action"] for x in result["candidates"]}
    assert "fold" in actions and "call" in actions
    assert result["required"] > 0


def test_size_is_clamped_to_ui_legal_range() -> None:
    assert executable_size(300, 500, 1000) == {
        "requested": 300, "actual": 500, "clamped": True,
        "precision": "clamped_to_legal_size",
    }
    assert executable_size(700, 500, 1000)["actual"] == 700
    with pytest.raises(ValueError):
        executable_size(500, 1000, 900)
