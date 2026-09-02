# Assignment #10 — Complete AI Dev Pipeline

## Student & Game Overview

**Student Name:** Trevor Newell
**Capstone Game Title:** Sporeborne
**Game Concept Brief:** A cozy-but-deadly 2D side-scrolling roguelike (Unreal
Engine 5, Paper2D/PaperZD). Morel, granddaughter of the last Doorwarden, descends
into the Blight-corrupted Rootways beneath the Warren, grafting spores onto a
fixed spear-and-buckler kit to fight her way toward The Gatekeeper — chasing the
trail her grandmother left behind and never returned from.

## Deliverable 1: Playable Link

**Playable Game Link:** https://claude.ai/code/artifact/3562bd96-0f71-43cd-b72f-de6cc6f22d63

A browser-playable slice — no engine, no install, no download, opens and plays
immediately. A real loop: four rooms (Mossy Antechamber → Spore Causeway →
Root Gauntlet → The Warden's Hollow, the first three matching the capstone's
Unreal room sequencer's own rooms), enemy count and toughness ramping up each
room, ending in a stronger named guardian encounter before a completion state —
"The guardian falls. You've reached the Gatekeeper's door." — restartable with
R. Movement, jump, dodge-with-i-frames (0.3s/0.8s cooldown, matching the GDD),
and attack (enemies have real HP, shown via on-screen health bars) are all
playable. It displays the same real pipeline-generated content described in
Deliverable 2 directly on the page.

This was chosen deliberately over the actual Unreal build: a real, working
Windows packaged build of the capstone *does* exist (confirmed compiling,
packaging, and running — see the Engine Integration note below) and could be
uploaded to itch.io instead, but the browser version was kept as the submitted
link for the "play within 2 minutes, no setup" gate specifically, since it has
no download step at all.

**⚠️ Before submitting: this link must be shared from its page's share menu —
Artifacts are private by default, and a grader opening a private link will hit
a login wall.**

## Deliverable 2: Pipeline Source Code & Engine Integration

**Pipeline Repository Link:** https://github.com/TrevorNewell/Sporeborne
**Pipeline Run Video Link:** *[not yet recorded — see Manual Steps below]*

**Target Game Engine:** Unreal Engine 5.8 (capstone development target) — the
submitted playable link runs on a WebGL/Phaser fallback (see note below).

**Automated Flow Description:** `content_pipeline.py` (in the repo above)
generates bestiary flavor text, spore flavor text, and Warren hub-NPC dialogue,
each checked by a Critic Agent that runs its own independent GDD-retrieval pass
before anything is accepted, and writes `output/content_pipeline_result.json`.

The capstone itself is built in Unreal Engine 5.8: a copy of that exact JSON is
staged into the project at `Content/PipelineData/content_pipeline_result.json`,
and a `USporeborneContentDisplaySubsystem` (a `UGameInstanceSubsystem` that
self-activates on level start, no manual Blueprint/level wiring) parses it at
runtime with Unreal's JSON module and displays the real generated lines
on-screen — preferring each item's Critic-corrected text where the verdict was
FAIL. This compiles clean and **was confirmed packaged and working**: a real
standalone Windows build exists and was verified to have the exact JSON file
staged inside its `.pak` (checked directly with `UnrealPak.exe -list`), at the
same content path the runtime code resolves.

**For the submitted playable link**, the same JSON is embedded directly in a
small browser build (Phaser) instead — same principle (the pipeline's own
output file drives what's displayed, no hand-retyped content), different
runtime, chosen for the zero-download play experience the gate criterion wants.
The Unreal build is real and available as supporting evidence that the
in-engine integration works end to end, not just in the browser fallback.

## Deliverable 3: Pipeline Audit & Cost Analysis

### Pipeline Production & Functionality

**What the pipeline produced, present in the playable build:** three pieces of
real generated content — one bestiary-enemy flavor-text line, one new spore
(mechanical effect + flavor text), and one Warren hub-NPC dialogue exchange
(Snail, triggered on first Bloom deposit) — displayed on-screen at run start,
sourced live from `content_pipeline_result.json`. Two of the three items failed
their first Critic pass (a lore break confusing Snail's Gold-shop role with
Beetle's Bloom-Archive role, and generic tone drift away from the GDD's
"cozy-above/deadly-below" voice) and were corrected before being shown — the
build displays the corrected versions.

**What manual steps remain:**
1. Recording the pipeline-run video — not done by this submission; screen
   recording isn't something the pipeline or its tooling does itself.
2. Uploading the real Unreal build to itch.io as an optional alternative
   download — the build itself is done and verified working, only the upload
   is manual (`butler push` can automate this, not yet wired up).
3. Real enemy/spore art — the build currently reuses the base template's
   placeholder "Fox" sprite flipbooks; the content pipeline generates text, not
   pixel art, and no art-generation pipeline exists yet.
4. A handful of gameplay systems (procedural room sequencing, telegraphed
   enemy attacks, player dodge/combo) were built this same project cycle but
   some remain only editor-verified, not yet exercised in a live in-editor
   playtest — noted here for honesty, not hidden.

**What it would take to eliminate them:** (1)/(2) are scriptable —
`ffmpeg`/OS screen-capture plus `butler push` in a small wrapper script would
close both without a human in the loop. (3) needs an actual art-generation
pipeline (a Pixel Lab AI integration was scoped but not started — blocked on
account setup). (4) needs either headless functional-test coverage or accepted
manual QA passes before each milestone; both are real engineering investments,
not one-line fixes.

### Architectural Reflection

**Current architectural decision to change:** `agents/llm_client.py` — the
shared Anthropic API wrapper every pipeline in this project uses — never
captured `response.usage` until this assignment forced it. Every prior live run
across five earlier assignments had real API cost with zero real cost
visibility; all prior cost figures in this project were estimates, not measured
data.

**Specific alternative:** Build usage accumulation (and per-call labeling) into
`LLMClient` from the very first agent, not bolted on under a deadline. Every
pipeline in this repo already shares one client class specifically so a fix like
this only has to happen once — that architecture was right; using it for cost
visibility from day one, not just live/simulate fallback, was the miss.

### Cost Analysis

**Total Actual Run Cost:** **$0.053055** — `content_pipeline.py`'s real, live
run (Claude Sonnet 4.6), the same run whose output is in the playable build.
Measured directly from `response.usage` on all 6 live API calls the run makes
(3 generation + 3 Critic-Agent evaluation), not estimated.

**Most Expensive Pipeline Step:** Not generation — the **Critic Agent's
evaluation calls**, specifically when a violation is found. Across the 6 calls,
the 3 generation calls cost $0.02158 combined; the 3 Critic calls cost $0.03147
combined — the Critic phase is ~59% of total run cost despite being "just" a
check, because every flagged issue gets a full written explanation on top of the
verdict.

**Solo/Small-Team Sustainability:** Yes, comfortably, at this scale. $0.053 for
3 content items with independent lore/tone review is trivial per-item cost
(~$0.018/item); generating the GDD's full committed content list (15 spores,
a full bestiary) at this rate would still land under $2 total. The real
sustainability question isn't per-run cost, it's re-run frequency during
iteration — which is exactly what the mid-project change below targets.

### Mid-Project Cost-Reduction Change

**Strategy/Prompting Approach:**
- **Before:** The Critic Agent's prompt asked it to "explain what you changed
  and why, citing the GDD excerpt that grounds the correction" with no length
  guidance — on a FAIL verdict it wrote full, multi-sentence explanations per
  issue.
- **After:** Added one constraint to the same prompt: *"Keep each issue's
  explanation to ONE sentence, max ~25 words — name the contradiction and the
  GDD section, don't restate the full excerpt or narrate at length."*

**Token / API Cost — Before vs. After (both real, measured, back-to-back runs
of the identical pipeline, same content type mix):**

| | Before | After | Change |
|---|---|---|---|
| Total input tokens | 11,529 | 11,340 | -1.6% |
| Total output tokens | 1,674 | 1,269 | **-24.2%** |
| Total run cost | $0.059697 | $0.053055 | **-11.1%** |
| Most expensive single call | $0.016152 (680 out tok) | $0.012018 (456 out tok) | -25.6% |

The reduction is concentrated exactly where predicted — the two Critic calls
that found real issues (out of 3) dropped 19-26% each; the calls with nothing to
flag were essentially unaffected, since the constraint only engages when there's
substantial explanation text to write in the first place.
