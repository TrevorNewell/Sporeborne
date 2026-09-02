from .base import Agent


class WarrenDialogue(Agent):
    """
    Assignment #4 content agent -- writes short hub-NPC dialogue for the
    Warren, grounded in the GDD's world/tone chunks.

    Named gap: GDD §4 names "Hades-style drip-feed" evolving hub-NPC
    dialogue as core to the storytelling pillar (Snail, Beetle each get
    between-run lines), but none has been authored anywhere in this repo.
    This is a scoped slice of the full Loremaster role (§8), which also
    owns spore-etching lore; this agent covers hub dialogue only.
    """
    name = "warren_dialogue"

    def build_prompt(self, context: dict):
        brief = context["brief"]
        chunks = context["retrieved_chunks"]
        grounding = "\n\n".join(f"[{c['id']}]\n{c['text']}" for c in chunks)
        system = (
            "You are Loremaster's dialogue-writing half for Sporeborne. Write "
            "2-3 short lines of between-run hub dialogue for the given NPC and "
            "trigger, grounded ONLY in the GDD excerpts provided -- correct "
            "currency names, correct hero title, correct tone (Hades-style "
            "drip-feed, cozy above / deadly below, no cutscenes, no generic "
            "fantasy framing like prophecies or chosen ones). Output ONLY "
            'valid JSON: {"npc": str, "trigger": str, "lines": [str, ...]}.'
        )
        user = (
            f"NPC: {brief['npc']}\n"
            f"Trigger: {brief['trigger']}\n\n"
            f"GDD excerpts:\n{grounding}"
        )
        return system, user

    def simulate(self, context: dict) -> dict:
        brief = context["brief"]
        return {
            "npc": brief["npc"],
            "trigger": brief["trigger"],
            "lines": [
                "First Bloom you've brought back, and already the Archive shelf "
                "looks less empty. Beetle's going to want to talk your ear off "
                "about it.",
                "Gold spends down here. Bloom's the only coin that remembers you "
                "came back at all.",
                "Don't thank me for the shop. Thank whatever's still growing "
                "under all that rot -- I just sell what it gives up.",
            ],
        }
