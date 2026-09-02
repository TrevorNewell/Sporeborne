# Sporeborne Content Crew

**Game:** Sporeborne — a 2D side-scrolling roguelike (Unreal Engine 5 / Paper2D), built solo with AI agents. Morel, a mushroom-folk knight, descends through the Rootways grafting spores onto a fixed spear-and-buckler kit to fight her way to The Gatekeeper.

## What this crew produces

A **game-ready combat-room package** for the Rootways zone: one room layout with hazard tags and a spawn table, the enemies that populate it, and the difficulty-curve projection for that room — validated against a rule-set before it's considered shippable. This is the smallest complete unit of content Sporeborne needs to add a new room to the game: a level designer (or the import pipeline) can take the output JSON straight into Unreal DataTables without touching anything by hand.

## The crew — 4 agents, each required

| Agent | Input | Output | Why it can't be removed |
|---|---|---|---|
| **Roomsmith** | Human-authored zone theme (`design/zone_theme_rootways.json`) | Room layout, hazard tags, spawn table | Nothing downstream has anything to work with without a room to populate. |
| **Bestiary** | Roomsmith's room (hazards, spawn slots) | Enemy stats, attack patterns, telegraph timing | Without Roomsmith's hazard tags it has no brief — it would be guessing enemies with nothing to fit them to. |
| **Curvewright** | Roomsmith's room + Bestiary's enemies + the difficulty band | Projected boss-door power multiple, flagged outliers | Can't project a curve without concrete enemy numbers to project from. |
| **Data Validator** | All three outputs above + the rule-set | PASS/FAIL report, per-item failure reasons | Nothing else in the crew checks cross-agent consistency (e.g. "does this enemy actually fit this room's hazards?") — remove it and broken content ships silently. |

Each agent's role, input, and output are defined in `agents/*.py`. See `architecture.mermaid` for the full data-flow diagram, including the retry/escalation path.

## How it coordinates

Roomsmith runs first. Bestiary and Curvewright run in sequence, each depending on the previous agent's actual output (not just its existence). Data Validator runs last and checks all three outputs together. If validation fails, the specific failing rows go back to their *originating* agent (identified by the `origin` field on each failure) for up to 2 retries; if it still fails, the crew stops and escalates rather than looping or shipping broken content.

## Running it

```bash
pip install anthropic          # only needed for live mode
python3 crew.py                # runs the crew, writes output/
python3 crew.py --inject-failure   # demonstrates the retry/escalation path
```

- **With `ANTHROPIC_API_KEY` set:** each content agent calls the real Anthropic API.
- **Without it:** each agent falls back to a deterministic `simulate()` method, so the crew is runnable and gradeable with zero setup. The orchestration, retry, and validation logic is identical in both modes — only where the content comes from changes.

Output lands in `output/`:
- `run_result.json` — full run log (every agent call, mode, pass/fail) plus the final package if the run passed.
- `<room_id>_package.json` — the game-ready package on its own, ready for the Unreal import step.

## Design source

This crew implements a subset of the multi-agent architecture defined in Sporeborne's GDD (§8, "AI Architecture") — specifically the room/enemy/curve authoring branch and its validation gate. The GDD's full architecture includes five more agents (Sporewright, Loremaster, Tester, Balancer, and the runtime-only Warren Voices) that aren't part of this assignment's minimum crew but follow the same input/output/ownership pattern.
