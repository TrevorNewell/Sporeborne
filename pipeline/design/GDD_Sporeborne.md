# Sporeborne — Game Design Document

> Transcribed from `GDD_Sporeborne_Final.pdf` (V0.2, rev. July 30 2026) at the repo root.
> The source PDF has no extractable text layer — its text was flattened to vector
> outline paths (a Figma/Canva-style export), so `pdftotext`/`pypdf` return nothing.
> This transcription was produced by rasterizing each page (PyMuPDF) and reading the
> images directly. Treat this file as the canonical plain-text GDD source for any
> retrieval/RAG pipeline — chunk this, not the PDF.

*A cozy little knight against a very deadly blight.*
2D side-view roguelike · Solo dev + AI agents · Unreal Engine 5 · Capstone (MAS for Game Dev)

## 1 · Executive Summary

Sporeborne is a 2D side-scrolling roguelike about **Morel**, a tiny mushroom-folk knight
who descends into the blighted roots beneath her home to learn what became of her
grandmother — the last knight to go down and never return. Each run is a fresh descent
through procedurally reordered handcrafted rooms: dodge readable projectile patterns,
clear a room, then **graft a spore** onto yourself. Spores mutate how you fight, and the
right combination breaks the run wide open. Cute on the surface, dark underneath —
Binding of Isaac's tonal range with Dead Cells' movement feel.

| | | |
|---|---|---|
| **Genre** | Roguelike action | |
| **Players** | Single-player (MVP) | |
| **Session** | 20–40 min runs | |
| **Engine** | Unreal 5 · Paper2D/PaperZD | |
| **Team** | Solo dev + AI agents | |
| **MVP scope** | 1 hero · 1 zone · 1 boss | |

**Win/loss condition.**
Win (MVP): defeat **The Gatekeeper**, the boss at the bottom of the Rootways. That boss
kill is the committed win state of the vertical slice — the whole MVP is a complete,
winnable game, not a fragment.
Lose: Morel's hearts reach zero anywhere in the dungeon; the run ends and you return to
the Warren with only your Bloom and any critters rescued that run (roguelike permadeath
— meta-progression persists, the run does not). There is no timer and no score; mastery
is measured by how deep and how cleanly a build carries you. (Full-game win — reaching
and defeating the final boss in the Blightheart — is a post-MVP goal; see §10.)

**Design pillars**
- **Every run breaks differently** — Spore grafting exists to be abused. Synergies
  should feel discovered, not designed.
- **Dodging is the dialogue** — Patterns are readable and fair (4/10 bullet-hell
  intensity). Death is always the player's read, not the game's cheat.
- **Cozy above, deadly below** — The warm Warren makes the dark descent land. Contrast
  is the tone.

**Core loop.**
Rest in the Warren → descend into the Rootways → fight room by room, grafting one spore
after each clear → face The Gatekeeper — win the run or fall → return with Bloom and
rescued critters → unlock permanent upgrades → descend again, stronger and stranger.

## 2 · Game Mechanics

**What the player does.**
Moment to moment, the player moves and jumps across a side-view arena, attacks with a
3-hit combo, fires a secondary on a short cooldown, dodges (0.3s of invulnerability,
0.8s cooldown — the core survival verb), and unleashes an ultimate once it charges from
damage dealt. Enemies fire slow, telegraphed volleys (0.4s wind-up flash) — arcs, rings,
and aimed shots that reward reading and positioning over twitch reflexes. Screen-filling
density is reserved for boss phases only; this is a **4/10 bullet-hell**, not a Touhou
wall.

**Spore grafting — the build system.**
After each cleared room the player picks 1 of 3 spores to graft. Spores never replace
your hero's weapon — they mutate how that fixed weapon behaves — so build variety and
single-kit mastery pull in the same direction rather than against each other.

| Category | Effect type | Example |
|---|---|---|
| **Cap** | Weapon mutation — changes how attacks behave | Ember Cap — attacks ignite enemies |
| **Gill** | Passive stat or rule change | Dry Rot Gill — ignited enemies explode on death |
| **Ring** | Triggered effect — on-dodge, on-kill, on-hurt | Sporecloud Ring — dodging leaves a toxic cloud |

**Stacking rules & the power curve.**
Earlier drafts said spores "stack without limit," which is a balance trap. The
committed rules:
- Distinct spores stack freely — depth comes from *combining* categories, not spamming
  one.
- No graft cap — you can keep grafting all run; the build is limited by how deep you
  get, not an arbitrary ceiling.
- Duplicate diminishing returns: the first copy of a spore gives full value; each
  further copy is 10% less effective than the previous copy (geometric decay), so
  stacking one spore keeps paying but never dominates — combining distinct spores stays
  the stronger play.
- Target power curve: cleared-room player power grows ≈15% per room; a full Rootways
  run (10–12 combat rooms) lands the player at roughly **4–5× starting DPS** at the boss
  door. The resistance curve in §5 is tuned to chase this, never to outrun it.

Rarities: **Common / Rare / Mythic**. Blighted spores (the deadly side of
cozy-but-deadly) offer Mythic-tier power with a curse attached — e.g. *Hollow Cap: triple
damage, but healing is halved.*

> **Synergy example — "Wildfire Waltz"**
> Ember Cap (ignite) + Sporecloud Ring (dodge clouds) + Dry Rot Gill (ignited enemies
> explode): the player dodges *through* packs, the cloud ignites, kills chain-explode.
> The core survival verb becomes the primary damage source — the build rewires how you
> play, not just your numbers.

## 3 · Heroes

A hero is a fixed kit — one signature weapon plus a unique secondary, dodge flavor, and
ultimate. You don't swap weapons; you re-contextualize the one you have through spores.
That's the mastery loop: learn one kit deeply, then watch each run reshape it. MVP ships
one hero. Additional heroes are found imprisoned in the dungeon and rescued to the
Warren (see §10).

**Morel, the Doorwarden** — MVP HERO
Spear-and-buckler knight; granddaughter of the last Doorwarden.
- **Attack:** thrust combo, long reach on the third hit.
- **Secondary:** buckler parry — a timed parry reflects projectiles (the bullet-hell
  payoff move that ties dodging and offense together).
- **Dodge:** short ground roll.
- **Ultimate — Rampart Bloom:** raises a wall of mushrooms that blocks projectiles and
  shoves enemies back.

*Design note: every spore is authored and validated against Morel's fixed kit first. A
second hero is only worth adding once its kit re-reads the existing spore pool into new
builds — otherwise it's content, not depth.*

## 4 · World & Narrative

**Setting.** The Eldercap — a colossal ancient mushroom whose roots cradle a warren of
mushroom-folk. A creeping Blight has begun rotting it from below, twisting the
root-caverns and the creatures inside them.

**Hook.** Your grandmother was the last Doorwarden — keeper of the gate between the
Warren and the deep roots. She descended to face the Blight and never came back. You
take up her rusted spear. Each run pushes toward wherever she went.

**The tether.** Grandmother left a trail: one spore-etching (a found lore note) surfaces
per run, always slightly deeper than the last you found, so story progress and dungeon
progress are the same axis. You are literally following her down. This is what keeps a
roguelike's repetition feeling like *pursuit* rather than a treadmill.

**Storytelling.** Hades-style drip-feed: hub NPCs have short, evolving between-run
dialogue, and the etchings reveal what grandmother learned on the way down. No
cutscenes; story never interrupts play.

**The Warren (hub).**
Critters freed from cages in the dungeon return to the Warren and take up jobs — the hub
visibly grows warmer and busier as you play. Snail opens a shop (in-run gold sink),
Beetle runs the Spore Archive (meta-progression, §5), and *(stretch)* Firefly becomes
lamplighter, revealing room maps. Rescues are the emotional reward that makes returning
home matter — and the reason a failed run still ends on something gained.

## 5 · Levels & Progression

**Run structure.**
Handcrafted rooms, procedural order (Hades × Dead Cells hybrid). A run stitches together
**10–12 combat rooms + 2 elite rooms + 2 shop rooms + 1 boss** from a library of **~26
authored templates**, with randomized enemy spawns and hazards inside each template.
Doors preview the next room's reward type, so routing is a live decision, not a coin
flip.

| Zone | Theme | Boss | Scope |
|---|---|---|---|
| **The Rootways** | Tangled roots, warm rot, first Blight tendrils | The Gatekeeper — a corrupted warden beetle | **MVP** |
| **Mireglow Caverns** | Bioluminescent flooded caves, projectile-heavy | The Chorus — a swarm that sings in patterns | Stretch |
| **The Blightheart** | The source. Dark mirror of the Warren | Final boss — grandmother's fate revealed | Stretch |

**The resistance curve (difficulty band).**
Enemy strength scales per room depth, tuned to trail the player power curve in §2 so the
descent stays tense without spiking: **+8% enemy HP and +5% enemy damage per room**
within the Rootways. Elite rooms spike +40% HP for a burst-check. The Gatekeeper is
tuned against a "clean, sensible build at room 10" baseline — beatable without a broken
synergy, but a broken synergy turns the fight into a victory lap. That gap *is* the
reward for build mastery.

**Meta-progression & economy.**
Two currencies, cleanly separated so they never compete: **Gold** is in-run only (spent
at Snail's shop, gone on death) and **Bloom** is persistent (earned per run, spent at
Beetle's Spore Archive). Bloom unlocks new spores into the drop pool, small permanent
perks (+1 heart, +1 shop reroll), and starting boons. **Hero unlocks come from rescues,
not currency.**

**Progression rule:** meta-progression widens options more than it raises numbers. A
fresh player and a veteran face the same danger; the veteran just has a richer build
space to draw from. This keeps the win honest — you beat the Gatekeeper because you
played well, not because you ground out stats.

## 6 · Technical

Unreal Engine 5 with Paper2D + PaperZD for sprites and animation state machines.
Enhanced Input (keyboard + gamepad from day one). Persistence via SaveGame objects.

**Data-driven content.** Spores, heroes, enemies, and room templates are DataTables /
DataAssets, not hardcoded logic. This is the single biggest scope lever: new content is
a row, not a code change, which is exactly what makes an AI content pipeline (§8) safe
on a solo timeline.

**Solo-first, co-op-friendly architecture.** No netcode in MVP, but authority-friendly
patterns from the start: gameplay state lives in actor components, UI never mutates
state directly, and every combat effect routes through a single damage pipeline. Later
co-op becomes a refactor, not a rewrite.

**Art.** ~32 px sprite scale, 2–3 frame animations for MVP, Risk of Rain-style readable
silhouettes. Purchased/placeholder packs are acceptable for the slice; original art is a
polish-phase task.

**Accessibility.** Baseline in MVP: full remappable controls (free via Enhanced Input)
and a colorblind-safe projectile palette (patterns readable by shape and motion, not
color alone — this is load-bearing for a bullet-hell). A deeper accessibility pass
(screen-reader menus, difficulty modifiers, input-timing assists) is explicitly scoped
as a post-MVP cut — named here so it's a decision, not an oversight.

## 7 · Production Plan & Scope

**Constraint:** the MVP must be technically completable in roughly one week with AI
agents (≈48 focused hours for two experienced devs). Everything inside the MVP box is
the contract; everything else is stretch.

**MVP — the shippable, winnable minimum**
- 1 hero (Morel)
- 1 zone: ~26 room templates
- 15 spores (5 per category)
- 3 enemy types + 1 boss (Gatekeeper)
- Win state: defeat the Gatekeeper
- Hub: Snail (shop) + Beetle (Archive)
- Bloom meta: 5+ Archive unlocks
- Keyboard + gamepad, remappable
- Main menu, death & victory screens
- Save/load

**Milestone-gated build (not calendar-locked).**
A fixed hour-by-hour schedule was cut deliberately — a zero-slack timetable is a way to
*discover* you're behind, not a way to stay on track. The build advances through gates
instead; each gate must be provably true before the next opens, and buffer lives between
gates rather than at the end.

| Gate | "Done" means |
|---|---|
| **G1 · Feel** | Move, jump, attack combo, dodge-with-i-frames all feel good in an empty room. (PaperZD spike lands here.) |
| **G2 · Fight** | Enemy AI + telegraphed projectiles + damage pipeline; one room is genuinely fun to clear. |
| **G3 · Build** | Spore DataTable pipeline + 1-of-3 choice UI; a run's build visibly changes how it plays. |
| **G4 · Run** | Procedural room sequencing + door rewards + boss; a full run is winnable and losable. |
| **G5 · Loop** | Hub, Bloom meta-progression, save/load; the between-run loop closes. |
| **G6 · Fill & feel** | Agent content pass to MVP counts, then juice (hit-stop, shake, SFX), playtest, balance, bugfix. |

**Cut lines — checked against the pillars.**
Every cut is ordered so it protects the three pillars. Nothing that's cut removes
"every run breaks differently," "dodging is the dialogue," or "cozy above, deadly
below":

| Cut order | Why it's safe to cut |
|---|---|
| 1. Co-op | The game is designed single-player-complete; co-op adds reach, not the core fantasy. |
| 2. Zones 2–3 | One zone with a real boss is a full loop; more zones deepen, they don't enable. |
| 3. Second hero | Build variety (pillar 1) lives in the spore pool, which one hero already exercises. |
| 4. Blighted spores | A flavor amplifier on "cozy-but-deadly," not the source of it; base spores carry the pillar. |
| 5. Firefly maps | Convenience layer; the run reads fine without it. |

Out of scope entirely: online matchmaking, monetization, localization, the deep
accessibility pass (§6).

## 8 · AI Architecture

Sporeborne is built by a multi-agent dev pipeline: **nine specialized agents**, each
with a narrow job, described here by what the player ends up seeing. Eight are dev-time
content and QA agents; one — **Warren Voices** — runs at runtime and is the only agent a
player ever indirectly meets. Splitting the earlier three roles into nine closes the
real gaps: nothing used to own enemies, lore, the difficulty curve, or rule-enforcement,
so those failures were only caught by human review after the fact.

| Agent | Role (one sentence) & player-facing effect | Runs after |
|---|---|---|
| **Roomsmith** | Authors room-template layouts + spawn tables from a zone theme & difficulty band — the player sees fresh dungeon rooms every run. | — (first) |
| **Bestiary** | Writes enemy rows (stats, attack pattern, telegraph timing, spawn weight) that fit Roomsmith's hazards — the player sees enemies that belong in their rooms. | Roomsmith |
| **Sporewright** | Generates new spore rows from a synergy brief + the full existing pool — the player sees new build options and combos to discover. | parallel |
| **Curvewright** | Sets the power/resistance curve constants (§2/§5) against the current content — the player feels a descent that stays tense, never spikes or trivializes. | Bestiary, Sporewright |
| **Loremaster** | Writes spore-etching lore + pre-authored hub dialogue from a human story outline — the player sees grandmother's trail and a warming Warren. | parallel |
| **Data Validator** | Checks every new/changed row against a human-owned rule-set (caps, forbidden combos, timing constants) and flags — the player never sees a rule-breaking or broken-config item. | all authors |
| **Tester** | Runs automated smoke/integration tests on generated code & assets — the player sees a build that boots and doesn't crash mid-run. | Data Validator |
| **Balancer** | Adjusts existing values from playtest telemetry (deaths, clear times, pick rates) — never adds or removes rows — the player feels fair difficulty and no dead spores. | Validator (re-check) |
| **Warren Voices** | **Runtime.** Generates ≤3 hub-NPC lines from a run summary on the death/victory screen — the player sees NPCs react to the build that just killed (or crowned) them. | runtime tier |

**There is no Critic Agent anywhere in this taxonomy.** Loremaster owns lore generation;
Data Validator owns rule-set enforcement — but it is explicitly deterministic/rule-based
(caps, forbidden combos, timing constants), not content-quality or lore-aware. Neither
agent catches tone drift or a lore contradiction against the GDD. A Critic Agent that
retrieves from the real GDD and visibly corrects a lore break is new scope, not a gap
any existing agent already half-covers.

**Sequencing, triggers & failure handling.**
Content-authoring agents run on-demand per zone; Balancer runs on playtest days only,
human-invoked; Warren Voices runs automatically on every run-end. The dev-time flow is a
gated pipeline — nothing merges without passing the gate:

```
Human defines zone theme + difficulty band
  |
  ├→ Roomsmith → Bestiary ─┐
  |              |          |
  ├→ Sporewright ──────────┤
  |         ├→ Curvewright |
  └→ Loremaster ───────────┘         |
              ▼
     ┌════════════════════┐
     ║ Data Validator +   ║ ← fail-closed gate
     ║ Tester (auto gate) ║
     └════════════════════┘
         |          |
       PASS       FAIL
         |          |
   Human merge   Flagged rows → originating
   review        agent, max 2 retries, then
         |       escalate to human
         ▼
   Import step (JSON/CSV → uasset) → Build
```

- **Trigger & retry:** a failed check returns the specific flagged rows to the agent
  that made them, with the failure reason. Max **2 automatic retries**, then it
  escalates to the human — agents never loop forever.
- **Fail-closed by default:** if the Validator or Tester itself errors or times out, the
  content is **blocked from merging**, not waved through. A check that can't run is
  treated as a failed check.
- **Human is the last gate always:** passing the automated gate makes content *eligible*
  to merge, not merged. A human approves the final merge and owns the import step.

**Ownership boundary.**
- **Agents author:** DataTable rows, standalone assets, tuning deltas, runtime dialogue
  — and, gated by Tester + Validator + human review, code changes too.
- **Always human-owned:** zone themes, difficulty-band definitions, the Validator
  rule-set itself, playtest execution, the import step, and final merge approval.
- **Structural guardrail:** Agents never write binary uassets — they emit JSON/CSV
  intermediates a human import step converts, so every change is reviewable as text.

## 9 · Technical Strategy

§8 defines *what* each agent does for the player; this section covers *how* it runs
feasibly on a solo, roughly-one-week build — the API constraints and the token budget
that keep it grounded.

**API & technical constraints.**
- **Reviewability over autonomy (the load-bearing constraint).** Agents may touch code,
  but every output must arrive as a reviewable diff — text rows, isolated assets, or a
  bounded code change — because a solo dev cannot safely merge sweeping, cross-cutting
  agent edits on this timeline. The Tester + Validator + human-merge gate exists to
  enforce exactly this.
- **Binary assets are off-limits to agents.** Unreal uassets are binary; agents author
  JSON/CSV intermediates and a human-run import step converts them.
- **Runtime calls never block play.** Warren Voices fires only on the death/victory
  screen, is capped at 3 lines/NPC, and ships with a pool of authored fallback lines —
  offline or on failure, the game is identical minus the personalization.
- **Determinism stays local.** Combat, drops, and procedural sequencing are
  deterministic and never depend on a model at runtime. AI touches content creation and
  one cosmetic runtime flourish — never the rules of play.

Full token-budget and per-action cost estimates are in the Appendix (§11), kept out of
the design-facing flow.

## 10 · Next Phase & Vision (Appendix)

Post-MVP directions, in the order they'd protect the pillars while adding reach. Each
cross-references the MVP system it extends so the vertical slice stays the foundation,
not a throwaway.

- **Amanita, the Sporeslinger** → §3 — A second, ranged hero — arcing spore-shots, a
  turret-toadstool secondary, and a Fairy Ring ultimate — that re-reads the existing
  spore pool into new builds.
- **Zones 2–3** → §5 — Mireglow Caverns and the Blightheart — deepening the descent and
  delivering the full-game win: grandmother's fate revealed.
- **Co-op** → §6 — Up to 4-player co-op, enabled by the authority-friendly architecture
  already in the MVP — a refactor, not a rewrite.
- **Firefly maps & Blighted spores** → §2, §4 — Lamplighter map reveals and the
  high-risk Blighted spore tier — flavor and convenience amplifiers on systems the MVP
  already ships.

## 11 · Appendix — Token Budget & Cost Estimates

Estimates for planning only — revise once real prompts are measured. Runtime figures
assume Claude Haiku pricing ($1 / MTok in, $5 / MTok out); dev-pipeline agents will in
practice run on larger models (~10–30× cost) and iterate 2–3× per item.

| Action | Tokens in / out | ~Cost each | At MVP volume |
|---|---|---|---|
| **Warren Voices** (runtime, 1/run-end) | ~1,200 / 250 | ~$0.0025 | **1,000 sessions ≈ $2.50** |
| Sporewright — one spore row | ~2,500 / 500 | ~$0.005 | 15 spores ≈ $0.08 |
| Bestiary — one enemy row | ~3,000 / 600 | ~$0.006 | 4 enemies ≈ $0.02 |
| Roomsmith — one room template | ~10,000 / 3,000 | ~$0.025 | 26 rooms ≈ $0.65 |
| Data Validator / Tester — one pass | ~8,000 / 800 | ~$0.012 | ~60 passes ≈ $0.72 |
| Balancer — one tuning sweep | ~40,000 / 5,000 | ~$0.065 | ~7 sweeps ≈ $0.46 |

**Bottom line:** Even with larger models and 2–3× iteration, the full MVP
content-generation pass should stay **under ~$30 of model spend**. Runtime is the only
per-player cost and is bounded by one capped, fail-safe call per run (~$2.50 per 1,000
sessions).
