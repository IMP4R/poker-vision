"""Тесты наблюдательного режима: ретропрогон советника по журналу."""

from solver.observe import hero_decisions, replay


def _h(match, at, history, board=None, cards=("As", "Kd")):
    return {"match": match, "at": at, "history": history, "board": board or [], "cards": list(cards), "result": {"won": False, "payout": []}}


def test_hero_decisions_reconstructs_pot_and_call() -> None:
    history = [
        {"id": "P1", "type": 8, "street": "preflop", "add": 25, "total": 25, "blind": True},
        {"id": "hero", "type": 8, "street": "preflop", "add": 50, "total": 50, "blind": True},
        {"id": "P1", "type": 4, "street": "preflop", "add": 25, "total": 50, "blind": False},
        {"id": "P1", "type": 8, "street": "preflop", "add": 200, "total": 250, "blind": False},
        {"id": "hero", "type": 1, "street": "preflop", "add": 0, "total": 50, "blind": False},
    ]
    hand = _h("m1", "t1", history)
    ds = hero_decisions(hand)
    assert len(ds) == 1
    d = ds[0]
    # перед решением hero: банк 300 (25+50+25+200), колл 200
    assert d["pot"] == 300
    assert d["to_call"] == 200
    assert d["taken"] == "fold"


def test_hero_check_decision() -> None:
    history = [
        {"id": "hero", "type": 8, "street": "preflop", "add": 50, "total": 50, "blind": True},
        {"id": "P1", "type": 4, "street": "preflop", "add": 50, "total": 50, "blind": False},
        {"id": "hero", "type": 2, "street": "flop", "add": 0, "blind": False},
    ]
    ds = hero_decisions(_h("m2", "t2", history))
    assert ds[-1]["taken"] == "check"
    assert ds[-1]["to_call"] == 0


def test_replay_runs_over_real_journal() -> None:
    rep = replay(trials=800, seed=1)
    assert rep["decisions"] > 100, rep["decisions"]
    assert 0.0 < rep["agreement"] <= 1.0
    assert rep["median_vpip"] is not None
    # префлоп-решения не должны видеть борд (утечка будущих карт запрещена)
    assert all(r["street"] != "preflop" or r["board_cards"] == 0 for r in rep["rows"])
    for r in rep["rows"][:20]:
        assert r["advice"] in ("fold", "call", "bet", "check")
        assert isinstance(r["agreed"], bool)
