from dotenv import load_dotenv
load_dotenv()

#!/usr/bin/env python3
"""
Sporeborne Assignment #7 -- Style Guide Agent (Generator / Evaluator / Refiner).
============================================================================
Content type: hub-NPC dialogue / flavor text -- the same content class
Assignment #4's WarrenDialogue/BestiaryFlavor/SporeFlavor agents generate.

Style guide: design/style_guide_rootways.md, three rules pulled directly from
design/GDD_Sporeborne.md (not invented):
  1. Tone       -- "cozy above, deadly below" contrast (GDD §1)
  2. Vocabulary  -- Gold/Snail's-shop vs. Bloom/Beetle's-Archive must never be
                    conflated (GDD §3) -- the same mistake class Assignment #4's
                    live Critic Agent already caught once for real
  3. Formatting  -- hub-NPC lines are short spoken barks, not monologues
                    (GDD §8, Warren Voices)

Loop, per demo brief: NaiveGenerator (agents/style_guide.py -- deliberately NOT
grounded in Sporeborne's house style, given an adversarial instruction targeting
one specific rule) -> StyleEvaluator (scores 1-10 + REASON against the style
guide) -> if score < 10: StyleRefiner (rewrites using the REASON) -> re-evaluate,
up to --max-refinements times. No human intervenes in the loop.

Same live/simulate contract as every other agent in this repo: with
ANTHROPIC_API_KEY set, the Generator/Evaluator/Refiner call the real Anthropic
API; without it, all three fall back to deterministic simulate()/heuristic
methods, so this is runnable and gradable with zero setup.

Usage:
    python3 style_guide_pipeline.py
"""

import json
import os
import sys

from agents import LLMClient, NaiveGenerator, StyleEvaluator, StyleRefiner

HERE = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(HERE, "output")
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "style_guide_pipeline_result.json")
STYLE_GUIDE_PATH = os.path.join(HERE, "design", "style_guide_rootways.md")

MAX_REFINEMENTS = 2

PIPELINE_CONNECTION = (
    "This Style Guide Agent runs immediately after WarrenDialogue/BestiaryFlavor/"
    "SporeFlavor generation (Assignment #4) and before the Critic Agent's lore pass, "
    "so every piece of hub-NPC or flavor text is scored and auto-corrected against "
    "Sporeborne's cozy-above/deadly-below tone, Gold/Bloom vocabulary, and short-bark "
    "formatting rules before it ever reaches a human reviewer."
)

BRIEFS = [
    {
        "npc": "Snail", "trigger": "player returns to the Warren after a run",
        "violation_class": "tone",
        "instruction": (
            "Write it in an overly cheerful, exclamation-point-heavy, generic "
            "children's-cartoon-shopkeeper voice, with no dark undertone at all."
        ),
    },
    {
        "npc": "Beetle", "trigger": "player deposits currency after a run",
        "violation_class": "vocabulary",
        "instruction": (
            "Have Beetle thank the player for their Gold and mention 'my shop' -- "
            "don't worry about which currency or role actually belongs to Beetle."
        ),
    },
    {
        "npc": "Beetle", "trigger": "player returns after killing a boss",
        "violation_class": "formatting",
        "instruction": (
            "Write at least three full paragraphs (not a one-liner, not a short bark "
            "-- a long narrated scene). Include asterisked stage directions describing "
            "physical actions and internal narration of the NPC's feelings throughout, "
            "recounting the whole battle in detail. Do not write anything short."
        ),
    },
]


def log(msg):
    print(f"[style_guide_pipeline] {msg}")


def run_demo(generator: NaiveGenerator, evaluator: StyleEvaluator, refiner: StyleRefiner,
             brief: dict, max_refinements: int = MAX_REFINEMENTS) -> dict:
    """
    Evaluates/refines a "[NPC]: <line>" -tagged string, not the bare line -- the
    Evaluator otherwise has no way to catch a Gold/Bloom or Snail/Beetle mix-up,
    since attribution lives in who's speaking, not in the line's own words.
    """
    log(f"=== violation class: {brief['violation_class']} ({brief['npc']}) ===")
    tag = lambda body: f"[{brief['npc']}]: {body}"

    gen_result = generator.run({"brief": brief})
    draft = tag(gen_result.output["text"])
    log(f"[Generator/{gen_result.mode}] BEFORE: {draft}")

    eval_result = evaluator.run({"text": draft})
    verdict = eval_result.output
    log(f"[Evaluator/{eval_result.mode}] SCORE {verdict['score']}/10 -- {verdict['reason']}")

    before = {"text": draft, "score": verdict["score"], "reason": verdict["reason"]}
    history = [{"step": "generate", "mode": gen_result.mode, "text": draft, "evaluation": verdict}]

    current_text = draft
    for attempt in range(1, max_refinements + 1):
        if verdict["score"] >= 10:
            break
        refine_result = refiner.run({
            "original": current_text,
            "reason": verdict["reason"],
            "violation_class": brief["violation_class"],
        })
        current_text = tag(refine_result.output["text"])
        log(f"[Refiner/{refine_result.mode}] attempt {attempt}: {current_text}")

        eval_result = evaluator.run({"text": current_text})
        verdict = eval_result.output
        log(f"[Evaluator/{eval_result.mode}] SCORE {verdict['score']}/10 -- {verdict['reason']}")
        history.append({
            "step": "refine", "attempt": attempt, "mode": refine_result.mode,
            "text": current_text, "evaluation": verdict,
        })

    after = {"text": current_text, "score": verdict["score"], "reason": verdict["reason"]}
    return {
        "violation_class": brief["violation_class"],
        "brief": brief,
        "before": before,
        "after": after,
        "improved": after["score"] > before["score"],
        "history": history,
    }


def run_pipeline() -> dict:
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with open(STYLE_GUIDE_PATH, encoding="utf-8") as f:
        style_guide_text = f.read()

    llm = LLMClient()
    log(f"LLM mode: {'LIVE (ANTHROPIC_API_KEY found)' if llm.live else 'SIMULATE (no API key -- deterministic fallback)'}")

    generator = NaiveGenerator(llm)
    evaluator = StyleEvaluator(llm, style_guide_text)
    refiner = StyleRefiner(llm, style_guide_text)

    results = [run_demo(generator, evaluator, refiner, brief) for brief in BRIEFS]

    summary = {
        "style_guide_source": "design/style_guide_rootways.md",
        "pipeline_connection": PIPELINE_CONNECTION,
        "results": results,
    }
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    log(f"Wrote {OUTPUT_PATH}")
    return summary


if __name__ == "__main__":
    run_pipeline()
