"""Капитал раздачи: стэки, effective stack и бюджеты активности."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CapitalState:
    pot: int
    hero_stack: int
    opponent_stacks: dict[str, int]
    session_budget: int
    active_budget: int = 0

    def __post_init__(self) -> None:
        values = [self.pot, self.hero_stack, self.session_budget, self.active_budget, *self.opponent_stacks.values()]
        if any(v < 0 for v in values):
            raise ValueError("капитал неотрицателен")

    def effective_stack(self, opponent_id: str) -> int:
        if opponent_id not in self.opponent_stacks:
            raise KeyError(f"неизвестен стэк {opponent_id}")
        return min(self.hero_stack, self.opponent_stacks[opponent_id])

    def max_collectable(self, eligible_opponents: tuple[str, ...]) -> int:
        """Верхняя граница выплаты hero без моделирования side pots.

        Текущий банк уже существует. От каждого оппонента дополнительно можно
        получить не больше effective stack. Это cap, а не прогноз выплаты.
        """
        return self.pot + sum(self.effective_stack(pid) for pid in eligible_opponents)

    def price_context(self, cost: int, opponent_id: str | None = None) -> dict:
        if cost < 0:
            raise ValueError("стоимость неотрицательна")
        effective = self.hero_stack if opponent_id is None else self.effective_stack(opponent_id)
        return {
            "cost": cost,
            "pot_fraction": cost / self.pot if self.pot else None,
            "hero_stack_fraction": cost / self.hero_stack if self.hero_stack else None,
            "effective_stack_fraction": cost / effective if effective else None,
            "session_fraction": cost / self.session_budget if self.session_budget else None,
            "active_fraction": cost / self.active_budget if self.active_budget else None,
            "effective_stack": effective,
            "precision": "exact_from_stacks",
        }
