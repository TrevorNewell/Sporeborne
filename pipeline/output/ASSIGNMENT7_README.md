# Style Guide Agent — Assignment #7

For Sporeborne, my capstone game — a cozy-but-deadly 2D roguelike where you play
Morel, a tiny mushroom knight fighting down through the Rootways.

## The problem

My content generators from Assignment #4 don't know Sporeborne's house style out
of the box. Left alone, an LLM will happily write a generic cheerful fantasy
shopkeeper line, or mix up which NPC sells what. I wanted something that catches
that automatically and fixes it, with no human in the loop.

## The style guide

Three rules, all pulled straight from the GDD (`Claude/design/style_guide_rootways.md`):

- **Tone** — "cozy above, deadly below." Every line needs warmth *and* a real edge
  of danger. Too cheerful (cartoon shopkeeper) or too grim (no warmth at all) both
  fail.
- **Vocabulary/lore** — Gold is Snail's in-run currency; Bloom is Beetle's
  persistent currency at the Spore Archive. Mixing them up is a lore error — the
  same mistake my Critic Agent actually caught for real back in Assignment #4.
- **Formatting** — hub-NPC lines are short spoken barks, not monologues with stage
  directions.

## How it works

`style_guide_pipeline.py` runs three agents:

1. **Generator** — writes a first draft with zero house-style grounding, on
   purpose — it's what you'd get from any generic content tool.
2. **Evaluator** — grades the draft 1–10 against the three rules and explains why
   (`SCORE: [X/10]` / `REASON: ...`).
3. **Refiner** — takes that reason and rewrites the line to fix it. No human
   involved.

It keeps looping (up to 2 rewrites) until the score is good. Everything falls back
to a deterministic version if there's no API key, so it still runs with zero
setup.

## Before / after

**Tone (Snail), 2/10 → 9/10**
Before: *"Welcome back, welcome back, welcome BACK! Oh, it's so wonderful to see
you again! Did you have the most amazing adventure?!"*
After: *"Made it back — I'd say I worried, but the shells don't sell themselves.
Spend what you've got; the Rootways have been swallowing runners whole this
week."*

**Vocabulary (Beetle), 1/10 → 9/10**
Before: *"Ah, Gold! Much appreciated, friend. Every coin you bring in keeps my
shop stocked and ready for ya!"*
After: *"Each bit of Bloom you carry back from the dark takes root here. The
Rootways give so little — I'm glad some of it finds its way home."*
(Beetle shouldn't know about Gold or "his shop" — that's Snail's thing.)

**Formatting (Beetle), 2/10 → 9/10**
Before: a full paragraph with asterisk stage directions and internal monologue.
After: *"Gave you maybe one-in-four odds walking in. Your Bloom's waiting — you've
more than earned it."*

All three are real output from one live run — full trace in
`Claude/output/style_guide_pipeline_result.json`.

## Where this fits

This runs right after my Assignment #4 content generators (WarrenDialogue,
BestiaryFlavor, SporeFlavor) and before the Critic Agent, so every line gets
scored and auto-fixed for tone, vocabulary, and formatting before a human ever
sees it.
