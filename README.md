# Sporeborne AI Dev Pipeline

The AI content/dev pipeline for **Sporeborne** — my capstone game (2D side-scrolling
roguelike, Unreal Engine 5). This repo is the pipeline half of Assignment #10's
submission; the playable game itself is a separate itch.io build.

## What's here (`pipeline/`)

- **`crew.py`** — 4-agent content crew: Roomsmith → Bestiary → Curvewright → Data
  Validator. Generates room templates, enemy stat rows, and power-curve constants
  from a zone theme + difficulty band, validated against a deterministic rule set.
- **`content_pipeline.py`** — retrieval-grounded content generation (TF-IDF over
  the real GDD) for bestiary flavor text, spore flavor text, and Warren hub-NPC
  dialogue, each checked by a Critic Agent that runs its own independent
  retrieval pass before anything's considered done.
- **`goal_agent.py`** — scans the actual game's C++ source against the GDD's own
  production-gate table, scores every gap, and writes the highest-priority
  missing feature as real code.
- **`ger_pipeline.py`** — Generator/Evaluator/Refiner/Circuit-Breaker loop
  enforcing a specific GDD rule (Mythic-rarity spores must carry a curse).
- **`style_guide_pipeline.py`** — a scored (1-10, not pass/fail) Evaluator +
  Refiner loop enforcing tone/vocabulary/formatting rules pulled from the GDD.
- **`agents/`** — the shared agent implementations + `llm_client.py` (the
  Anthropic API wrapper every pipeline uses, live/simulate fallback built in so
  the whole pipeline is runnable with zero setup if no API key is present).
- **`design/`** — the plain-text GDD (`GDD_Sporeborne.md`) every pipeline reads
  from directly, plus the deterministic rule sets.
- **`output/`** — real, live-run output from every pipeline above, including a
  full trace (queries, retrieved chunks, generated content, critique/evaluation)
  for `content_pipeline.py`'s most recent run — the same run whose content is
  displayed in the playable build.

## Automated flow: pipeline output to in-game content

`content_pipeline.py` writes `output/content_pipeline_result.json`. The Unreal
project reads that file directly at runtime (no manual copy/paste, no DataTable
re-authoring step) and displays real generated lines on-screen during play. The
JSON produced by the pipeline is the same JSON the shipped game reads — one file,
no reformatting in between.

## Running it

```bash
pip install -r pipeline/requirements.txt
python3 pipeline/content_pipeline.py       # writes output/content_pipeline_result.json
```

Requires `ANTHROPIC_API_KEY` for live generation; without one, every agent falls
back to a deterministic `simulate()` mode so the pipeline still runs end to end.
