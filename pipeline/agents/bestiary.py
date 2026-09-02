from .base import Agent


class Bestiary(Agent):
    """
    Writes enemy rows that fit the room Roomsmith just produced.
    Runs after Roomsmith -- its entire brief comes from Roomsmith's
    `hazards` and `notes_for_bestiary` fields, not from the zone theme
    directly.
    """
    name = "bestiary"

    def build_prompt(self, context: dict):
        room = context["room"]
        band = context["difficulty_band"]
        system = (
            "You are Bestiary, an enemy designer for Sporeborne. You output ONLY "
            "valid JSON matching this schema: "
            '{"zone": str, "room_id": str, "enemies": [2 enemy objects, each: '
            '{"enemy_id": str, "role": "primary"|"secondary", "hp": int, "damage": int, '
            '"attack_pattern": {"type": str, "telegraph_seconds": float, "description": str}, '
            '"spawn_weight": float, "fits_hazard_tags": [str]}]}. '
            "zone and room_id MUST echo the room given below exactly. "
            f"telegraph_seconds MUST be >= {band['telegraph_seconds_floor']}. "
            "fits_hazard_tags MUST intersect the room's hazards."
        )
        user = (
            f"Zone: {room['zone']}\n"
            f"Room: {room['room_id']}\n"
            f"Hazards: {room['hazards']}\n"
            f"Bestiary brief: {room['notes_for_bestiary']}\n"
            f"Spawn table slots needed: {[s['enemy_slot'] for s in room['spawn_table']]}"
        )
        return system, user

    def simulate(self, context: dict) -> dict:
        room = context["room"]
        band = context["difficulty_band"]
        depth = room["depth_band"]
        hp_mult = (1 + band["enemy_hp_growth_per_room"]) ** depth
        dmg_mult = (1 + band["enemy_damage_growth_per_room"]) ** depth
        enemies = [
            {
                "enemy_id": f"{room['zone']}_root_lasher_{depth:02d}",
                "role": "primary",
                "hp": round(28 * hp_mult),
                "damage": round(6 * dmg_mult),
                "attack_pattern": {
                    "type": "arc",
                    "telegraph_seconds": max(0.4, band["telegraph_seconds_floor"]),
                    "description": "slow root-whip arc, readable wind-up before the swing",
                },
                "spawn_weight": 0.6,
                "fits_hazard_tags": [room["hazards"][0]],
            },
            {
                "enemy_id": f"{room['zone']}_spore_gnat_{depth:02d}",
                "role": "secondary",
                "hp": round(14 * hp_mult),
                "damage": round(4 * dmg_mult),
                "attack_pattern": {
                    "type": "aimed_volley",
                    "telegraph_seconds": max(0.45, band["telegraph_seconds_floor"]),
                    "description": "hovers near the hazard pool, fires a single slow aimed spore",
                },
                "spawn_weight": 0.4,
                "fits_hazard_tags": [room["hazards"][1]],
            },
        ]
        return {"zone": room["zone"], "room_id": room["room_id"], "enemies": enemies}
