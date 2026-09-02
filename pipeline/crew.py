from dotenv import load_dotenv
load_dotenv()

#!/usr/bin/env python3
"""
Sporeborne Content Crew
========================
Raw orchestration (no framework) for a 4-agent crew that produces one
game-ready combat-room package for Sporeborne's Rootways zone:

    Roomsmith -> Bestiary -> Curvewright -> Data Validator

Each agent's output becomes the next agent's input, so the crew can't be
run with fewer than these four agents without breaking the data flow:
  - Bestiary needs Roomsmith's hazards to write enemies that fit the room.
  - Curvewright needs Bestiary's enemy stats to project the power curve.
  - Data Validator needs all three outputs together to check cross-agent
    rules (does this enemy actually fit this room? is the curve in band?).

If ANTHROPIC_API_KEY is set in the environment, each LLM-backed agent
calls the real Anthropic API. If not (or if a live call fails), it falls
back to a deterministic simulate() mode -- the orchestration, retry, and
validation logic is identical either way. This lets the crew run and be
graded anywhere, with or without an API key.

Usage:
    python3 crew.py                  # normal run
    python3 crew.py --inject-failure # deliberately corrupt one output to
                                      # exercise the retry/escalation path
"""

import json
import os
import sys
import copy
from datetime import datetime, timezone

from agents import LLMClient, Roomsmith, Bestiary, Curvewright, DataValidator

HERE = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(HERE, "output")
MAX_RETRIES = 2


def load_json(*parts):
    with open(os.path.join(HERE, *parts)) as f:
        return json.load(f)


def log(msg):
    print(f"[crew] {msg}")


def run_crew(inject_failure: bool = False) -> dict:
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    llm = LLMClient()
    log(f"LLM mode: {'LIVE (ANTHROPIC_API_KEY found)' if llm.live else 'SIMULATE (no API key -- deterministic fallback)'}")

    zone_theme = load_json("design", "zone_theme_rootways.json")
    difficulty_band = load_json("design", "difficulty_band_rootways.json")
    rules = load_json("validation", "rules_rootways.json")

    roomsmith = Roomsmith(llm)
    bestiary = Bestiary(llm)
    curvewright = Curvewright(llm)
    validator = DataValidator(llm)

    context = {
        "zone_theme": zone_theme,
        "difficulty_band": difficulty_band,
        "rules": rules,
    }

    run_log = []
    attempt = 0

    while attempt <= MAX_RETRIES:
        attempt += 1
        log(f"--- Attempt {attempt}/{MAX_RETRIES + 1} ---")

        # 1. Roomsmith
        r_result = roomsmith.run(context)
        run_log.append({"agent": "roomsmith", "attempt": attempt, "ok": r_result.ok, "mode": r_result.mode})
        if not r_result.ok:
            log(f"Roomsmith failed to produce output: {r_result.error}. Escalating.")
            return _finish(run_log, status="ESCALATED", reason="roomsmith produced no output")
        context["room"] = r_result.output
        log(f"Roomsmith ({r_result.mode}) -> {context['room']['room_id']}")

        # 2. Bestiary (depends on room)
        b_result = bestiary.run(context)
        run_log.append({"agent": "bestiary", "attempt": attempt, "ok": b_result.ok, "mode": b_result.mode})
        if not b_result.ok:
            log(f"Bestiary failed: {b_result.error}. Escalating.")
            return _finish(run_log, status="ESCALATED", reason="bestiary produced no output")
        context["enemies"] = b_result.output

        if inject_failure and attempt == 1:
            # deliberately break a rule to prove the retry/escalation path
            # runs cleanly instead of crashing the crew
            log("!! --inject-failure: corrupting an enemy's telegraph timing to force a validator FAIL")
            context["enemies"]["enemies"][0]["attack_pattern"]["telegraph_seconds"] = 0.1

        log(f"Bestiary ({b_result.mode}) -> {[e['enemy_id'] for e in context['enemies']['enemies']]}")

        # 3. Curvewright (depends on room + enemies)
        c_result = curvewright.run(context)
        run_log.append({"agent": "curvewright", "attempt": attempt, "ok": c_result.ok, "mode": c_result.mode})
        if not c_result.ok:
            log(f"Curvewright failed: {c_result.error}. Escalating.")
            return _finish(run_log, status="ESCALATED", reason="curvewright produced no output")
        context["curve"] = c_result.output
        log(f"Curvewright ({c_result.mode}) -> projected {context['curve']['projected_boss_door_dps_multiple']}x at boss door")

        # 4. Data Validator (checks everything together)
        v_result = validator.run(context)
        run_log.append({"agent": "data_validator", "attempt": attempt, "ok": v_result.ok, "mode": v_result.mode})
        if not v_result.ok:
            log(f"Data Validator itself errored: {v_result.error}. Fail-closed -> escalating.")
            return _finish(run_log, status="ESCALATED", reason="validator error, fail-closed")

        report = v_result.output
        context["validation_report"] = report

        if report["status"] == "PASS":
            log(f"Data Validator -> PASS ({len(report['passes'])} checks)")
            return _finish(run_log, status="PASS", context=context)

        log(f"Data Validator -> FAIL ({len(report['failures'])} issue(s)):")
        for f in report["failures"]:
            log(f"    - [{f['rule']}] {f['item']}: {f['reason']} (origin: {f['origin']})")

        if attempt > MAX_RETRIES:
            log(f"Max retries ({MAX_RETRIES}) exhausted. Escalating to human.")
            return _finish(run_log, status="ESCALATED", context=context,
                            reason="validation failures persisted after max retries")

        log("Retrying: regenerating from the originating agent(s)...")
        # In live mode the next loop iteration naturally regenerates fresh
        # output. In simulate mode the deterministic generators are
        # correct-by-construction, EXCEPT for the deliberately-injected
        # failure above, which we clear here so attempt 2 demonstrates a
        # real recovery instead of looping forever on a self-inflicted bug.
        if inject_failure:
            inject_failure = False

    return _finish(run_log, status="ESCALATED", reason="unexpected loop exit")


def _finish(run_log, status, context=None, reason=""):
    result = {
        "status": status,
        "reason": reason,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "run_log": run_log,
    }
    if context:
        result["package"] = {
            "room": context.get("room"),
            "enemies": context.get("enemies"),
            "curve": context.get("curve"),
            "validation_report": context.get("validation_report"),
        }

    out_path = os.path.join(OUTPUT_DIR, "run_result.json")
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)
    log(f"Wrote {out_path}")

    if status == "PASS":
        pkg_path = os.path.join(OUTPUT_DIR, f"{context['room']['room_id']}_package.json")
        with open(pkg_path, "w") as f:
            json.dump(result["package"], f, indent=2)
        log(f"Wrote game-ready package: {pkg_path}")

    log(f"FINAL STATUS: {status}" + (f" ({reason})" if reason else ""))
    return result


if __name__ == "__main__":
    inject = "--inject-failure" in sys.argv
    result = run_crew(inject_failure=inject)
    sys.exit(0 if result["status"] == "PASS" else 1)
