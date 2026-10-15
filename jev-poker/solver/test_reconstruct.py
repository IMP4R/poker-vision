"""Тесты проверяемой реконструкции раздачи. Эталон правил — PokerKit.

Конвенция: кнопка на seat 0, SB = seat (button+1) % n, первым префлоп
действует SB. Это поведение сверено с PokerKit и может отличаться от
конвенции живого сервера — см. пометку в solver/reconstruct.py.
"""

from pokerkit import Automation, NoLimitTexasHoldem

from solver.reconstruct import chip_invariant, reconstruct


def test_call_preserves_chips_and_pot() -> None:
    # SB (villain) рейзит до 100, BB (hero) коллирует 50.
    hand = {
        "players": ["hero", "villain"],
        "stacks": {"hero": 1000, "villain": 1000},
        "button": 0,
        "sb": 25,
        "bb": 50,
        "actions": [
            {"player": "villain", "kind": "raise", "amount": 100},
            {"player": "hero", "kind": "call"},
        ],
    }
    state = reconstruct(hand)
    assert state.pot == 200
    assert state.stacks == {"hero": 900, "villain": 900}
    assert chip_invariant(hand, state)


def test_fold_matches_pokerkit() -> None:
    hand = {
        "players": ["hero", "villain"],
        "stacks": {"hero": 1000, "villain": 1000},
        "button": 0,
        "sb": 25,
        "bb": 50,
        "actions": [
            {"player": "hero", "kind": "deal_hole", "cards": ["As", "Kd"]},
            {"player": "villain", "kind": "deal_hole", "cards": ["Qc", "Jh"]},
            {"player": "villain", "kind": "raise", "amount": 200},
            {"player": "hero", "kind": "fold"},
        ],
    }
    ours = reconstruct(hand)
    state = NoLimitTexasHoldem.create_state(
        (
            Automation.ANTE_POSTING,
            Automation.BET_COLLECTION,
            Automation.BLIND_OR_STRADDLE_POSTING,
            Automation.HOLE_CARDS_SHOWING_OR_MUCKING,
            Automation.HAND_KILLING,
            Automation.CHIPS_PUSHING,
            Automation.CHIPS_PULLING,
        ),
        True,
        0,
        (25, 50),
        25,
        (1000, 1000),
        2,
    )
    state.deal_hole("AsKd")
    state.deal_hole("QcJh")
    state.complete_bet_or_raise_to(200)
    state.fold()
    assert list(state.stacks) == [ours.stacks["hero"], ours.stacks["villain"]]
    assert list(state.stacks) == [950, 1050]
    assert ours.pot == 0
    assert chip_invariant(hand, ours)


def test_uncalled_raise_is_returned_three_way() -> None:
    # a на кнопке рейзит до 500, SB и BB сбрасывают: неуравненные 450
    # возвращаются, банк 100 уходит победителю.
    hand = {
        "players": ["a", "b", "c"],
        "stacks": {"a": 1000, "b": 1000, "c": 1000},
        "button": 0,
        "sb": 25,
        "bb": 50,
        "actions": [
            {"player": "a", "kind": "raise", "amount": 500},
            {"player": "b", "kind": "fold"},
            {"player": "c", "kind": "fold"},
        ],
    }
    state = reconstruct(hand)
    assert state.pot == 0
    assert state.stacks == {"a": 1075, "b": 975, "c": 950}
    assert chip_invariant(hand, state)


def test_side_pots_match_pokerkit() -> None:
    # a=BB(1000), b=SB короткий(80), c=кнопка(1000).
    # c рейзит до 300, a коллирует, b коллирует олл-ином на 80.
    # Эталон PokerKit: pots [(240, (0,1,2)), (440, (0,2))].
    hand = {
        "players": ["a", "b", "c"],
        "stacks": {"a": 1000, "b": 80, "c": 1000},
        "button": 2,
        "sb": 25,
        "bb": 50,
        "actions": [
            {"player": "c", "kind": "raise", "amount": 300},
            {"player": "a", "kind": "call"},
            {"player": "b", "kind": "call"},
        ],
    }
    ours = reconstruct(hand)
    state = NoLimitTexasHoldem.create_state(
        (
            Automation.ANTE_POSTING,
            Automation.BET_COLLECTION,
            Automation.BLIND_OR_STRADDLE_POSTING,
            Automation.HOLE_CARDS_SHOWING_OR_MUCKING,
            Automation.HAND_KILLING,
            Automation.CHIPS_PUSHING,
            Automation.CHIPS_PULLING,
        ),
        True,
        0,
        (25, 50),
        50,
        (1000, 80, 1000),
        3,
    )
    state.deal_hole("AsKd")
    state.deal_hole("QcJh")
    state.deal_hole("7c2d")
    assert state.actor_index == 2
    state.complete_bet_or_raise_to(300)
    state.check_or_call()
    state.check_or_call()
    ref = [(p.amount, p.player_indices) for p in state.pots]
    assert ref == [(240, (0, 1, 2)), (440, (0, 2))]
    got = [(p.amount, tuple(hand["players"].index(x) for x in p.eligible)) for p in ours.side_pots]
    assert got == ref
    assert ours.pot == 680
    assert chip_invariant(hand, ours)


def test_flop_betting_matches_pokerkit() -> None:
    # Префлоп: c(кнопка) рейз до 150, оба колл. Флоп AhKsQd:
    # a чекает, b ставит 200, оба колл. Эталон: банк 1050, стэки по 650.
    hand = {
        "players": ["a", "b", "c"],
        "stacks": {"a": 1000, "b": 1000, "c": 1000},
        "button": 2,
        "sb": 25,
        "bb": 50,
        "actions": [
            {"player": "c", "street": "preflop", "kind": "raise", "amount": 150},
            {"player": "a", "street": "preflop", "kind": "call"},
            {"player": "b", "street": "preflop", "kind": "call"},
            {"player": "c", "street": "preflop", "kind": "deal_board", "cards": ["Ah", "Ks", "Qd"]},
            {"player": "a", "street": "flop", "kind": "check"},
            {"player": "b", "street": "flop", "kind": "bet", "amount": 200},
            {"player": "c", "street": "flop", "kind": "call"},
            {"player": "a", "street": "flop", "kind": "call"},
        ],
    }
    ours = reconstruct(hand)
    state = NoLimitTexasHoldem.create_state(
        (
            Automation.ANTE_POSTING,
            Automation.BET_COLLECTION,
            Automation.BLIND_OR_STRADDLE_POSTING,
            Automation.HOLE_CARDS_SHOWING_OR_MUCKING,
            Automation.HAND_KILLING,
            Automation.CHIPS_PUSHING,
            Automation.CHIPS_PULLING,
        ),
        True,
        0,
        (25, 50),
        50,
        (1000, 1000, 1000),
        3,
    )
    state.deal_hole("AsKd")
    state.deal_hole("QcJh")
    state.deal_hole("7c2d")
    state.complete_bet_or_raise_to(150)
    state.check_or_call()
    state.check_or_call()
    state.burn_card("??")
    state.deal_board("AhKsQd")
    assert state.actor_index == 0
    state.check_or_call()
    state.complete_bet_or_raise_to(200)
    state.check_or_call()
    state.check_or_call()
    assert list(state.stacks) == [ours.stacks[p] for p in hand["players"]]
    assert ours.pot == 1050
    assert [(p.amount, tuple(hand["players"].index(x) for x in p.eligible)) for p in ours.side_pots] == [(1050, (0, 1, 2))]
    assert chip_invariant(hand, ours)


def test_unopened_check_is_rejected() -> None:
    # SB (b) не может чекнуть префлоп при живом BB hero... здесь a=SB
    # при button=1; проще: b чекает при ненулевой ставке против него.
    hand = {
        "players": ["a", "b"],
        "stacks": {"a": 500, "b": 500},
        "button": 0,
        "sb": 25,
        "bb": 50,
        "actions": [{"player": "b", "kind": "check"}],
    }
    try:
        reconstruct(hand)
    except ValueError as exc:
        assert "чек" in str(exc)
    else:
        raise AssertionError("незаконный чек принят")
