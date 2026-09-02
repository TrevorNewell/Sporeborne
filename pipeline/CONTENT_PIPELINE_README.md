# Assignment #4 — Dynamic Content Pipeline

`content_pipeline.py` generates three pieces of content grounded in the real Sporeborne
GDD (retrieved via `agents/retriever.py`, not the seed JSON `crew.py` uses), then a
shared **Critic Agent** (`agents/critic.py`) independently re-retrieves against each
generated piece and checks it for lore breaks or tone drift before it's considered
done.

```bash
python3 content_pipeline.py                 # normal run
python3 content_pipeline.py --inject-break   # deliberately breaks the Warren dialogue
                                              # draft, for a deterministic offline
                                              # demonstration of the same catch-and-
                                              # correct path shown below with live output
```

Everything below is **live output** — `ANTHROPIC_API_KEY` was set and every agent
(`BestiaryFlavor`, `SporeFlavor`, `WarrenDialogue`, `Critic`) called the real Anthropic
API, not the deterministic fallback. Pulled directly from `output/content_pipeline_result.json`,
not paraphrased.

## What was generated, and why these three

All three fill a gap that's real and checkable against the repo, not invented for this
assignment (see `CLAUDE.md` for the full reasoning):

| Content type | The gap |
|---|---|
| Bestiary flavor text | `agents/bestiary.py` outputs only `hp`/`damage`/`attack_pattern` — zero lore description exists for any enemy. |
| Spore flavor text | No spore content exists anywhere in the repo — no data file, no agent output — despite GDD §7 committing 15 spores to the shippable MVP. |
| Warren dialogue | GDD §4 names "Hades-style" evolving hub-NPC dialogue as core to the storytelling pillar; none has been authored. |

## Retrieval: query → chunk → output

Retrieval is TF-IDF + cosine similarity over `design/GDD_Sporeborne.md`, chunked by its
11 numbered `##` sections (`agents/retriever.py`). No vector DB or embedding API — the
corpus is one ~10-page file, and the lightest approach that satisfies "show your work"
is the right one here.

### 1. Bestiary flavor text

**Input:** `rootways_root_lasher_07`, a real enemy row pulled from `crew.py`'s own last
output (`output/rootways_combat_07_package.json`), not a fixture invented for this
assignment.

**Query:** `"Blight rotting corrupted twisting root-caverns creatures Eldercap corrupted warden beetle Gatekeeper tone dark underneath cozy"`

**Retrieved chunks:**
| Score | Chunk |
|---|---|
| 0.1172 | § 4 · World & Narrative |
| 0.1124 | § 5 · Levels & Progression |
| 0.0631 | § 1 · Executive Summary |

**Output (live):**
> The Blight doesn't rot the roots so much as remind them what they were before they
> learned patience. A Root Lasher has forgotten the slow work of holding the Eldercap
> together — now it only remembers the swing. Step wrong on the platforms it's wound
> itself beneath, and the creak you hear isn't the wood settling.

Uses "the Blight" and "the Eldercap" (§4, not in the seed JSON) and reframes the
enemy's own mechanical hazard tag (`collapsing_platform`) as the diegetic "creak" —
grounded in both the room it actually spawns in and the world lore, not generic.

**Critic verdict: PASS** (query built from this text, retrieved §4/§1/§5 independently,
found nothing to flag.)

### 2. Spore flavor text

**Input brief:** category `Ring`, mechanical intent "punishes reckless dashing near
hazards."

**Query:** `"new spore Ring category triggered effect on-dodge on-kill on-hurt rarity mythic blighted curse naming Cap Gill Ring"`

**Retrieved chunks:**
| Score | Chunk |
|---|---|
| 0.2631 | § 2 · Game Mechanics |
| 0.0886 | § 10 · Next Phase & Vision |
| 0.0436 | § 3 · Heroes |

**Output (live):**
```json
{
  "spore_id": "ring_brambleveil",
  "name": "Brambleveil Ring",
  "category": "Ring",
  "rarity": "Rare",
  "mechanical_effect": "On-dodge: if the player rolls within 1.5 tiles of a hazard (pit edge, projectile zone, or environmental damage field), the invulnerability window is cut to 0.1s and the player suffers a 'Snagged' debuff for 3s — reducing dodge cooldown recovery by 40% and dealing 8% max HP in thorned recoil damage. Dodging cleanly away from hazards is unaffected.",
  "flavor_text": "The mycelium remembers every reckless root that lunged into the rot-water. It does not forgive the second."
}
```

`Ring` category (on-dodge trigger) and the `[Adjective] Ring` naming pattern both come
straight from §2's spore-category table and its Sporecloud Ring example. The mechanical
effect is stated relative to the GDD's own dodge baseline (§2: 0.3s i-frames / 0.8s
cooldown), not invented numbers in a vacuum.

**Critic verdict: PASS**

### 3. Warren dialogue

**Input brief:** NPC `Snail`, trigger "after depositing Bloom for the first time."

**Query:** `"Snail shop Warren hub NPC dialogue between-run cozy warm rescued critters Gold Bloom currency storytelling drip-feed"`

**Retrieved chunks:**
| Score | Chunk |
|---|---|
| 0.2107 | § 4 · World & Narrative |
| 0.1124 | § 1 · Executive Summary |
| 0.1091 | § 5 · Levels & Progression |

**Output (live):**
> "Bloom! Actual Bloom. I haven't seen anyone come back with that since — well. You
> know."
> "Beetle will put it to good use, I'm sure. More spores in the pool means more
> peculiar things to sell you. Good for both of us, really."
> "Don't spend it all at once. Actually — spend it however you like. You're the one
> going back down."

This is where the pipeline caught a real mistake — see below.

## The Critic Agent: what it caught

There is no Critic Agent anywhere in the GDD's own 9-agent architecture (§8) — Loremaster
authors lore, Data Validator enforces a structural rule-set, and neither is
lore/tone-aware. This is new scope built for this assignment, not a relabeled existing
role (see `agents/critic.py`'s docstring and `CLAUDE.md` for the full reasoning).

It's shared across all three content types (parameterized by `content_type`) rather than
one critic per type, and it runs **its own retrieval pass** — a query built from the
generated text itself, searched against the whole GDD — rather than reusing the chunks
generation retrieved. That matters: a critic that only re-checks against the same
evidence that produced the content isn't independent verification, it's a rubber stamp.
It showed up concretely here: the critic's own query for the Warren dialogue retrieved
§7 and §3 — sections generation never touched — which is exactly what caught the issue
below.

This catch is **organic, not staged** — nothing was deliberately broken. The live
generator, unprompted, wrote a line giving Snail credit for the spore pool:

**Critic verdict: FAIL — 2 issues caught**

| Type | Found | Why it's wrong |
|---|---|---|
| lore_break | `"More spores in the pool means more peculiar things to sell you."` | GDD §5 · Meta-progression & Economy cleanly separates the two hub NPCs by function: Snail runs the in-run Gold shop; Beetle runs the Spore Archive where Bloom unlocks spores into the drop pool. Snail doesn't sell spores and doesn't benefit from the pool expanding — this line collapses the two-currency, two-NPC structure the GDD treats as a design pillar. |
| tone_drift | `"Good for both of us, really."` | Sitcom-chipper phrasing that softens the GDD's "cozy above, deadly below" voice — Snail's self-interest should read dry, not upbeat-salesperson. |

**Corrected output** (same JSON structure back, only the flagged line changed):
```json
{
  "npc": "Snail",
  "trigger": "after depositing Bloom for the first time",
  "lines": [
    "Bloom! Actual Bloom. I haven't seen anyone come back with that since — well. You know.",
    "Beetle will put it to good use, I'm sure. More spores unlocked means more interesting runs. Better for you, marginally better for my foot traffic.",
    "Don't spend it all at once. Actually — spend it however you like. You're the one going back down."
  ]
}
```

The other two content items (bestiary flavor, spore flavor) went through the same live
critic, unmodified, and both came back `PASS` — it isn't flagging everything by default,
only what's actually wrong.

For a fully offline, deterministic demonstration of the same catch-and-correct path
(no API key required), `--inject-break` deliberately appends a line with generic-fantasy
tone drift and a wrong currency/honorific to the Warren dialogue draft, and the
simulate-mode critic — a small set of explicit phrase → grounded-correction rules, see
`agents/critic.py` — catches and corrects it the same way. That path is documented in
the file's git/Perforce history and still runs; it's kept as the zero-setup fallback,
not the headline example, now that live output demonstrates the real thing.

## Does it sound like the game?

Yes. Every generated piece uses vocabulary and facts that only exist in the real GDD
(Eldercap, the Blight, Doorwarden, Gold vs. Bloom, the Rootways, the 0.3s/0.8s dodge
baseline) rather than generic fantasy filler — and the Warren dialogue catch shows the
pipeline isn't just producing plausible-sounding text, it's producing text a second,
independently-retrieving pass can hold accountable to specific GDD facts.

## Implementation notes

- **Live vs. simulate:** every agent (`BestiaryFlavor`, `SporeFlavor`, `WarrenDialogue`,
  `Critic`) calls the real Anthropic API when `ANTHROPIC_API_KEY` is set, same as
  `crew.py`; without it, each falls back to a deterministic `simulate()`, so the
  pipeline is still runnable and gradable with zero setup.
- **`corrected_output` has the same shape in both modes.** Live mode is prompted to
  return a corrected JSON object with the same keys as the input, not a flattened
  string — this was an actual bug caught while getting live output (`build_prompt` was
  originally asking for a `corrected_text` string while `simulate()` returned a
  structured `corrected_output`); fixed so both modes are consistent for anything
  downstream that reads this file.
- **Retrieval is deliberately not a vector DB.** The GDD is one file; TF-IDF over
  section-sized chunks is enough to demonstrate query → chunk → output, and a heavier
  stack would be solving a problem this corpus doesn't have.
