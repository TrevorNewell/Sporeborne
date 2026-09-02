from .base import Agent


class SporeMechanics(Agent):
    """
    Assignment #6 GER pipeline -- Generator/Refiner for spore mechanical rows
    (spore_id, category, rarity, mechanical_effect, curse, flavor_text).

    Named gap: Assignment #4's SporeFlavor writes flavor text for one spore
    but has no "curse" field at all, and no mechanical-row generator exists
    anywhere in the repo despite validation/rules_rootways.json already
    defining a "mythic_curse" rule (rarity == Mythic requires a non-null
    curse, per GDD §2's Blighted-spore rule) that agents/data_validator.py
    never actually implements. This agent is the Generator half of the GER
    loop that closes that gap; ger_pipeline.py's evaluate_spore() is the
    Evaluator that finally enforces the rule.

    build_prompt/simulate are the initial-generation pair (same live/simulate
    contract as every other agent). build_refine_prompt/refine_simulate are a
    second pair used only by the Refiner step in ger_pipeline.py -- not part
    of the base Agent.run() contract, since refinement needs the prior draft
    and the evaluator's failure list as extra context, not just a brief.
    """
    name = "spore_mechanics"

    _CURSE_BY_CATEGORY = {
        "Cap": "triple effect magnitude, but healing is halved",
        "Gill": "the passive bonus doubles, but max HP is permanently reduced by 20%",
        "Ring": "the trigger fires on every dodge instead of every third, but each "
                "activation costs 10% of current HP",
    }

    def build_prompt(self, context: dict):
        brief = context["brief"]
        chunks = context["retrieved_chunks"]
        grounding = "\n\n".join(f"[{c['id']}]\n{c['text']}" for c in chunks)
        system = (
            "You are Sporewright, Sporeborne's spore-mechanics author. Sporeborne's "
            "spore system (GDD §2): three categories -- Cap (weapon mutation), Gill "
            "(passive stat/rule change), Ring (triggered on-dodge/on-kill/on-hurt "
            "effect) -- and three rarities -- Common, Rare, Mythic. Mythic spores are "
            "'Blighted': they trade Mythic-tier power for a real downside curse (e.g. "
            "Hollow Cap: triple damage, but healing is halved). Common and Rare spores "
            "must NOT carry a curse -- only Mythic spores do. Given a category, "
            "rarity, and mechanical intent, invent ONE new spore matching the naming "
            "convention and tone in the GDD excerpts provided. Output ONLY valid "
            'JSON: {"spore_id": str, "name": str, "category": "Cap"|"Gill"|"Ring", '
            '"rarity": "Common"|"Rare"|"Mythic", "mechanical_effect": str, '
            '"curse": str or null, "flavor_text": str}. curse MUST be null unless '
            'rarity is "Mythic", in which case curse MUST be a real, concrete '
            "drawback, not a vague one."
        )
        user = (
            f"Category: {brief['category']}\n"
            f"Rarity: {brief['rarity']}\n"
            f"Mechanical intent: {brief['intent']}\n\n"
            f"GDD excerpts:\n{grounding}"
        )
        return system, user

    def simulate(self, context: dict) -> dict:
        brief = context["brief"]
        category = brief["category"]
        rarity = brief["rarity"]
        hint = brief.get("spore_id_hint", "new_spore")
        curse = self._CURSE_BY_CATEGORY[category] if rarity == "Mythic" else None
        return {
            "spore_id": hint,
            "name": hint.replace("_", " ").title(),
            "category": category,
            "rarity": rarity,
            "mechanical_effect": f"({category} intent: {brief['intent']})",
            "curse": curse,
            "flavor_text": (
                "The Rootways remember every knight who ever walked them, and "
                "they aren't always in a hurry to let go of the next one."
            ),
        }

    def build_refine_prompt(self, context: dict):
        draft = context["draft"]
        failures = context["failures"]
        import json as _json
        system = (
            "You are Sporewright, refining a spore draft that failed evaluator "
            "checks against Sporeborne's GDD §2 spore rules (Common/Rare/Mythic "
            "rarity; only Mythic/'Blighted' spores carry a curse). Fix ONLY the "
            "listed failures -- keep every other field exactly as given. Output the "
            'corrected spore as the same JSON object: {"spore_id", "name", '
            '"category", "rarity", "mechanical_effect", "curse", "flavor_text"}.'
        )
        user = (
            f"Draft:\n{_json.dumps(draft)}\n\n"
            "Evaluator failures:\n" + "\n".join(f"- [{f['rule']}] {f['reason']}" for f in failures)
        )
        return system, user

    def refine_simulate(self, context: dict) -> dict:
        draft = dict(context["draft"])
        for f in context["failures"]:
            rule = f["rule"]
            if rule == "mythic_curse":
                if draft.get("rarity") == "Mythic" and not draft.get("curse"):
                    draft["curse"] = self._CURSE_BY_CATEGORY.get(draft.get("category"), "a real downside")
                elif draft.get("rarity") in ("Common", "Rare") and draft.get("curse"):
                    draft["curse"] = None
            elif rule == "no_duplicate_ids":
                draft["spore_id"] = f"{draft.get('spore_id', 'spore')}_v2"
            elif rule == "schema_valid":
                if draft.get("category") not in ("Cap", "Gill", "Ring"):
                    draft["category"] = "Cap"
                if draft.get("rarity") not in ("Common", "Rare", "Mythic"):
                    draft["rarity"] = "Common"
        return draft
