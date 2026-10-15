"""Тесты графика наглости."""

from solver.boldness import (
    boldness_series,
    decayed_state,
    hand_boldness,
    reaction_after_outcome,
)


def _e(pid, typ, street="preflop", add=0, blind=False):
    return {"id": pid, "type": typ, "street": street, "add": add, "blind": blind}


def _hand(at, entries, won=None):
    h = {"at": at, "history": entries}
    if won is not None:
        h["result"] = {"won": won, "payout": [1000] if won else []}
    return h


BB = 50


def test_blinds_do_not_count_as_boldness() -> None:
    hist = [_e("v", 8, add=25, blind=True), _e("v", 8, add=50, blind=True)]
    assert hand_boldness(hist, "v", BB) == 0.0


def test_street_weights_and_bb_scale() -> None:
    hist = [
        _e("v", 8, "preflop", add=50),
        _e("v", 8, "flop", add=100),
        _e("v", 8, "turn", add=100),
        _e("v", 8, "river", add=150),
    ]
    expected = 1.0 + 1.2 * 2 + 1.4 * 2 + 1.6 * 3
    assert abs(hand_boldness(hist, "v", BB) - expected) < 1e-9
    assert hand_boldness(hist, "v", 100) * 2 == hand_boldness(hist, "v", 50)
    try:
        hand_boldness(hist, "v", 0)
    except ValueError:
        pass
    else:
        raise AssertionError("bb=0 не отклонён")


def test_series_filters_foreign_hands() -> None:
    hands = [
        _hand("a", [_e("v", 8, add=100)]),
        _hand("b", [_e("hero", 8, add=100)]),
        _hand("c", [_e("v", 8, add=200)]),
    ]
    s = boldness_series(hands, "v", BB)
    assert [t for t, _ in s] == ["a", "c"]
    assert [v for _, v in s] == [2.0, 4.0]


def test_decayed_state_detects_boldening() -> None:
    quiet = [_hand(f"h{i}", [_e("v", 8, add=50)]) for i in range(10)]
    bold = [_hand(f"h{i}", [_e("v", 8, add=200)]) for i in range(10, 20)]
    s = decayed_state(boldness_series(quiet + bold, "v", BB), half_life=3)
    assert s["shift_z"] > 0.5, s
    back = decayed_state(boldness_series(bold + quiet, "v", BB), half_life=3)
    assert back["shift_z"] < -0.5, back
    # постоянный игрок: сдвиг около нуля
    flat = [_hand(f"h{i}", [_e("v", 8, add=100)]) for i in range(15)]
    assert abs(decayed_state(boldness_series(flat, "v", BB))["shift_z"]) < 1e-9
    assert decayed_state([])["n"] == 0


def test_reaction_uses_known_outcomes_only() -> None:
    # Чередование побед; рука ПОСЛЕ победы в два раза агрессивнее.
    hands = []
    for i in range(20):
        hands.append(_hand(f"h{i}", [_e("hero", 8, add=50)], won=(i % 2 == 0)))
    for i in range(19):
        if hands[i]["result"]["won"]:
            hands[i + 1]["history"] = [_e("hero", 8, add=100)]
    r = reaction_after_outcome(hands, "hero", BB)
    assert r["after_win_n"] > 0 and r["after_loss_n"] > 0
    assert r["after_win_bold"] > r["after_loss_bold"], r
    assert "наглеет" in r["hypothesis"]
    assert "нужен" in r["caveat"]
