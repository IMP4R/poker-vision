"""Экономика широкого входа и implied odds.

Это не заменяет дерево раздачи. Модуль считает сценарную ценность входа,
когда прибыль может прийти позднее: через сильное попадание, кражу банка или
дешёвый выход. Все суммы payout_* — валовая выплата игроку, а costs_* —
дополнительные вложения после текущего решения.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EntryScenario:
    """Один взаимоисключающий исход продолжения."""

    probability: float
    payout: float
    future_cost: float = 0.0
    label: str = "scenario"

    @property
    def net_after_entry(self) -> float:
        return self.payout - self.future_cost


def speculative_entry_ev(
    entry_cost: float,
    scenarios: tuple[EntryScenario, ...],
    *,
    miss_payout: float = 0.0,
    miss_future_cost: float = 0.0,
) -> dict:
    """EV входа с учётом будущих банков и будущих вложений.

    `entry_cost` списывается во всех исходах. Переданные сценарии должны быть
    взаимоисключающими; остаток вероятности считается miss. `payout` —
    валовая выплата из банка, а не прибыль. Поэтому формула честно вычитает
    entry_cost и будущие затраты.
    """
    if entry_cost < 0:
        raise ValueError("entry_cost неотрицателен")
    if not scenarios:
        raise ValueError("нужен хотя бы один сценарий")
    total_p = 0.0
    for s in scenarios:
        if not 0 <= s.probability <= 1:
            raise ValueError("вероятности в [0,1]")
        if s.payout < 0 or s.future_cost < 0:
            raise ValueError("выплата и будущие затраты неотрицательны")
        total_p += s.probability
    if total_p > 1 + 1e-12:
        raise ValueError("сумма вероятностей больше единицы")
    miss_p = max(0.0, 1.0 - total_p)
    contribution = sum(s.probability * s.net_after_entry for s in scenarios)
    contribution += miss_p * (miss_payout - miss_future_cost)
    ev = contribution - entry_cost
    return {
        "ev": round(ev, 4),
        "entry_cost": entry_cost,
        "scenario_probability": round(total_p, 6),
        "miss_probability": round(miss_p, 6),
        "breakdown": {
            s.label: round(s.probability * s.net_after_entry, 4)
            for s in scenarios
        },
        "miss_contribution": round(miss_p * (miss_payout - miss_future_cost), 4),
        "precision": "scenario_approximate",
    }


def entry_budget_gate(
    *,
    ev: float,
    entry_cost: int,
    stack: int,
    effective_stack: int,
    session_budget: int,
    active_mode: bool = False,
    max_stack_fraction: float = 0.05,
    max_session_fraction: float = 0.01,
) -> dict:
    """Бюджетный фильтр: общий баланс не превращает минус в плюс.

    Основной режим требует EV > 0. `active_mode` разрешает лишь небольшой
    отрицательный EV, если цена входа одновременно мала относительно стэка,
    эффективного стэка и бюджета сессии.
    """
    if min(entry_cost, stack, effective_stack, session_budget) < 0:
        raise ValueError("суммы неотрицательны")
    if stack == 0 or effective_stack == 0 or session_budget == 0:
        return {"allowed": False, "reason": "нет доступного бюджета", "precision": "budget_gate"}
    if not 0 < max_stack_fraction <= 1 or not 0 < max_session_fraction <= 1:
        raise ValueError("лимиты долей в (0,1]")
    stack_ok = entry_cost <= stack * max_stack_fraction
    effective_ok = entry_cost <= effective_stack * max_stack_fraction
    session_ok = entry_cost <= session_budget * max_session_fraction
    positive = ev > 0
    exploratory = active_mode and ev >= -entry_cost * 0.25 and stack_ok and effective_ok and session_ok
    allowed = positive and stack_ok and effective_ok and session_ok or exploratory
    reason = "положительный EV и лимиты бюджета" if positive and allowed else (
        "активный режим: небольшой отрицательный EV в пределах бюджета"
        if exploratory else "EV или бюджетный лимит не пройден"
    )
    return {
        "allowed": allowed,
        "reason": reason,
        "positive_ev": positive,
        "exploratory": exploratory,
        "stack_fraction": round(entry_cost / stack, 6),
        "effective_fraction": round(entry_cost / effective_stack, 6),
        "session_fraction": round(entry_cost / session_budget, 6),
        "precision": "budget_gate",
    }
