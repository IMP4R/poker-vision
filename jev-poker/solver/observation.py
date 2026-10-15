"""G8: валидатор наблюдаемого состояния стола без игровых действий.

Модуль не подключается к CDP и ничего не нажимает. Он проверяет snapshot,
который может быть получен существующим decoder/OCR-контуром:
legal action mask, банк, call/raise, стэки, street и согласованность размеров.
"""

from __future__ import annotations

from dataclasses import dataclass

ACTION_BITS = {"fold": 1, "check": 2, "call": 4, "raise": 8}
STREETS = {"preflop": 0, "flop": 3, "turn": 4, "river": 5}


@dataclass(frozen=True)
class ObservationSnapshot:
    street: str
    board: tuple[str, ...]
    pot: int
    to_call: int
    hero_stack: int
    allowed_actions: tuple[str, ...]
    min_raise: int | None = None
    committed: int = 0
    gross_contributions: int | None = None


def allowed_from_mask(mask: int) -> tuple[str, ...]:
    if not isinstance(mask, int) or mask < 0:
        raise ValueError("allowed mask должен быть неотрицательным int")
    unknown_bits = mask & ~sum(ACTION_BITS.values())
    if unknown_bits:
        raise ValueError(f"неизвестные биты allowed mask: {unknown_bits}")
    actions = tuple(name for name, bit in ACTION_BITS.items() if mask & bit)
    if not actions:
        raise ValueError(f"пустой allowed mask: {mask}")
    return actions


def validate_snapshot(snapshot: ObservationSnapshot) -> dict:
    """Проверить snapshot и вернуть диагностический отчёт.

    Любое нарушение состояния — hard failure (`valid=False`), чтобы наблюдатель
    не мог передать рассинхронизированное состояние советнику/кликеру.
    """
    errors: list[str] = []
    if snapshot.street not in STREETS:
        errors.append("unknown_street")
    expected_cards = STREETS.get(snapshot.street)
    if expected_cards is not None and len(snapshot.board) != expected_cards:
        errors.append("board_street_mismatch")
    if snapshot.pot < 0:
        errors.append("negative_pot")
    if snapshot.to_call < 0:
        errors.append("negative_to_call")
    if snapshot.hero_stack < 0:
        errors.append("negative_stack")
    if snapshot.to_call > snapshot.hero_stack:
        errors.append("call_exceeds_stack")
    if snapshot.committed < 0:
        errors.append("negative_commitment")
    if snapshot.min_raise is not None and snapshot.min_raise <= 0:
        errors.append("invalid_min_raise")
    if "fold" in snapshot.allowed_actions and snapshot.to_call == 0:
        errors.append("fold_without_bet_allowed")
    if snapshot.to_call > 0 and "call" not in snapshot.allowed_actions and "fold" not in snapshot.allowed_actions:
        errors.append("missing_call_or_fold")
    if "raise" in snapshot.allowed_actions and snapshot.min_raise is None:
        errors.append("raise_without_minimum")
    if snapshot.gross_contributions is not None and snapshot.gross_contributions < snapshot.pot:
        errors.append("pot_exceeds_observed_contributions")
    return {
        "valid": not errors,
        "errors": errors,
        "street": snapshot.street,
        "board_cards": len(snapshot.board),
        "pot": snapshot.pot,
        "to_call": snapshot.to_call,
        "hero_stack": snapshot.hero_stack,
        "allowed_actions": list(snapshot.allowed_actions),
        "min_raise": snapshot.min_raise,
        "precision": "exact_protocol_snapshot" if not errors else "invalid_snapshot",
    }


def snapshot_from_protocol(event: dict, *, pot: int, board: tuple[str, ...], allowed_mask: int) -> ObservationSnapshot:
    """Собрать snapshot из полей `game_start_move` существующего decoder."""
    actions = allowed_from_mask(allowed_mask)
    street = {0: "preflop", 3: "flop", 4: "turn", 5: "river"}.get(len(board), "unknown")
    return ObservationSnapshot(
        street=street,
        board=tuple(board),
        pot=int(pot),
        to_call=int(event.get("call_value", 0) or 0),
        hero_stack=int(event.get("cash", 0) or 0),
        allowed_actions=actions,
        min_raise=(int(event.get("raise_value")) if event.get("raise_value") is not None else None),
        committed=int(event.get("committed", 0) or 0),
        gross_contributions=(int(event["gross_contributions"]) if event.get("gross_contributions") is not None else None),
    )


def validate_executable_action(snapshot: ObservationSnapshot, action: str, *, requested_size: int | None = None) -> dict:
    """Проверить, что решение legal и его размер исполним."""
    report = validate_snapshot(snapshot)
    errors = list(report["errors"])
    if action not in snapshot.allowed_actions:
        errors.append("action_not_allowed")
    actual_size = None
    if action == "call":
        actual_size = snapshot.to_call
        if requested_size is not None and requested_size != actual_size:
            errors.append("call_size_mismatch")
    elif action == "raise":
        if snapshot.min_raise is None:
            errors.append("raise_minimum_missing")
        else:
            actual_size = snapshot.min_raise
            if requested_size is not None and requested_size < actual_size:
                errors.append("raise_below_legal_minimum")
    return {
        "valid": not errors,
        "errors": errors,
        "action": action,
        "actual_size": actual_size,
        "snapshot_valid": report["valid"],
        "precision": "exact_protocol_snapshot" if not errors else "invalid_action_or_snapshot",
    }
