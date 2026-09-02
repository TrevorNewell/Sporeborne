"""
Assignment #7 -- Style Guide Agent: Generator / Evaluator / Refiner.

The Evaluator and Refiner need a raw-text completion, not the JSON-only contract
`agents/llm_client.py`'s `LLMClient.complete_json()` provides (the assignment
requires the literal "SCORE: [X/10]" / "REASON: [...]" text format) -- they use
`LLMClient.complete_text()` for that.
"""

import re

from .base import Agent, AgentResult


class NaiveGenerator(Agent):
    """
    Deliberately NOT grounded in the GDD or Sporeborne's house style -- this
    represents a raw first-draft generator (e.g. a generic content tool) that
    doesn't know Sporeborne's rules, which is exactly why a Style Guide Agent is
    needed downstream. Each brief includes an explicit adversarial instruction
    (per the assignment's step 4) so a live call reliably produces one specific,
    identifiable violation class; simulate() hardcodes the same three known-bad
    drafts so the demo is reproducible with zero API cost.
    """
    name = "naive_generator"

    _SIMULATED_DRAFTS = {
        "tone": (
            "Oh WOW, welcome back, friend!!! You're the BEST customer ever!!! "
            "Come buy something shiny, it'll be SO much fun, I promise!!!"
        ),
        "vocabulary": (
            "Thanks for the Gold, adventurer! I'll add it to my shop's collection "
            "right here in my humble store."
        ),
        "formatting": (
            "*The old beetle sets down its tools and looks up slowly.* Ahh... you've "
            "returned, and not empty-handed either, I see. *It shuffles closer, "
            "antennae twitching with something like relief.* Let me tell you, when "
            "the Gatekeeper's roar echoes up through the Rootways, even here in the "
            "Warren we feel it in our shells. Your grandmother used to stand right "
            "where you're standing, you know. *It pauses, lost in memory for a long "
            "moment.* But that's a story for another day. Rest now. You've earned it, "
            "and there's always more work waiting below for those brave enough to "
            "seek it out."
        ),
    }

    def run(self, context: dict) -> AgentResult:
        """
        Overrides the base Agent.run() (rather than using build_prompt/simulate
        through complete_json()) because this Generator needs plain dialogue text
        back, not a JSON object -- same reasoning as StyleEvaluator/StyleRefiner.
        """
        brief = context["brief"]
        if self.llm.live:
            try:
                system, user = self._build_prompt(brief)
                text = self.llm.complete_text(system, user)
                return AgentResult(agent=self.name, ok=True, output={"text": text}, mode="live")
            except Exception as e:
                print(f"[{self.name}] live call failed ({e}); falling back to simulate.")
        try:
            text = self._SIMULATED_DRAFTS[brief["violation_class"]]
            return AgentResult(agent=self.name, ok=True, output={"text": text}, mode="simulate")
        except Exception as e:
            return AgentResult(agent=self.name, ok=False, error=str(e), mode="simulate")

    @staticmethod
    def _build_prompt(brief: dict):
        system = (
            "You are a dialogue writer for a generic fantasy game. Write a short line "
            "or two of NPC dialogue based on the brief below. Follow the brief's "
            "instructions exactly, including any tone/format instructions given. "
            "Output ONLY the dialogue text, nothing else."
        )
        user = f"NPC: {brief['npc']}\nSituation: {brief['trigger']}\nInstruction: {brief['instruction']}"
        return system, user


class StyleEvaluator(Agent):
    """
    Grades text 1-10 against style_guide_rootways.md, in the literal
    "SCORE: [X/10]" / "REASON: [...]" format the assignment requires. Overrides
    run() rather than using build_prompt/simulate through the base Agent contract
    (same pattern agents/data_validator.py already uses) because the live path
    needs raw text + regex parsing, not complete_json()'s JSON contract.

    simulate() is a real (if narrow) deterministic check against the three
    specific rules in the style guide -- exclamation/caps density for tone,
    Gold-vs-Bloom / Snail-vs-Beetle keyword pairing for vocabulary, word count +
    stage-direction/paragraph count for formatting -- not a stub that always
    passes or always fails.
    """
    name = "style_evaluator"

    def __init__(self, llm_client, style_guide_text: str):
        super().__init__(llm_client)
        self.style_guide_text = style_guide_text

    def run(self, context: dict) -> AgentResult:
        text = context["text"]
        if self.llm.live:
            try:
                return AgentResult(agent=self.name, ok=True, output=self._live_evaluate(text), mode="live")
            except Exception as e:
                print(f"[{self.name}] live call failed ({e}); falling back to simulate.")
        try:
            return AgentResult(agent=self.name, ok=True, output=self._simulate_evaluate(text), mode="simulate")
        except Exception as e:
            return AgentResult(agent=self.name, ok=False, error=str(e), mode="simulate")

    def _live_evaluate(self, text: str) -> dict:
        system = (
            "You are the Style Guide Evaluator for Sporeborne, a 2D roguelike. Grade "
            "the following text strictly against these three house-style rules:\n\n"
            f"{self.style_guide_text}\n\n"
            "Review the text. Grade it on a scale of 1-10 based on these three rules. "
            "Output your response strictly as:\nSCORE: [X/10]\nREASON: [your detailed "
            "explanation of exactly which rule(s) were violated and why -- or why it "
            "earns a 10 if it fully complies]"
        )
        user = f"Text to grade:\n{text}"
        raw = self.llm.complete_text(system, user)
        return self._parse(raw)

    @staticmethod
    def _parse(raw: str) -> dict:
        score_match = re.search(r"SCORE:\s*\[?\s*(\d+)", raw)
        reason_match = re.search(r"REASON:\s*\[?(.*)", raw, re.DOTALL)
        score = int(score_match.group(1)) if score_match else 0
        reason = reason_match.group(1).strip().rstrip("]") if reason_match else raw
        return {"score": score, "reason": reason, "raw": raw}

    @staticmethod
    def _simulate_evaluate(text: str) -> dict:
        violations = []
        score = 10

        bang_count = text.count("!")
        caps_words = re.findall(r"\b[A-Z]{3,}\b", text)
        if bang_count >= 3 or caps_words:
            violations.append(
                f"Tone: {bang_count} exclamation marks and shouty caps ({caps_words or 'none'}) "
                "read as generic cartoon-cheerful, with no 'cozy above, deadly below' contrast "
                "(GDD §1)."
            )
            score -= 4

        if re.search(r"\bBeetle\b", text) and re.search(r"\b(Gold|shop)\b", text) and not re.search(r"\b(Bloom|Archive)\b", text):
            violations.append(
                "Vocabulary: Beetle is speaking about Gold/'shop', but Beetle runs the "
                "Bloom-funded Spore Archive -- Gold and the shop belong to Snail (GDD §3)."
            )
            score -= 4
        if re.search(r"\bSnail\b", text) and re.search(r"\b(Bloom|Archive)\b", text) and not re.search(r"\b(Gold|shop)\b", text):
            violations.append(
                "Vocabulary: Snail is speaking about Bloom/the Archive, but Snail runs the "
                "in-run Gold shop -- Bloom and the Archive belong to Beetle (GDD §3)."
            )
            score -= 4

        word_count = len(text.split())
        has_stage_direction = "*" in text
        paragraph_count = len([p for p in text.split("\n\n") if p.strip()]) or 1
        if word_count > 40 or has_stage_direction or paragraph_count > 1:
            violations.append(
                f"Formatting: {word_count} words across {paragraph_count} paragraph(s)"
                f"{' with asterisk stage directions' if has_stage_direction else ''} -- Warren "
                "hub-NPC lines must stay short spoken barks, not monologues (GDD §8, Warren Voices)."
            )
            score -= 4

        if not violations:
            reason = (
                "No rule violations detected: tone matches the cozy-above/deadly-below "
                "contrast, vocabulary keeps Gold/Snail's-shop and Bloom/Beetle's-Archive "
                "separate, and formatting is a short single spoken bark."
            )
            score = 10
        else:
            reason = " ".join(violations)
            score = max(1, score)

        return {"score": score, "reason": reason, "raw": f"SCORE: [{score}/10]\nREASON: [{reason}]"}


class StyleRefiner(Agent):
    """
    Rewrites text to score 10/10, using the Evaluator's REASON as the fix
    instruction. Same run()-override pattern as StyleEvaluator, for the same
    raw-text reason.
    """
    name = "style_refiner"

    def __init__(self, llm_client, style_guide_text: str):
        super().__init__(llm_client)
        self.style_guide_text = style_guide_text

    _SIMULATED_FIXES = {
        "tone": (
            "Back again already? Good -- the Warren's warmer with you in it. Doesn't "
            "mean the Rootways got any kinder down there, though."
        ),
        "vocabulary": (
            "Thanks for the Bloom -- I'll log it in the Archive. Snail's the one to see "
            "if you're after Gold-side wares."
        ),
        "formatting": (
            "Made it back in one piece. The Rootways don't usually let go that easy."
        ),
    }

    def run(self, context: dict) -> AgentResult:
        original = context["original"]
        reason = context["reason"]
        if self.llm.live:
            try:
                fixed = self._live_refine(original, reason)
                return AgentResult(agent=self.name, ok=True, output={"text": fixed}, mode="live")
            except Exception as e:
                print(f"[{self.name}] live call failed ({e}); falling back to simulate.")
        try:
            fixed = self._SIMULATED_FIXES[context["violation_class"]]
            return AgentResult(agent=self.name, ok=True, output={"text": fixed}, mode="simulate")
        except Exception as e:
            return AgentResult(agent=self.name, ok=False, error=str(e), mode="simulate")

    def _live_refine(self, original: str, reason: str) -> str:
        system = (
            "You are the Style Guide Refiner for Sporeborne. Take the original text and "
            "the Evaluator's REASON, and rewrite the text so that it scores a perfect "
            "10/10 on the style guide below:\n\n"
            f"{self.style_guide_text}\n\n"
            "Fix exactly the violations named in the REASON -- keep the same NPC, "
            "situation, and intent, just bring it on-brand. The original is given as "
            "\"[NPC]: line\" so you know who's speaking; output ONLY the rewritten "
            "dialogue line itself, WITHOUT the \"[NPC]:\" prefix, nothing else -- no "
            "preamble, no explanation."
        )
        user = f"Original text:\n{original}\n\nEvaluator's REASON:\n{reason}"
        return self.llm.complete_text(system, user)
