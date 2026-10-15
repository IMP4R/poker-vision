"""G6 tests for personal opponent models and per-player ranges."""

from solver.opponent_model import (
    ActionObservation,
    build_personal_ranges,
    model_from_profile,
    update_personal_range,
)
from solver.ranges import full_range


def profile(**kw):
    base = {
        "hands": 20, "vpip": 0.6, "pfr": 0.25,
        "aggression_factor": 1.2, "fold_postflop": 3,
        "postflop_aggr": 5, "postflop_calls": 8,
    }
    base.update(kw)
    return base


def test_small_sample_shrinks_action_probability() -> None:
    unknown = model_from_profile("u", profile(hands=0, pfr=0.9))
    known = model_from_profile("k", profile(hands=100, pfr=0.9))
    obs = ActionObservation("preflop", "raise", 0.75)
    assert abs(unknown.action_probability(obs, hand_strength=1) - 0.5) < abs(
        known.action_probability(obs, hand_strength=1) - 0.5
    )


def test_action_update_keeps_normalized_personal_range() -> None:
    rng = full_range()
    model = model_from_profile("vill", profile(hands=50, pfr=0.5))
    updated = update_personal_range(rng, model, ActionObservation("preflop", "raise", 0.8))
    assert abs(sum(updated.values()) - 1) < 1e-9
    assert updated[("As", "Ah")] > updated[("2c", "7d")]


def test_each_player_gets_separate_range() -> None:
    result = build_personal_ranges(
        {"tight": profile(pfr=0.1), "wide": profile(pfr=0.8)},
        {
            "tight": (ActionObservation("preflop", "raise", 0.8),),
            "wide": (ActionObservation("preflop", "call", 0.2),),
        },
    )
    assert set(result) == {"tight", "wide"}
    assert result["tight"] != result["wide"]
    assert abs(sum(result["tight"].values()) - 1) < 1e-9
