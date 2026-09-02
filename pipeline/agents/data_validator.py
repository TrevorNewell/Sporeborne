from .base import Agent, AgentResult


class DataValidator(Agent):
    """
    Checks every other agent's output against the human-owned rule-set.
    Runs last -- reads Roomsmith's, Bestiary's, and Curvewright's output
    together, since several rules (enemy_fits_room, curve_tolerance) only
    make sense checked across agents.

    This agent is deliberately NOT model-backed: it enforces the rule-set
    file exactly, with no room for a model to "interpret" a rule leniently.
    That's the same fail-closed design the GDD specifies for this role.
    """
    name = "data_validator"

    def run(self, context: dict) -> AgentResult:
        try:
            output = self._validate(context)
            return AgentResult(agent=self.name, ok=True, output=output, mode="deterministic")
        except Exception as e:
            return AgentResult(agent=self.name, ok=False, error=str(e), mode="deterministic")

    def build_prompt(self, context):  # not used -- rule-based, not model-backed
        raise NotImplementedError

    def simulate(self, context):  # not used -- rule-based, not model-backed
        raise NotImplementedError

    def _validate(self, context: dict) -> dict:
        room = context["room"]
        enemies = context["enemies"]["enemies"]
        curve = context["curve"]
        band = context["difficulty_band"]
        zone_theme = context["zone_theme"]
        rules = context["rules"]["rules"]

        failures = []
        passes = []

        rule_ids = {r["id"] for r in rules}

        # hazard_vocab
        if "hazard_vocab" in rule_ids:
            bad = [h for h in room["hazards"] if h not in zone_theme["hazard_vocabulary"]]
            if bad:
                failures.append({"rule": "hazard_vocab", "item": room["room_id"],
                                  "reason": f"hazards not in vocabulary: {bad}", "origin": "roomsmith"})
            else:
                passes.append({"rule": "hazard_vocab", "item": room["room_id"]})

        # telegraph_floor + enemy_fits_room
        for e in enemies:
            if "telegraph_floor" in rule_ids:
                t = e["attack_pattern"]["telegraph_seconds"]
                if t < band["telegraph_seconds_floor"]:
                    failures.append({"rule": "telegraph_floor", "item": e["enemy_id"],
                                      "reason": f"telegraph {t}s < floor {band['telegraph_seconds_floor']}s",
                                      "origin": "bestiary"})
                else:
                    passes.append({"rule": "telegraph_floor", "item": e["enemy_id"]})

            if "enemy_fits_room" in rule_ids:
                if not set(e["fits_hazard_tags"]) & set(room["hazards"]):
                    failures.append({"rule": "enemy_fits_room", "item": e["enemy_id"],
                                      "reason": "fits_hazard_tags does not intersect room hazards",
                                      "origin": "bestiary"})
                else:
                    passes.append({"rule": "enemy_fits_room", "item": e["enemy_id"]})

        # curve_tolerance
        if "curve_tolerance" in rule_ids:
            proj = curve["projected_boss_door_dps_multiple"]
            lo, hi = band["target_boss_door_dps_multiple_min"], band["target_boss_door_dps_multiple_max"]
            if not (lo <= proj <= hi):
                failures.append({"rule": "curve_tolerance", "item": room["room_id"],
                                  "reason": f"projected multiple {proj} outside [{lo}, {hi}]",
                                  "origin": "curvewright"})
            else:
                passes.append({"rule": "curve_tolerance", "item": room["room_id"]})

        # no_duplicate_ids
        if "no_duplicate_ids" in rule_ids:
            ids = [room["room_id"]] + [e["enemy_id"] for e in enemies]
            dupes = {i for i in ids if ids.count(i) > 1}
            if dupes:
                failures.append({"rule": "no_duplicate_ids", "item": list(dupes),
                                  "reason": "duplicate ids in package", "origin": "multiple"})
            else:
                passes.append({"rule": "no_duplicate_ids", "item": room["room_id"]})

        return {
            "zone": room["zone"],
            "room_id": room["room_id"],
            "status": "PASS" if not failures else "FAIL",
            "passes": passes,
            "failures": failures,
        }
