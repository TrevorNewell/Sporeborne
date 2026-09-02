from dotenv import load_dotenv
load_dotenv()

#!/usr/bin/env python3
"""
Sporeborne Assignment #4 -- Dynamic Content Pipeline
======================================================
Retrieval-grounded content generation + a shared Critic Agent, sitting
alongside the Assignment #3 crew (crew.py) rather than inside it.

Three named content gaps (locked in, see CLAUDE.md):
  1. Bestiary flavor text  -- enemies have stats but no lore identity.
  2. Spore flavor text     -- zero spore content exists anywhere, despite
                               the GDD (§7) requiring 15 for the MVP.
  3. Warren dialogue       -- GDD §4 names this as core storytelling;
                               none has been authored.

Pipeline per item: form a retrieval query from the content brief -> search
the real GDD (agents/retriever.py, TF-IDF over design/GDD_Sporeborne.md,
not the seed JSON) -> generate grounded on the retrieved chunks -> the
Critic Agent runs ITS OWN retrieval query (built from the generated text,
not reused from generation) -> checks for a lore break or tone drift ->
corrects if it finds one.

Same live/simulate contract as crew.py: with ANTHROPIC_API_KEY set, each
content agent calls the real Anthropic API; without it, every agent falls
back to a deterministic simulate() so this is runnable and gradable with
zero setup. The Critic's simulate() is a real (if narrow) check, not a
stub -- see agents/critic.py.

Usage:
    python3 content_pipeline.py                 # normal run
    python3 content_pipeline.py --inject-break   # deliberately breaks the
                                                  # Warren dialogue draft to
                                                  # demonstrate the Critic
                                                  # actually catching and
                                                  # correcting something,
                                                  # the same way crew.py's
                                                  # --inject-failure proves
                                                  # its retry path
"""

import json
import os
import sys

from agents import LLMClient, GDDRetriever, BestiaryFlavor, SporeFlavor, WarrenDialogue, Critic

HERE = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(HERE, "output")
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "content_pipeline_result.json")


def log(msg):
    print(f"[content_pipeline] {msg}")


def load_existing_enemy():
    """
    Pulls a real enemy row out of Assignment #3's own last output, so the
    Bestiary-flavor piece enriches actual generated content rather than a
    fixture invented just for this assignment.
    """
    path = os.path.join(OUTPUT_DIR, "rootways_combat_07_package.json")
    with open(path) as f:
        package = json.load(f)
    return package["enemies"]["enemies"][0]  # rootways_root_lasher_07


def flatten_text(value) -> str:
    """Concatenates every string in a dict/list, for use as a retrieval query
    or as the text a Critic checks -- no field is skipped."""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return " ".join(flatten_text(v) for v in value.values())
    if isinstance(value, list):
        return " ".join(flatten_text(v) for v in value)
    return ""


def run_content_item(agent, content_type: str, brief_context: dict, retriever: GDDRetriever,
                      query: str, critic: Critic, k: int = 3) -> dict:
    log(f"--- {content_type} ---")

    gen_chunks = retriever.search(query, k=k)
    log(f"generation query: {query!r}")
    for c in gen_chunks:
        log(f"  retrieved [{c['score']:.4f}] {c['id']}")

    gen_context = dict(brief_context)
    gen_context["retrieved_chunks"] = gen_chunks
    gen_result = agent.run(gen_context)
    log(f"generated ({gen_result.mode}): {json.dumps(gen_result.output)}")

    return {
        "content_type": content_type,
        "generation": {
            "query": query,
            "retrieved_chunks": [{"id": c["id"], "score": c["score"]} for c in gen_chunks],
            "output": gen_result.output,
            "mode": gen_result.mode,
        },
    }


def run_critic(item: dict, retriever: GDDRetriever, critic: Critic, k: int = 3) -> dict:
    content_type = item["content_type"]
    generated_output = item["generation"]["output"]
    generated_text = flatten_text(generated_output)

    critic_query = generated_text
    critic_chunks = retriever.search(critic_query, k=k)
    log(f"critic query (from generated text): {critic_query[:80]!r}...")
    for c in critic_chunks:
        log(f"  retrieved [{c['score']:.4f}] {c['id']}")

    critic_context = {
        "content_type": content_type,
        "generated_output": generated_output,
        "generated_text": generated_text,
        "retrieved_chunks": critic_chunks,
    }
    critic_result = critic.run(critic_context)
    verdict = critic_result.output["verdict"]
    if verdict == "PASS":
        log("critic -> PASS")
    else:
        log(f"critic -> FAIL ({len(critic_result.output['issues'])} issue(s)):")
        for issue in critic_result.output["issues"]:
            log(f"    - [{issue['type']}] found {issue['found']!r}: {issue['explanation']}")

    item["critique"] = {
        "query": critic_query,
        "retrieved_chunks": [{"id": c["id"], "score": c["score"]} for c in critic_chunks],
        "output": critic_result.output,
        "mode": critic_result.mode,
    }
    return item


def run_pipeline(inject_break: bool = False) -> dict:
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    llm = LLMClient()
    log(f"LLM mode: {'LIVE (ANTHROPIC_API_KEY found)' if llm.live else 'SIMULATE (no API key -- deterministic fallback)'}")

    retriever = GDDRetriever()
    log(f"Retriever loaded {len(retriever.chunks)} GDD chunks: {[c['id'] for c in retriever.chunks]}")

    bestiary_flavor = BestiaryFlavor(llm)
    spore_flavor = SporeFlavor(llm)
    warren_dialogue = WarrenDialogue(llm)
    critic = Critic(llm)

    items = []

    enemy = load_existing_enemy()
    items.append(run_content_item(
        bestiary_flavor, "bestiary_flavor", {"enemy": enemy}, retriever,
        query=(
            "Blight rotting corrupted twisting root-caverns creatures Eldercap "
            "corrupted warden beetle Gatekeeper tone dark underneath cozy"
        ),
        critic=critic,
    ))

    spore_brief = {"category": "Ring", "intent": "punishes reckless dashing near hazards"}
    items.append(run_content_item(
        spore_flavor, "spore_flavor", {"brief": spore_brief}, retriever,
        query=(
            "new spore Ring category triggered effect on-dodge on-kill on-hurt "
            "rarity mythic blighted curse naming Cap Gill Ring"
        ),
        critic=critic,
    ))

    dialogue_brief = {"npc": "Snail", "trigger": "after depositing Bloom for the first time"}
    items.append(run_content_item(
        warren_dialogue, "warren_dialogue", {"brief": dialogue_brief}, retriever,
        query=(
            "Snail shop Warren hub NPC dialogue between-run cozy warm rescued "
            "critters Gold Bloom currency storytelling drip-feed"
        ),
        critic=critic,
    ))

    if inject_break:
        log("!! --inject-break: corrupting the Warren dialogue draft with generic-fantasy "
            "tone drift + a wrong currency name, to prove the Critic actually catches and "
            "corrects a real break instead of just asserting it can")
        broken_line = (
            "Ah, chosen one -- the ancient prophecy foretold your coming. Spend your "
            "coins of legend wisely, Sir Morel."
        )
        items[2]["generation"]["output"]["lines"].append(broken_line)

    items = [run_critic(item, retriever, critic) for item in items]

    result = {"items": items}
    with open(OUTPUT_PATH, "w") as f:
        json.dump(result, f, indent=2)
    log(f"Wrote {OUTPUT_PATH}")

    # !! Added for Assignment #10's cost-analysis deliverable -- real, provider-
    # reported usage from this actual run, not an estimate.
    if llm.live:
        cost = llm.cost_summary()
        result["real_cost_analysis"] = cost
        log(f"REAL COST (Sonnet 4.6, this run): {cost['call_count']} calls, "
            f"{cost['total_input_tokens']} in / {cost['total_output_tokens']} out tokens, "
            f"${cost['total_cost_usd']}")
        with open(OUTPUT_PATH, "w") as f:
            json.dump(result, f, indent=2)

    return result


if __name__ == "__main__":
    inject = "--inject-break" in sys.argv
    run_pipeline(inject_break=inject)
