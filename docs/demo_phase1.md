# Demo — Phase 1 (synthetic data, advise mode)

1. `python tools/synth_data/generate.py ./data/synth 200` — 200 items, 2 sites, 25 suppliers.
2. `pip install -e ./backend[dev]` then `pytest ./backend -q` — expect all green (26 tests).
3. `uvicorn app.main:app --app-dir backend` — `GET /health` → ok; `GET /api/v1/dashboard/summary` → counts.
4. Golden proof: INV-01/SEV/SCORE/SUP/DQS/CLS suites pin spec formulas to evaluation-dataset.json.
5. Frontend: `npm i && npm run dev` in frontend/ — dashboard reads the summary API (estimates labeled).

Targets A1-A7 are measured fully once the P1-10 simulation harness replays ground_truth week-by-week (next).
