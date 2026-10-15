# Acceptance report: local poker solver

Дата: 2026-09-24
Проект: `/home/user/jev-poker`

## Результат

Математическое ядро и read-only верификационный контур приняты для перехода к
human-gated operational запуску. Автоматический G9 запуск не активирован:
hero-specific move confirmation и явное разрешение запуска отсутствуют.

## Покрытые требования

- Full-line scenario EV: `solver/line_ev.py`.
- Effective stack/session/active budget: `solver/capital.py`, `solver/entry.py`.
- Wide preflop entry: `solver/preflop.py`.
- Board/postflop candidates: `solver/postflop.py`.
- Per-opponent ranges/action likelihood: `solver/opponent_model.py`.
- Snapshot/action/size consistency: `solver/observation.py`.
- Snapshot-to-policy bridge: `solver/decision_bridge.py`.
- Fixed-journal replay: `solver/offline_validate.py`, `solver/shadow_replay.py`.
- Human safety gate: `solver/launch_gate.py`, `G9_LAUNCH_CHECKLIST.md`.

## Evidence

- Full solver suite: **104 passed**.
- Offline fixed journal: 367 decisions, 62.67% agreement overall;
  preflop 63.89%. Small postflop sample is not treated as proof of quality.
- Shadow replay: 367 decisions; selected check=133, call=144, fold=90.
- CDP page probe: Chrome/CDP and Crazy Panda game page available.
- Protocol probe: read-only websocket subscription; no clicks/reloads/actions.
- Behavior map: CLI extractor reports 0/0 nodes and 100% arithmetic coverage;
  no UI/routes were enumerated for this CLI project.
- Runtime safety: `auto-solver.mjs`, `auto-jev.mjs`, and `watchdog-play.mjs`
  were not running during final audit.

## Explicit limitations

- Several preflop/postflop/line EV values are scenario-approximate, not a solved
  Nash equilibrium or proof of profitability.
- Full operational G8 series is not claimed: one observed move was not proven
  to belong to hero; launch gate therefore remains closed.
- Side pots, rake, uncalled refunds and all UI-size variants require additional
  live protocol evidence before production-like use.
- No automatic game actions were executed in this acceptance pass.

## Safety policy

Jev/LLM is not on the decision path. Chip purchases and tournaments are
forbidden. Any future live run must pass `launch_gate.py`, use play-money only,
set a small hand limit and active budget, and auto-stop on invalid state,
hero-ID mismatch, action-mask mismatch, OCR mismatch, timer expiry or unknown
side-pot state.
