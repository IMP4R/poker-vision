"""G4: широкий префлоп-вход как сценарное решение, не один pot-odds порог.

Численные implied-odds поля здесь являются приближёнными: без модели будущих
действий соперников нельзя выдавать их за точный EV. Модуль возвращает
прозрачные кандидаты fold/call/raise и показывает, откуда берётся надбавка
за потенциальный будущий банк.
"""

from __future__ import annotations

from dataclasses import dataclass

from solver.capital import CapitalState
from solver.ranges import equity_vs_ranges, full_range, top_percent_range

RANKS = "23456789TJQKA"
BROADWAY = set("TJQKA")


@dataclass(frozen=True)
class PreflopContext:
    pot: int
    call: int
    hero_stack: int
    effective_stack: int
    position: str = "unknown"
    players_behind: int = 0
    aggressive_players_behind: int = 0
    opponents: int = 1
    opponent_vpip: float | None = None
    active_mode: bool = False
    session_budget: int = 0
    active_budget: int = 0

    def validate(self) -> None:
        if self.pot <= 0 or self.call < 0 or self.hero_stack < 0 or self.effective_stack < 0:
            raise ValueError("pot/call/stacks некорректны")
        if self.call > self.hero_stack:
            raise ValueError("call больше hero_stack")
        if self.players_behind < 0 or self.aggressive_players_behind < 0:
            raise ValueError("players_behind неотрицателен")
        if self.aggressive_players_behind > self.players_behind:
            raise ValueError("агрессивных игроков больше игроков за спиной")
        if self.opponents <= 0:
            raise ValueError("нужен хотя бы один соперник")


def classify_starting_hand(hole: tuple[str, str]) -> dict:
    """Классификация стартовой руки для выбора сценария."""
    if len(hole) != 2 or hole[0] == hole[1] or hole[0][0] not in RANKS or hole[1][0] not in RANKS:
        raise ValueError("некорректные две карты")
    r1, r2 = RANKS.index(hole[0][0]), RANKS.index(hole[1][0])
    hi, lo = max(r1, r2), min(r1, r2)
    gap = hi - lo - 1
    pair = r1 == r2
    suited = hole[0][1] == hole[1][1]
    ace = hi == RANKS.index("A")
    broadway = hole[0][0] in BROADWAY and hole[1][0] in BROADWAY
    wheel_ace = ace and lo <= RANKS.index("5")
    if pair:
        category = "pair"
        potential = "set_mining" if lo <= RANKS.index("9") else "overpair_or_set"
    elif suited and ace:
        category, potential = "suited_ace", "nut_flush_and_pair"
    elif suited and gap == 0:
        category, potential = "suited_connector", "straight_flush_draws"
    elif suited and gap <= 2:
        category, potential = "suited_gapper", "straight_flush_potential"
    elif not suited and ace:
        category, potential = "offsuit_ace", "top_pair_dominance_risk"
    elif broadway:
        category, potential = "broadway", "top_pair_and_straight"
    elif gap == 0:
        category, potential = "offsuit_connector", "straight_potential"
    else:
        category, potential = "offsuit_trash", "low_realization"
    # A2-A5 suited has wheel/nut-flush potential; keep it explicit.
    if wheel_ace and suited:
        potential = "nut_flush_and_wheel"
    return {
        "category": category,
        "potential": potential,
        "pair": pair,
        "suited": suited,
        "gap": gap,
        "high_rank": RANKS[hi],
        "low_rank": RANKS[lo],
        "nut_potential": bool(suited and (ace or gap <= 2)),
    }


def _implied_parameters(info: dict, ctx: PreflopContext) -> tuple[float, float, float]:
    """(hit probability, payability, reverse-implied-risk), all heuristic."""
    category = info["category"]
    hit = {
        "pair": 0.118,  # flop set/quads approximation
        "suited_ace": 0.24,
        "suited_connector": 0.20,
        "suited_gapper": 0.16,
        "offsuit_ace": 0.18,
        "broadway": 0.22,
        "offsuit_connector": 0.14,
        "offsuit_trash": 0.06,
    }[category]
    payability = 0.85 if ctx.position in {"button", "cutoff"} else 0.65
    payability += min(0.15, ctx.opponents * 0.03)
    if ctx.effective_stack < 8 * max(ctx.call, 1):
        payability *= 0.55
    reverse_risk = 0.35 if category in {"offsuit_ace", "offsuit_trash"} else 0.12
    if ctx.position in {"small_blind", "big_blind", "unknown"}:
        reverse_risk += 0.08
    return hit, min(payability, 1.0), min(reverse_risk, 1.0)


def preflop_plan(
    hole: tuple[str, str],
    ctx: PreflopContext,
    *,
    trials: int = 2500,
    seed: int = 0,
) -> dict:
    """Построить префлоп-кандидаты с implied-odds надбавкой.

    `call_ev` и `raise_ev` approximate, потому что ответы соперников и будущие
    улицы абстрагированы. Это уже шире текущего call-only советника, но не
    подмена полноценного дерева G5.
    """
    ctx.validate()
    info = classify_starting_hand(hole)
    vpip = ctx.opponent_vpip
    percent = 100.0 if vpip is None else max(5.0, min(100.0, vpip * 100))
    ranges = tuple(top_percent_range(percent) for _ in range(ctx.opponents))
    equity_result = equity_vs_ranges(hole, (), ranges, trials=trials, seed=seed)
    equity = equity_result["equity"]
    required = ctx.call / (ctx.pot + ctx.call) if ctx.call else 0.0
    immediate_ev = equity * (ctx.pot + ctx.call) - ctx.call
    hit, payability, reverse_risk = _implied_parameters(info, ctx)
    future_cap = min(ctx.effective_stack, max(ctx.pot, 1) * (2 if ctx.position in {"button", "cutoff"} else 1))
    implied_bonus = hit * payability * future_cap
    reverse_cost = reverse_risk * ctx.call
    call_ev = immediate_ev + implied_bonus - reverse_cost
    # Players behind reduce the value of passive entry and raise the risk.
    squeeze_penalty = ctx.aggressive_players_behind * max(ctx.call, ctx.pot * 0.05)
    call_ev -= squeeze_penalty
    raise_size = max(ctx.call * 2, ctx.pot // 2, 1)
    raise_fold_credit = 0.12 * ctx.pot if ctx.aggressive_players_behind == 0 else 0.04 * ctx.pot
    raise_ev = immediate_ev + raise_fold_credit - raise_size
    if equity > 0.62 and info["category"] not in {"offsuit_trash", "offsuit_ace"}:
        raise_ev += equity * future_cap * 0.15
    candidates = [
        {"action": "fold", "ev": 0.0, "precision": "baseline"},
        {"action": "call" if ctx.call else "check", "ev": round(call_ev, 4), "size": ctx.call, "precision": "scenario_approximate"},
        {"action": "raise", "ev": round(raise_ev, 4), "size": raise_size, "precision": "scenario_approximate"},
    ]
    candidates.sort(key=lambda x: x["ev"], reverse=True)
    chosen = candidates[0]
    active_override = False
    if not ctx.call:
        chosen = next(x for x in candidates if x["action"] in {"check", "raise"})
    elif ctx.active_mode:
        call_candidate = next(x for x in candidates if x["action"] == "call")
        cheap_vs_stack = ctx.hero_stack > 0 and ctx.call / ctx.hero_stack <= 0.02
        cheap_vs_effective = ctx.effective_stack > 0 and ctx.call / ctx.effective_stack <= 0.05
        acceptable_loss = call_ev >= -0.75 * ctx.call
        playable = info["category"] != "offsuit_trash"
        if cheap_vs_stack and cheap_vs_effective and acceptable_loss and playable:
            chosen = call_candidate
            active_override = chosen is not candidates[0]
    return {
        "chosen": chosen,
        "candidates": candidates,
        "hand": info,
        "equity": round(equity, 4),
        "equity_stderr": round(equity_result["stderr"], 6),
        "required_immediate_equity": round(required, 4),
        "immediate_ev": round(immediate_ev, 4),
        "implied_bonus": round(implied_bonus, 4),
        "reverse_implied_cost": round(reverse_cost, 4),
        "squeeze_penalty": round(squeeze_penalty, 4),
        "future_cap": future_cap,
        "payability": round(payability, 4),
        "precision": "scenario_approximate",
        "active_mode": ctx.active_mode,
        "active_override": active_override,
    }
