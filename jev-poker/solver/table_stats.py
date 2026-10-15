"""Медианный VPIP стола по стабильным профилям журнала.

Печатает JSON {"median_vpip": float|null}. Используется игроком на
советнике как ширина диапазона оппонента по умолчанию.
"""

from __future__ import annotations

import json
import statistics

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from solver.profiles import build_profiles, load_finished, summarize


def main() -> None:
    hands = load_finished("/home/user/jev-poker/auto-jev.jsonl")
    profiles = build_profiles(hands)
    vpips = [summarize(s)["vpip"] for s in profiles.values() if s["hands"] >= 5]
    median = statistics.median(vpips) if vpips else None
    print(json.dumps({"median_vpip": median, "players": len(vpips)}))


if __name__ == "__main__":
    main()
