import copy
import json
import re

from .base import Agent


# Phrase -> (issue_type, grounded replacement, why it's wrong for Sporeborne).
# Replacements are chosen to keep the surrounding sentence grammatical (not
# blanked to "") so the corrected_output reads as an actual line, not a
# word-swap with gaps left in it -- e.g. "foretold your coming" becomes
# "already knew you'd come", not "".
#
# Deliberately narrow and explicit rather than a general "sounds generic"
# heuristic: in simulate mode this has to be a check that actually runs
# offline with zero setup (same constraint every other agent in this crew
# is built under), so it trades breadth for being reliably correct on what
# it does check. Live mode (build_prompt) does the open-ended judgment call
# a real model is needed for.
_FLAGS = [
    (r"\bsir morel\b", "lore_break",
     "Morel, the Doorwarden",
     "GDD §3: her title is 'the Doorwarden' (granddaughter of the last "
     "Doorwarden), not a knighthood honorific -- 'Sir' isn't used anywhere "
     "in the source."),
    (r"\bcoins? of legend\b", "tone_drift",
     "Gold",
     "GDD §5: the game's only currencies are Gold (in-run) and Bloom "
     "(persistent) -- 'coins of legend' is generic-fantasy currency "
     "language that doesn't exist in Sporeborne's economy."),
    (r"\bchosen one\b", "tone_drift",
     "Doorwarden",
     "GDD §4: storytelling is Hades-style drip-feed, explicitly no "
     "chosen-one framing -- and Morel already has a real, specific title "
     "('Doorwarden') the game uses instead of a generic epithet."),
    (r"\bthe ancient prophec(?:y|ies)\b", "tone_drift",
     "the old trail",
     "GDD §4: there is no prophecy in Sporeborne's story -- grandmother "
     "left an actual trail (one spore-etching found per run), which is "
     "the game's real mechanism for 'how the story knows where you are.'"),
    (r"\bforetold your coming\b", "tone_drift",
     "already knew you'd come",
     "GDD §4: nothing in the GDD foretells the player -- the trail is "
     "something grandmother left behind, not a prophecy about the future."),
    (r"\bevil sorcerer\b|\bdark lord\b",
     "tone_drift", "the Blight",
     "GDD §4: the antagonist force is 'the Blight,' a rot/corruption, not "
     "a sorcerer or dark-lord villain archetype."),
]


class Critic(Agent):
    """
    Assignment #4's Critic Agent -- does NOT exist anywhere in the GDD's
    own 9-agent taxonomy (§8). Loremaster authors lore; Data Validator
    enforces the human-owned rule-set (validation/rules_rootways.json) but
    is explicitly schema/numeric, not content-aware. Neither catches a
    lore contradiction or a tone drift against the GDD -- this agent is
    genuinely new scope, not a relabeling of an existing role.

    Shared across all three Assignment #4 content types (bestiary flavor,
    spore flavor, Warren dialogue) rather than one critic per type -- see
    CLAUDE.md's "Decision 1" writeup. Takes `content_type` as a parameter
    so its prompt/checks can be type-aware without needing three separate
    agent classes.

    Runs its own retrieval pass (content_pipeline.py queries the GDD using
    the generated text itself, not the generation step's original query),
    so it can catch a contradiction that lives in a different GDD section
    than whatever the generator retrieved -- reusing the generator's exact
    chunks would let the critic only ever check output against the same
    narrow evidence that produced it.
    """
    name = "critic"

    def build_prompt(self, context: dict):
        content_type = context["content_type"]
        generated_output = context["generated_output"]
        chunks = context["retrieved_chunks"]
        grounding = "\n\n".join(f"[{c['id']}]\n{c['text']}" for c in chunks)
        system = (
            "You are the Critic Agent for Sporeborne's content pipeline. Given "
            f"a piece of generated {content_type} content (as JSON) and GDD "
            "excerpts retrieved against it, check for two things: (1) lore "
            "breaks -- facts that contradict the GDD excerpts, and (2) tone "
            "drift -- generic fantasy language that doesn't match Sporeborne's "
            "established voice (cozy above/deadly below, dry, specific, no "
            "prophecies or chosen-one framing). If you find either, produce a "
            "corrected version of the JSON with the SAME keys and structure as "
            "the input -- only the flagged text changed, everything else left "
            "as-is -- and explain what you changed and why, citing the GDD "
            "excerpt that grounds the correction. Keep each issue's explanation "
            "to ONE sentence, max ~25 words -- name the contradiction and the "
            "GDD section, don't restate the full excerpt or narrate at length. "
            "Output ONLY valid JSON: "
            '{"verdict": "PASS"|"FAIL", "issues": [{"type": str, "found": str, '
            '"explanation": str}], "corrected_output": <object matching the '
            "input's structure>|null}."
        )
        user = (
            f"Generated {content_type} content:\n{json.dumps(generated_output, indent=2)}"
            f"\n\nGDD excerpts:\n{grounding}"
        )
        return system, user

    def simulate(self, context: dict) -> dict:
        content_type = context["content_type"]
        generated_output = context["generated_output"]
        generated_text = context["generated_text"]

        issues = []
        corrected_output = copy.deepcopy(generated_output)

        for pattern, issue_type, replacement, why in _FLAGS:
            matches = list(re.finditer(pattern, generated_text, flags=re.IGNORECASE))
            if not matches:
                continue
            found = matches[0].group(0)
            issues.append({"type": issue_type, "found": found, "explanation": why})
            corrected_output = _replace_in_strings(corrected_output, pattern, replacement)

        if issues:
            corrected_output = _clean_whitespace(corrected_output)

        if not issues:
            return {
                "content_type": content_type,
                "verdict": "PASS",
                "issues": [],
                "corrected_output": None,
            }

        return {
            "content_type": content_type,
            "verdict": "FAIL",
            "issues": issues,
            "corrected_output": corrected_output,
        }


def _replace_in_strings(value, pattern, replacement):
    """Recursively applies a regex replace to every string in a dict/list/str."""
    if isinstance(value, str):
        return re.sub(pattern, replacement, value, flags=re.IGNORECASE)
    if isinstance(value, dict):
        return {k: _replace_in_strings(v, pattern, replacement) for k, v in value.items()}
    if isinstance(value, list):
        return [_replace_in_strings(v, pattern, replacement) for v in value]
    return value


def _clean_whitespace(value):
    """
    Collapses double-spaces and stray leading punctuation that a removed
    phrase can leave behind (e.g. a blanked word leaving "Ah,  -- the").
    Runs once, after all _FLAGS substitutions, only on strings that were
    actually touched -- so a normal sentence with no corrections is never
    re-formatted.
    """
    if isinstance(value, str):
        cleaned = re.sub(r"\s+", " ", value)
        cleaned = re.sub(r"\s+([,.!?])", r"\1", cleaned)
        return cleaned.strip()
    if isinstance(value, dict):
        return {k: _clean_whitespace(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_clean_whitespace(v) for v in value]
    return value
