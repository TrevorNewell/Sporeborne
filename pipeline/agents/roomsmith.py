import random
from .base import Agent


class Roomsmith(Agent):
    """
    Authors one room-template layout + spawn table for a zone.
    First agent in the crew -- input comes only from the human-owned zone
    theme, not from any other agent.
    """
    name = "roomsmith"

    def build_prompt(self, context: dict):
        zone = context["zone_theme"]
        system = (
            "You are Roomsmith, a room-template designer for the 2D roguelike "
            "Sporeborne. You output ONLY valid JSON, no prose, matching this schema: "
            '{"room_id": str, "zone": str, "type": str, "depth_band": int, '
            '"layout_summary": str, "hazards": [str], '
            '"spawn_table": [{"enemy_slot": str, "weight": float, "count_range": [int,int]}], '
            '"notes_for_bestiary": str}. '
            "hazards MUST only use tags from the provided hazard_vocabulary."
        )
        user = (
            f"Zone theme: {zone['theme']}\n"
            f"Hazard vocabulary: {zone['hazard_vocabulary']}\n"
            f"Room type requested: {zone['room_type_requested']}\n"
            f"Depth band: {zone['depth_band']}\n"
            "Author one combat room template."
        )
        return system, user

    def simulate(self, context: dict) -> dict:
        zone = context["zone_theme"]
        random.seed(zone["depth_band"])
        hazards = random.sample(zone["hazard_vocabulary"], k=2)
        return {
            "room_id": f"{zone['zone']}_combat_{zone['depth_band']:02d}",
            "zone": zone["zone"],
            "type": zone["room_type_requested"],
            "depth_band": zone["depth_band"],
            "layout_summary": (
                "A long root-choked corridor opening into a sunken chamber; "
                "a collapsed bridge forces a drop into the lower tier, where "
                f"{hazards[0]} lines the far wall and {hazards[1]} pools near center."
            ),
            "hazards": hazards,
            "spawn_table": [
                {"enemy_slot": "primary", "weight": 0.6, "count_range": [2, 3]},
                {"enemy_slot": "secondary", "weight": 0.4, "count_range": [1, 2]},
            ],
            "notes_for_bestiary": (
                f"Arena favors ranged harassment near the {hazards[1]} and a melee "
                f"presence guarding the {hazards[0]} choke point."
            ),
        }
