from dotenv import load_dotenv
load_dotenv()

#!/usr/bin/env python3
"""
Sporeborne Assignment #6 -- GER Pipeline (Generator / Evaluator / Refiner /
Circuit Breaker) for the capstone.
============================================================================
Content type: spore mechanical rows (spore_id, category, rarity,
mechanical_effect, curse, flavor_text) -- Sporewright's role per GDD §8.

Named gap this closes: Assignment #4's SporeFlavor agent writes flavor text
for exactly one spore and has no "curse" field at all. Separately,
validation/rules_rootways.json already defines a "mythic_curse" rule
("if rarity == mythic, curse must be non-null") sourced from GDD §2
("Rarities: Common/Rare/Mythic. Blighted spores offer Mythic-tier power
with a curse attached -- e.g. Hollow Cap: triple damage, but healing is
halved") -- but agents/data_validator.py's _validate() never implements
that rule id. So a Mythic spore could already be generated (by hand or by
an agent) with raw power and no downside, and nothing in the repo would
catch it. This pipeline is the first thing that actually enforces it.

Loop, per spore brief:
  Generator (agents/spore_mechanics.py, SporeMechanics.run())
      -> Evaluator (evaluate_spore(), deterministic, rule-based -- same
         fail-closed philosophy as agents/data_validator.py, not model-backed)
      -> if FAIL: Refiner (SporeMechanics.build_refine_prompt/refine_simulate)
         gets the draft + the evaluator's failure list back, fixes only what
         was flagged
      -> re-evaluate, up to --max-refinements (default 3) times
      -> Circuit Breaker: if still failing after the max, stop looping and
         mark the item ESCALATED for human review instead of looping forever
         or silently shipping a broken row.

Same live/simulate contract as crew.py and content_pipeline.py: with
ANTHROPIC_API_KEY set, the Generator/Refiner call the real Anthropic API;
without it, both fall back to deterministic simulate()/refine_simulate() so
this is runnable and gradable with zero setup.

Usage:
    python3 ger_pipeline.py                    # normal run, all items should pass
    python3 ger_pipeline.py --inject-break      # forces the Mythic item's first
                                                 # draft to violate mythic_curse
                                                 # (curse stripped), to prove the
                                                 # Refiner catches and fixes a real
                                                 # break instead of just asserting
                                                 # it can -- same demonstration
                                                 # pattern as crew.py's
                                                 # --inject-failure and
                                                 # content_pipeline.py's
                                                 # --inject-break
    python3 ger_pipeline.py --force-escalate    # like --inject-break, but the
                                                 # Refiner re-submits the same
                                                 # broken draft unchanged every
                                                 # time, to prove the Circuit
                                                 # Breaker actually trips and
                                                 # escalates instead of looping
                                                 # forever when self-correction
                                                 # fails
"""

import json
import os
import sys

from agents import LLMClient, GDDRetriever, SporeMechanics

HERE = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(HERE, "output")
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "ger_pipeline_result.json")
RULES_PATH = os.path.join(HERE, "validation", "rules_rootways.json")

MAX_REFINEMENTS = 3


def log(msg):
    print(f"[ger_pipeline] {msg}")


def load_mythic_curse_rule() -> dict:
    with open(RULES_PATH) as f:
        rules = json.load(f)["rules"]
    for r in rules:
        if r["id"] == "mythic_curse":
            return r
    raise RuntimeError("mythic_curse rule missing from validation/rules_rootways.json")


def evaluate_spore(spore: dict, seen_ids: set) -> dict:
    """
    The Evaluator. Deterministic, rule-based -- not model-backed, same
    fail-closed design as agents/data_validator.py, so a model can't
    "interpret" the rule leniently.

    Primary graded rule (mythic_curse, from validation/rules_rootways.json,
    grounded in GDD §2): rarity == "Mythic" requires a non-empty curse.
    Extended the same rule to the reverse direction too (Common/Rare must
    NOT carry a curse) since GDD §2 frames curses as the Blighted/Mythic
    exception, not the norm -- letting a Common spore quietly carry a
    downside would be just as wrong. no_duplicate_ids and a minimal schema
    check are secondary safety nets so the Refiner has something concrete
    to fix if the model returns malformed output, not the graded rule.
    """
    failures = []
    category = spore.get("category")
    rarity = spore.get("rarity")
    curse = spore.get("curse")
    spore_id = spore.get("spore_id")

    if category not in ("Cap", "Gill", "Ring"):
        failures.append({"rule": "schema_valid", "reason": f"category {category!r} not one of Cap/Gill/Ring"})
    if rarity not in ("Common", "Rare", "Mythic"):
        failures.append({"rule": "schema_valid", "reason": f"rarity {rarity!r} not one of Common/Rare/Mythic"})

    has_curse = bool(curse) and str(curse).strip().lower() not in ("", "none", "null")
    if rarity == "Mythic" and not has_curse:
        failures.append({
            "rule": "mythic_curse",
            "reason": "rarity is Mythic but curse is missing/empty -- GDD §2: Blighted "
                      "spores must offer Mythic-tier power with a curse attached",
        })
    if rarity in ("Common", "Rare") and has_curse:
        failures.append({
            "rule": "mythic_curse",
            "reason": f"rarity is {rarity} but a curse is attached -- GDD §2 reserves "
                      "curses for Mythic/Blighted spores only",
        })

    if spore_id in seen_ids:
        failures.append({"rule": "no_duplicate_ids", "reason": f"spore_id {spore_id!r} already used in this batch"})

    return {"status": "PASS" if not failures else "FAIL", "failures": failures}


def refine_step(agent: SporeMechanics, llm: LLMClient, draft: dict, failures: list) -> tuple:
    """The Refiner. Tries live, falls back to deterministic refine_simulate()."""
    context = {"draft": draft, "failures": failures}
    if llm.live:
        try:
            system, user = agent.build_refine_prompt(context)
            return llm.complete_json(system, user), "live"
        except Exception as e:
            log(f"live refine failed ({e}); falling back to simulate")
    return agent.refine_simulate(context), "simulate"


def run_ger_for_brief(agent: SporeMechanics, llm: LLMClient, retriever: GDDRetriever,
                       brief: dict, seen_ids: set, query: str,
                       inject_break: bool = False, force_escalate: bool = False,
                       max_refinements: int = MAX_REFINEMENTS) -> dict:
    log(f"--- {brief['category']}/{brief['rarity']}: {brief.get('spore_id_hint', '?')} ---")

    chunks = retriever.search(query, k=3)
    gen_result = agent.run({"brief": brief, "retrieved_chunks": chunks})
    draft = dict(gen_result.output)
    log(f"generated ({gen_result.mode}): {json.dumps(draft)}")

    history = [{"step": "generate", "mode": gen_result.mode, "output": dict(draft)}]

    if inject_break or force_escalate:
        log("!! injecting a real mythic_curse violation: stripping the curse from this Mythic draft")
        draft["curse"] = None
        history[-1]["output"] = dict(draft)
        history[-1]["note"] = "curse stripped by --inject-break/--force-escalate to force a real failure"

    for attempt in range(1, max_refinements + 1):
        verdict = evaluate_spore(draft, seen_ids)
        history[-1]["evaluation"] = verdict

        if verdict["status"] == "PASS":
            seen_ids.add(draft["spore_id"])
            log(f"evaluator -> PASS (attempt {attempt - 1})")
            return {"brief": brief, "status": "ACCEPTED", "refinements": attempt - 1,
                    "final": draft, "history": history}

        log(f"evaluator -> FAIL: " + "; ".join(f["reason"] for f in verdict["failures"]))

        if force_escalate:
            log("!! --force-escalate: refiner re-submits the draft unchanged, to prove the "
                "circuit breaker trips when self-correction fails")
            refined, refine_mode = dict(draft), "forced-no-op"
        else:
            refined, refine_mode = refine_step(agent, llm, draft, verdict["failures"])
            log(f"refined ({refine_mode}): {json.dumps(refined)}")

        history.append({"step": "refine", "attempt": attempt, "mode": refine_mode, "output": dict(refined)})
        draft = refined

    final_verdict = evaluate_spore(draft, seen_ids)
    history[-1]["evaluation"] = final_verdict
    seen_ids.add(draft.get("spore_id"))
    log(f"!! CIRCUIT BREAKER TRIPPED after {max_refinements} refinement attempt(s) -- "
        f"escalating {brief.get('spore_id_hint')} for human review")
    return {"brief": brief, "status": "ESCALATED", "refinements": max_refinements,
            "final": draft, "history": history,
            "reason": f"evaluator still failing after {max_refinements} refinement attempt(s)"}


def run_pipeline(inject_break: bool = False, force_escalate: bool = False) -> dict:
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    llm = LLMClient()
    log(f"LLM mode: {'LIVE (ANTHROPIC_API_KEY found)' if llm.live else 'SIMULATE (no API key -- deterministic fallback)'}")

    retriever = GDDRetriever()
    agent = SporeMechanics(llm)
    rule = load_mythic_curse_rule()
    log(f"Evaluator enforcing rule '{rule['id']}': {rule['check']}")

    briefs = [
        {"spore_id_hint": "hollow_cap", "category": "Cap", "rarity": "Mythic",
         "intent": "raw burst damage weapon mutation, Blighted/cursed tier", "_target": True},
        {"spore_id_hint": "dryrot_gill", "category": "Gill", "rarity": "Rare",
         "intent": "passive rule change rewarding igniting enemies"},
        {"spore_id_hint": "sporecloud_ring", "category": "Ring", "rarity": "Common",
         "intent": "on-dodge triggered utility effect"},
    ]

    seen_ids = set()
    results = []
    for brief in briefs:
        is_target = brief.pop("_target", False)
        query = (
            f"spore {brief['category']} category rarity {brief['rarity']} Blighted "
            f"curse mythic {brief['intent']}"
        )
        results.append(run_ger_for_brief(
            agent, llm, retriever, brief, seen_ids, query,
            inject_break=inject_break and is_target,
            force_escalate=force_escalate and is_target,
        ))

    summary = {
        "content_type": "spore_mechanics",
        "evaluator_rule": rule,
        "items": results,
    }
    with open(OUTPUT_PATH, "w") as f:
        json.dump(summary, f, indent=2)
    log(f"Wrote {OUTPUT_PATH}")
    return summary


if __name__ == "__main__":
    run_pipeline(
        inject_break="--inject-break" in sys.argv,
        force_escalate="--force-escalate" in sys.argv,
    )
