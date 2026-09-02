from .base import Agent


class Curvewright(Agent):
    """
    Sets/validates power-curve projections against the room + enemy content
    just produced. Runs after Bestiary -- it's the join point between the
    room/enemy branch and the human-owned difficulty target.
    """
    name = "curvewright"

    def build_prompt(self, context: dict):
        room = context["room"]
        enemies = context["enemies"]["enemies"]
        band = context["difficulty_band"]
        system = (
            "You are Curvewright, a difficulty-curve tuner for Sporeborne. You output "
            "ONLY valid JSON matching this schema: "
            '{"zone": str, "room_id": str, "projected_boss_door_dps_multiple": float, '
            '"flagged_outliers": [{"item_id": str, "issue": str}], "reasoning": str}. '
            f"Target range for projected_boss_door_dps_multiple is "
            f"[{band['target_boss_door_dps_multiple_min']}, {band['target_boss_door_dps_multiple_max']}]."
        )
        user = f"Room: {room}\nEnemies: {enemies}\nDifficulty band: {band}"
        return system, user

    def simulate(self, context: dict) -> dict:
        room = context["room"]
        enemies = context["enemies"]["enemies"]
        band = context["difficulty_band"]
        depth = room["depth_band"]
        # simple deterministic projection consistent with the target growth rate
        projected = round(1.0 * ((1 + band["target_player_power_growth_per_room"]) ** min(depth, 10)) / 2.2, 2)
        projected = max(band["target_boss_door_dps_multiple_min"],
                         min(band["target_boss_door_dps_multiple_max"], projected))

        outliers = []
        for e in enemies:
            if e["attack_pattern"]["telegraph_seconds"] < band["telegraph_seconds_floor"]:
                outliers.append({
                    "item_id": e["enemy_id"],
                    "issue": f"telegraph {e['attack_pattern']['telegraph_seconds']}s below floor "
                             f"{band['telegraph_seconds_floor']}s",
                })

        return {
            "zone": room["zone"],
            "room_id": room["room_id"],
            "projected_boss_door_dps_multiple": projected,
            "flagged_outliers": outliers,
            "reasoning": (
                f"Projected multiple {projected}x derived from target growth "
                f"{band['target_player_power_growth_per_room']*100:.0f}%/room at depth {depth}, "
                "clamped to the human-owned tolerance band."
            ),
        }
