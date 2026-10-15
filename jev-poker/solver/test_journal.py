"""Тесты импорта журнала: только проверяемые факты, без выдуманных стэков."""

from solver.journal import gross_pot, hero_committed, load_finished_journal, verify_hand

JOURNAL = "/home/user/jev-poker/auto-jev.jsonl"


def test_journal_loads_finished_hands() -> None:
    hands = load_finished_journal(JOURNAL)
    assert len(hands) >= 100, f"ожидались сотни рук, найдено {len(hands)}"


def test_journal_hands_are_consistent() -> None:
    hands = load_finished_journal(JOURNAL)
    bad = 0
    total_committed = 0
    for h in hands:
        rep = verify_hand(h)
        assert not rep["errors"], f"{rep['match']}: {rep['errors']}"
        total_committed += rep["hero_committed"]
        assert rep["gross_pot"] >= rep["hero_committed"]
    assert bad == 0
    # sanity: hero вообще вкладывал фишки за историю
    assert total_committed > 0


def test_known_hand_pot_breakdown() -> None:
    # FD197074: SB25 + BB50 + колл P1 50 + колл hero 50 + 4975 + 4950 + 4800.
    hands = {h["match"]: h for h in load_finished_journal(JOURNAL)}
    h = hands["FD197074-B7F4-11F1-868A-84E19E7DDAF2"]
    rep = verify_hand(h)
    assert rep["hero_committed"] == 50
    assert rep["gross_pot"] == 25 + 50 + 50 + 50 + 4975 + 4950 + 4800
    assert rep["hero_folded"] is True
    assert rep["won"] is False


def test_gross_pot_matches_money_v2_definition() -> None:
    # Определение банка money-v2: сумма add_coins с начала раздачи.
    hands = load_finished_journal(JOURNAL)
    h = next(x for x in hands if x["match"].startswith("FD197074"))
    assert gross_pot(h["history"]) == hero_committed(h["history"]) + sum(
        int(a.get("add", 0) or 0) for a in h["history"] if a.get("id") != "hero"
    )
