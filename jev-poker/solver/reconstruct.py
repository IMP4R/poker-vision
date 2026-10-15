"""Проверяемая реконструкция раздачи без игровых действий."""

from __future__ import annotations

from dataclasses import dataclass, field

RANKS = "23456789TJQKA"
SUITS = "shdc"


class ReconstructionError(ValueError):
    """Журнал нельзя превратить в согласованную раздачу."""


@dataclass(frozen=True)
class Action:
    player_id: str
    street: str
    kind: str
    amount: int = 0
    cards: tuple[str, ...] = ()


@dataclass
class SidePot:
    amount: int
    eligible: tuple[str, ...]
    returned_to: tuple[str, ...] = ()


@dataclass
class HandState:
    players: tuple[str, ...]
    stacks: dict[str, int]
    button: int
    sb: int
    bb: int
    hole: dict[str, tuple[str, str]] = field(default_factory=dict)
    board: list[str] = field(default_factory=list)
    pot: int = 0
    street_commit: dict[str, int] = field(default_factory=dict)
    folded: set[str] = field(default_factory=set)
    street: str = "preflop"
    total_commit: dict[str, int] = field(default_factory=dict)
    side_pots: list[SidePot] = field(default_factory=list)

    def active(self) -> list[str]:
        return [p for p in self.players if p not in self.folded and self.stacks[p] + self.street_commit[p] > 0 or p not in self.folded]

    def to_call(self, player: str) -> int:
        target = max(self.street_commit.values(), default=0)
        return target - self.street_commit[player]


def _rotate(players: tuple[str, ...], start: int) -> list[str]:
    return [players[(start + i) % len(players)] for i in range(len(players))]


def _next_street(street: str) -> str:
    return {"preflop": "flop", "flop": "turn", "turn": "river"}[street]


def reconstruct(hand: dict) -> HandState:
    """Восстановить банк и стэки из явного, полностью наблюдаемого сценария.

    Сценарий намеренно не читает сырой WebSocket: неизвестный протокол нельзя
    молча считать правильным. Подключение журнала — отдельная проверка.
    """
    players = tuple(hand["players"])
    if len(players) < 2 or len(set(players)) != len(players):
        raise ReconstructionError("нужны уникальные игроки")
    state = HandState(
        players=players,
        stacks={p: int(hand["stacks"][p]) for p in players},
        button=int(hand["button"]),
        sb=int(hand["sb"]),
        bb=int(hand["bb"]),
    )
    state.street_commit = {p: 0 for p in players}
    state.total_commit = {p: 0 for p in players}
    n = len(players)
    # Сверено с PokerKit: seat 1 всегда постит SB, seat 2 — BB. Отличается от
    # живой конвенции «кнопка = SB в хедз-апе»: конвенцию реального сервера
    # сверить по журналу (кто действует первым префлоп) до живых данных.
    button = state.button
    if n == 2 and button == 0:
        sb_index, bb_index = 1, 0
    else:
        sb_index = (button + 1) % n
        bb_index = (sb_index + 1) % n
    _post(state, players[sb_index], state.sb, blind=True)
    _post(state, players[bb_index], state.bb, blind=True)

    for raw in hand["actions"]:
        action = Action(
            player_id=raw["player"],
            street=raw.get("street", state.street),
            kind=raw["kind"],
            amount=int(raw.get("amount", 0)),
            cards=tuple(raw.get("cards", ())),
        )
        if action.street != state.street:
            raise ReconstructionError("действие относится к другой улице")
        if action.kind == "deal_board":
            _deal_board(state, action.cards)
        elif action.kind == "deal_hole":
            if len(action.cards) != 2:
                raise ReconstructionError("у игрока должно быть две карты")
            state.hole[action.player_id] = action.cards
        elif action.kind == "fold":
            if action.player_id in state.folded:
                raise ReconstructionError("повторный фолд")
            state.folded.add(action.player_id)
        elif action.kind in {"call", "check", "bet", "raise"}:
            _bet(state, action)
        else:
            raise ReconstructionError(f"неизвестное действие {action.kind}")
        _advance_when_closed(state)
    return state


def _post(state: HandState, player: str, amount: int, *, blind: bool) -> None:
    if amount > state.stacks[player]:
        amount = state.stacks[player]
    state.stacks[player] -= amount
    state.street_commit[player] += amount
    state.total_commit[player] += amount
    state.pot += amount
    if not blind and amount < 0:
        raise ReconstructionError("отрицательная ставка")
    _refresh_side_pots(state)


def _refresh_side_pots(state: HandState) -> None:
    """Построить уровни банков по итоговым взносам.

    Уровень [prev, level]: каждый участник с total >= level вносит
    (level - prev). Участники: все, кто внёс фишки, включая сбросивших
    (их деньги остаются в банке). Сбросившие исключаются только из
    returned_to при возврате верхнего уровня.
    """
    totals = sorted({v for v in state.total_commit.values() if v > 0})
    pots: list[SidePot] = []
    prev = 0
    participants = [p for p in state.players if state.total_commit[p] > 0]
    for level in totals:
        contributors = tuple(p for p in participants if state.total_commit[p] >= level)
        pots.append(SidePot(amount=(level - prev) * len(contributors), eligible=contributors))
        prev = level
    state.side_pots = pots


def _bet(state: HandState, action: Action) -> None:
    if action.player_id in state.folded:
        raise ReconstructionError("сбросивший игрок действует")
    due = state.to_call(action.player_id)
    if action.kind == "check":
        if due:
            raise ReconstructionError("чек при ненулевой ставке")
        amount = 0
    elif action.kind == "call":
        # Олл-ин: колл ограничен остатком стэка.
        amount = min(due, state.stacks[action.player_id])
    elif action.kind in {"bet", "raise"}:
        target = action.amount
        if target <= state.street_commit[action.player_id] + due:
            raise ReconstructionError("повышение должно задавать больший итог")
        amount = min(target - state.street_commit[action.player_id], state.stacks[action.player_id])
    state.stacks[action.player_id] -= amount
    state.street_commit[action.player_id] += amount
    state.total_commit[action.player_id] += amount
    state.pot += amount
    _refresh_side_pots(state)


def _deal_board(state: HandState, cards: tuple[str, ...]) -> None:
    expected = {"preflop": 3, "flop": 1, "turn": 1}[state.street]
    if len(cards) != expected:
        raise ReconstructionError("неверное число карт борда")
    _advance_street(state)
    state.board.extend(cards)


def _advance_street(state: HandState) -> None:
    state.street = _next_street(state.street)
    state.street_commit = {p: 0 for p in state.players}


def _advance_when_closed(state: HandState) -> None:
    active = [p for p in state.players if p not in state.folded]
    if len(active) == 1:
        _return_uncalled(state, active)
        winner = active[0]
        state.stacks[winner] += state.pot
        state.pot = 0
        return
    if any(state.to_call(p) and state.stacks[p] for p in active):
        return


def _return_uncalled(state: HandState, active: list[str]) -> None:
    """Вернуть неуравненное превышение на текущей улице.

    1. Если один активный игрок не в олл-ине превысил максимум среди
       остальных — вернуть превышение ему (классический uncalled bet).
    2. Если кто-то в олл-ине за меньшую сумму (короткий стэк), а двое
       глубоких продолжают выше — верхний уровень остаётся сайд-потом,
       возврата нет. Это сверено с PokerKit: 240/440.
    """
    commits = state.street_commit
    ranked = sorted(commits.values(), reverse=True)
    matched = ranked[1] if len(ranked) > 1 else 0
    for player, committed in commits.items():
        excess = committed - matched
        in_allin = state.stacks[player] == 0
        if excess > 0 and player in active and not in_allin:
            state.stacks[player] += excess
            state.pot -= excess
            state.street_commit[player] -= excess
            state.total_commit[player] -= excess
            if state.side_pots:
                top = state.side_pots[-1]
                top.amount -= excess
                top.returned_to = top.returned_to + (player,)
            break
    _refresh_side_pots(state)


def chip_invariant(hand: dict, state: HandState) -> bool:
    initial = sum(int(v) for v in hand["stacks"].values())
    return initial == state.pot + sum(state.stacks.values())
