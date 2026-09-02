# Assignment #6 — GER Pipeline for Sporeborne

**Game:** Sporeborne (2D side-scrolling roguelike, UE5). **Content type:** spore
mechanical rows — `spore_id`, `category` (Cap/Gill/Ring), `rarity`
(Common/Rare/Mythic), `mechanical_effect`, `curse`, `flavor_text`.

## Pre-Build Declaration

**What content type does your game currently generate manually, inconsistently, or
not at all?** Spore mechanical rows aren't generated at all. Assignment #4's
`SporeFlavor` agent writes flavor text for exactly one spore and has no `curse`
field; no mechanical spore data (rarity-bearing, gameplay-affecting rows) exists
anywhere in the repo, despite GDD §7 committing 15 spores to the MVP.

**What specific rule from your GDD must every piece of that content satisfy?**
GDD §2: "Rarities: Common/Rare/Mythic. Blighted spores offer Mythic-tier power with
a curse attached — e.g. Hollow Cap: triple damage, but healing is halved." Every
Mythic spore must carry a real curse; Common/Rare spores must not.

**What does a failure look like, concretely, in your game's terms?** A Mythic spore
with raw power and zero downside — free triple damage, no cost. That breaks the
"cozy but deadly" pillar: Mythic loot should be a gamble, not a strict upgrade.
`validation/rules_rootways.json` already names this rule (`mythic_curse`), but
`agents/data_validator.py` never actually implements it — nothing in the repo
currently catches this.

## Pipeline

`Claude/ger_pipeline.py`, using `agents/spore_mechanics.py`'s `SporeMechanics` agent:

1. **Generator** — `SporeMechanics.run()`, grounded via TF-IDF retrieval
   (`agents/retriever.py`) over `design/GDD_Sporeborne.md`. Given a category/rarity/
   intent brief, writes one candidate spore.
2. **Evaluator** — `evaluate_spore()` in `ger_pipeline.py`, deterministic and
   rule-based (never model-backed, same fail-closed design as
   `agents/data_validator.py`). Primary rule: `mythic_curse` — `rarity == "Mythic"`
   requires a non-empty `curse`; `Common`/`Rare` must *not* carry one (the reverse
   direction, since GDD §2 frames curses as the Mythic exception, not the norm).
   Secondary checks (`schema_valid`, `no_duplicate_ids`) exist only so the Refiner
   has something concrete to fix if a live call returns malformed output.
3. **Refiner** — on FAIL, `SporeMechanics.build_refine_prompt`/`refine_simulate` gets
   the draft plus the Evaluator's failure list and fixes only what was flagged,
   leaving everything else untouched. Tries live, falls back to a deterministic
   simulate on failure — same live/simulate contract as every other agent.
4. **Circuit Breaker** — the loop in `run_ger_for_brief()` retries up to
   `--max-refinements` (default 3). If the Evaluator still fails after that, the
   item is marked `ESCALATED` with the full attempt history instead of looping
   forever or silently shipping a broken row.

Three demo modes (`python3 ger_pipeline.py [--inject-break | --force-escalate]`),
same pattern as `crew.py --inject-failure` and `content_pipeline.py --inject-break`:
normal run, a forced real violation that gets self-corrected, and a forced violation
that can't self-correct so the Circuit Breaker has to trip.

## Did it catch something I would have missed?

Yes, twice, in the same live run (`--inject-break`, `ANTHROPIC_API_KEY` set):

- **The rule itself.** `mythic_curse` was already written into
  `validation/rules_rootways.json` from Assignment #3, but `data_validator.py` never
  implemented it — a real, pre-existing gap in this repo, not a hypothetical one.
- **A genuine live-mode failure, live.** During the `--inject-break` run, the
  Refiner's real Anthropic call came back as text that failed JSON parsing
  (`model response was not valid JSON`). The pipeline logged the failure and fell
  back to the deterministic `refine_simulate()`, which added a valid curse and the
  Evaluator passed on the next check — the fallback path this project always builds
  for live-call failure actually engaged, unprompted, not just in a hand-crafted
  demo.
- **The Circuit Breaker really trips.** `--force-escalate` runs a Mythic draft with
  its curse stripped through 3 refinement attempts where the Refiner is forced to
  resubmit it unchanged; the pipeline correctly stops after the max and marks it
  `ESCALATED` rather than looping or silently accepting it.

Full traces for all three modes are in `Claude/output/ger_pipeline_result.json`
(each run overwrites it — the version currently on disk is the `--inject-break` run,
showing FAIL → refine → PASS).
