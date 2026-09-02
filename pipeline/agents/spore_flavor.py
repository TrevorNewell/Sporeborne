from .base import Agent


class SporeFlavor(Agent):
    """
    Assignment #4 content agent -- writes one new spore (mechanical effect +
    flavor text), grounded in the GDD's spore system rules and existing
    example spores.

    Named gap: no spore content exists anywhere in this repo -- no data
    file, no agent output -- despite the GDD (§7) committing 15 spores
    (5/category) to the shippable MVP. This is the largest content debt of
    the three Assignment #4 targets. The full Sporewright role (§8) also
    balances numeric stacking against the existing pool; this agent is
    scoped to flavor + a plausible mechanical effect only, not full balance
    authoring.
    """
    name = "spore_flavor"

    def build_prompt(self, context: dict):
        brief = context["brief"]
        chunks = context["retrieved_chunks"]
        grounding = "\n\n".join(f"[{c['id']}]\n{c['text']}" for c in chunks)
        system = (
            "You are Sporewright's flavor-writing half for Sporeborne. Given a "
            "spore category and a mechanical intent, invent ONE new spore that "
            "fits the naming convention, category rules, and tone shown in the "
            "GDD excerpts provided. Output ONLY valid JSON: "
            '{"spore_id": str, "name": str, "category": "Cap"|"Gill"|"Ring", '
            '"rarity": "Common"|"Rare"|"Mythic", "mechanical_effect": str, '
            '"flavor_text": str}.'
        )
        user = (
            f"Category: {brief['category']}\n"
            f"Mechanical intent: {brief['intent']}\n\n"
            f"GDD excerpts:\n{grounding}"
        )
        return system, user

    def simulate(self, context: dict) -> dict:
        brief = context["brief"]
        category = brief["category"]

        return {
            "spore_id": "rootbound_ring",
            "name": "Rootbound Ring",
            "category": category,
            "rarity": "Rare",
            "mechanical_effect": (
                "On dodge, roots erupt beneath the nearest enemy within melee "
                "range, snaring them in place for 1.2s (does not stack with "
                "itself; refreshes duration on trigger)."
            ),
            "flavor_text": (
                "The Rootways remember every knight who ever walked them, and "
                "they aren't always in a hurry to let go of the next one."
            ),
        }
