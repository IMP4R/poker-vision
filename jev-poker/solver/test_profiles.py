"""Тесты профилей: синтетические архетипы и проверка на живом журнале."""

from solver.profiles import (
    build_profiles,
    load_finished,
    profile_hand,
    summarize,
    vpip_to_range_percent,
    wilson_lower,
)


def _e(pid, typ, street="preflop", add=0, total=0, blind=False):
    return {"id": pid, "type": typ, "street": street, "add": add, "total": total, "blind": blind}


def test_calling_station_profile() -> None:
    hist = [
        _e("vill", 8, add=25, total=25, blind=True),
        _e("vill", 4, add=25, total=50, blind=False),
        _e("vill", 4, street="flop", add=100, total=150),
        _e("vill", 4, street="turn", add=200, total=350),
        _e("vill", 4, street="river", add=300, total=650),
    ]
    s = summarize(profile_hand(hist, {"vill"})["vill"])
    assert s["vpip"] == 1
    assert s["pfr"] == 0
    assert s["postflop_calls"] == 3 and s["postflop_aggr"] == 0
    assert s["aggression_factor"] == 0.0
    assert s["raise_then_fold"] == 0


def test_raise_then_fold_is_detected() -> None:
    hist = [
        _e("vill", 8, add=300, total=325),
        _e("hero", 8, add=900, total=950),
        _e("vill", 1, add=0, total=325),
    ]
    s = summarize(profile_hand(hist, {"vill"})["vill"])
    assert s["pfr"] == 1
    assert s["raise_then_fold"] == 1


def test_aggressive_never_folds_is_not_coward() -> None:
    hist = [
        _e("vill", 8, add=300, total=325),
        _e("hero", 8, add=900, total=950),
        _e("vill", 4, add=650, total=975, street="preflop"),
        _e("vill", 8, street="flop", add=500, total=1475),
    ]
    s = summarize(profile_hand(hist, {"vill"})["vill"])
    assert s["raise_then_fold"] == 0
    assert s["postflop_aggr"] == 1


def test_wilson_lower_is_conservative() -> None:
    assert wilson_lower(0, 10) == 0.0
    lo = wilson_lower(5, 10)
    assert 0.15 < lo < 0.5, lo
    assert wilson_lower(50, 100) > wilson_lower(5, 10)
    assert wilson_lower(0, 0) == 0.0


def test_seat_labels_are_excluded_from_profiles() -> None:
    hands = load_finished("/home/user/jev-poker/auto-jev.jsonl")
    profiles = build_profiles(hands)
    assert profiles, "ожидались стабильные id в журнале"
    assert all(not p.startswith("P") or len(p) < 4 for p in profiles)


def test_journal_profiles_are_sane() -> None:
    hands = load_finished("/home/user/jev-poker/auto-jev.jsonl")
    profiles = build_profiles(hands)
    active = {p: summarize(s) for p, s in profiles.items() if s["hands"] >= 5}
    assert active, "нужны игроки с 5+ руками"
    for pid, s in active.items():
        assert 0 < s["vpip"] <= 1, (pid, s)
        assert s["vpip_wilson_lo"] <= s["vpip"]
    # хотя бы один игрок заходил чаще, чем тайтовый тип, и есть коровы-рейзеры
    vpips = [s["vpip"] for s in active.values()]
    assert max(vpips) >= 0.5, vpips


def test_vpip_to_range_percent_bounds() -> None:
    assert vpip_to_range_percent(1.0) == 100.0
    assert vpip_to_range_percent(0.6) == 60.0
    assert vpip_to_range_percent(0.01) == 5.0
    try:
        vpip_to_range_percent(0)
    except ValueError:
        pass
    else:
        raise AssertionError("vpip=0 не отклонён")
