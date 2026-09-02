from .base import Agent


class BestiaryFlavor(Agent):
    """
    Assignment #4 content agent -- writes a narrative flavor description for
    an enemy the (Assignment #3) Bestiary agent already produced mechanically.

    Named gap: agents/bestiary.py outputs only hp/damage/attack_pattern rows.
    Nothing in the crew has ever given an enemy a lore identity -- what it
    IS within the Blight, not just what it does in a fight. This agent fills
    that gap, grounded in GDD chunks retrieved by content_pipeline.py (not
    the seed JSON in design/), per Assignment #4.
    """
    name = "bestiary_flavor"

    def build_prompt(self, context: dict):
        enemy = context["enemy"]
        chunks = context["retrieved_chunks"]
        grounding = "\n\n".join(f"[{c['id']}]\n{c['text']}" for c in chunks)
        system = (
            "You are writing a short (2-3 sentence) lore/flavor description for a "
            "Sporeborne enemy, grounded ONLY in the GDD excerpts provided -- do not "
            "invent world facts that aren't in them. Match the game's established "
            "tone (cozy above, deadly below; dry, specific, never generic fantasy "
            "cliche). Output ONLY valid JSON: "
            '{"enemy_id": str, "lore_description": str}.'
        )
        user = (
            f"Enemy: {enemy['enemy_id']} ({enemy['role']})\n"
            f"Attack: {enemy['attack_pattern']['type']} -- "
            f"{enemy['attack_pattern']['description']}\n"
            f"Fits hazard tags: {enemy['fits_hazard_tags']}\n\n"
            f"GDD excerpts:\n{grounding}"
        )
        return system, user

    def simulate(self, context: dict) -> dict:
        enemy = context["enemy"]
        hazard = enemy["fits_hazard_tags"][0]
        attack_desc = enemy["attack_pattern"]["description"]

        hazard_phrasing = {
            "root_snare": "roots that still remember which way the old Doorwardens walked",
            "collapsing_platform": "stone the Blight has been quietly hollowing out for years",
            "rot_pool": "rot pooling where clean water used to run",
            "spore_vent": "vents coughing spore long after anything living should still be feeding it",
        }.get(hazard, f"the {hazard.replace('_', ' ')} nearby")

        lore_description = (
            f"Something the Eldercap's own roots used to be, before the Blight got "
            f"into them. It doesn't hunt so much as wait near {hazard_phrasing}, "
            f"and its {attack_desc} -- the corruption slowed it down as much as it "
            f"twisted it. Cozy above, deadly below; this is what deadly-below "
            f"actually looks like once you're close enough to see it."
        )

        return {"enemy_id": enemy["enemy_id"], "lore_description": lore_description}
