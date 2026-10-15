"""VPIP по каждому стабильному id из журнала. Печатает JSON."""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from solver.profiles import build_profiles, load_finished, summarize


def main() -> None:
    hands, seen = [], set()
    for path in ("/home/user/jev-poker/auto-jev.jsonl", "/home/user/jev-poker/auto-solver.jsonl"):
        try:
            for h in load_finished(path):
                if h["match"] not in seen:
                    seen.add(h["match"])
                    hands.append(h)
        except FileNotFoundError:
            pass
    profiles = build_profiles(hands)
    out = {}
    for pid, s in profiles.items():
        summ = summarize(s)
        if summ["hands"] >= 3:
            out[pid] = {"vpip": summ["vpip"], "hands": summ["hands"]}
    print(json.dumps({"players": out}))


if __name__ == "__main__":
    main()
