"""G6: персональные диапазоны и вероятности действий соперников.

Модель deliberately conservative: при малой выборке likelihood остаётся близким
к prior, а при достаточной выборке учитывает street/action/size/profile. Это
механизм обновления, не утверждение о скрытых картах.
"""

from __future__ import annotations

from dataclasses import dataclass

from solver.profiles import summarize
from solver.ranges import full_range, update_range


@dataclass(frozen=True)
class ActionObservation:
    street: str
    action: str
    size_fraction: float = 0.0


@dataclass(frozen=True)
class OpponentModel:
    player_id: str
    summary: dict
    prior_strength: float = 0.5

    @property
    def confidence(self) -> float:
        hands = int(self.summary.get("hands", 0))
        return min(0.9, hands / (hands + 20)) if hands else 0.0

    def action_probability(self, observation: ActionObservation, *, hand_strength: float) -> float:
        """P(action | hand, line) с shrinkage к нейтральному prior."""
        if not 0 <= hand_strength <= 1:
            raise ValueError("hand_strength в [0,1]")
        action = observation.action.lower()
        street = observation.street.lower()
        vpip = float(self.summary.get("vpip", 0.5) or 0.5)
        pfr = float(self.summary.get("pfr", 0.2) or 0.2)
        af = self.summary.get("aggression_factor")
        af = 1.0 if af is None else float(af)
        fold = float(self.summary.get("fold_postflop", 0) or 0)
        aggr = float(self.summary.get("postflop_aggr", 0) or 0)
        calls = float(self.summary.get("postflop_calls", 0) or 0)
        fold_rate = fold / max(1.0, fold + calls + aggr)
        if action in {"raise", "bet", "allin", "aggro"}:
            base = pfr if street == "preflop" else min(0.9, 0.2 + 0.15 * af)
            strength_bias = 0.25 + 0.75 * hand_strength
            size_bias = min(0.25, max(0.0, observation.size_fraction - 0.5) * 0.2)
            estimate = base * strength_bias + size_bias
        elif action in {"call", "check"}:
            base = vpip if street == "preflop" else min(0.85, 0.35 + calls / max(1.0, calls + aggr))
            estimate = base * (0.35 + 0.65 * hand_strength)
        elif action == "fold":
            estimate = max(0.05, fold_rate + (1.0 - hand_strength) * 0.35)
        else:
            estimate = 0.5
        confidence = self.confidence
        return max(0.02, min(0.98, (1 - confidence) * 0.5 + confidence * estimate))


def model_from_profile(player_id: str, raw_profile: dict) -> OpponentModel:
    """Преобразовать сырую статистику или уже готовую summary в модель."""
    if "raise_then_fold" in raw_profile and "went_to_river" in raw_profile:
        summary = summarize(raw_profile)
    else:
        # Live/profile consumers may already provide summarize() output.
        summary = dict(raw_profile)
        summary.setdefault("hands", 0)
        summary.setdefault("vpip", 0.5)
        summary.setdefault("pfr", 0.2)
        summary.setdefault("aggression_factor", None)
        summary.setdefault("fold_postflop", 0)
        summary.setdefault("postflop_aggr", 0)
        summary.setdefault("postflop_calls", 0)
    return OpponentModel(player_id, summary)


def update_personal_range(
    current_range: dict[tuple[str, str], float],
    model: OpponentModel,
    observation: ActionObservation,
    *,
    strength_fn=None,
) -> dict[tuple[str, str], float]:
    """Обновить диапазон одного игрока после конкретного действия.

    `strength_fn(combo)` возвращает нормированную силу комбинации относительно
    board/range context. По умолчанию используется только ранг первой карты,
    поэтому для боевой оценки вызывающий код должен передать evaluator-aware
    функцию.
    """
    if strength_fn is None:
        strength_fn = lambda combo: ("23456789TJQKA".index(combo[0][0]) + "23456789TJQKA".index(combo[1][0])) / 24
    likelihood = {
        combo: model.action_probability(observation, hand_strength=max(0.0, min(1.0, strength_fn(combo))))
        for combo in current_range
    }
    return update_range(current_range, likelihood)


def build_personal_ranges(
    player_profiles: dict[str, dict],
    observations: dict[str, tuple[ActionObservation, ...]],
) -> dict[str, dict[tuple[str, str], float]]:
    """Создать и последовательно обновить отдельный range каждого игрока."""
    result: dict[str, dict[tuple[str, str], float]] = {}
    for player_id, raw in player_profiles.items():
        model = model_from_profile(player_id, raw)
        rng = full_range()
        for observation in observations.get(player_id, ()):
            rng = update_personal_range(rng, model, observation)
        result[player_id] = rng
    return result
