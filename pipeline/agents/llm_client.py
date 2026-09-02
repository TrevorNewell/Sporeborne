"""
Thin wrapper around the Anthropic API used by every agent in the crew.

Why this exists: every agent needs the same "call a model, get text back,
handle failure" behavior, and the crew needs to be gradeable/runnable on a
machine that doesn't have an API key configured. So this client tries a real
call first and transparently falls back to each agent's own deterministic
`simulate()` method if no key is present or the call fails. Nothing about
the orchestration logic changes between the two modes -- only where the
content comes from.
"""

import os
import json


class LLMJSONError(Exception):
    """
    Raised when the model's response can't be parsed as JSON. Carries the raw
    text so a caller can log what actually came back instead of just "invalid
    JSON" -- required by the "never let malformed LLM output reach the engine"
    rule: you can't diagnose or retry deliberately without seeing the output
    that broke. Still an Exception subclass, so existing bare `except
    Exception` handlers (agents/base.py) keep working unchanged.
    """

    def __init__(self, message: str, raw_text: str):
        super().__init__(message)
        self.raw_text = raw_text


class LLMClient:
    def __init__(self, model: str = "claude-sonnet-4-6"):
        self.model = model
        self.api_key = os.environ.get("ANTHROPIC_API_KEY")
        self._client = None
        # !! Added for Assignment #10's real cost-analysis requirement -- accumulates
        # actual provider-reported usage (response.usage), not an estimate, across
        # every live call this client instance makes.
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cache_creation_tokens = 0
        self.total_cache_read_tokens = 0
        self.call_log = []  # [{"label": str, "input": int, "output": int}, ...]
        if self.api_key:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self.api_key)
            except Exception as e:  # pragma: no cover
                print(f"[llm_client] Could not init Anthropic client ({e}); falling back to simulate mode.")
                self._client = None

    @property
    def live(self) -> bool:
        return self._client is not None

    def _record_usage(self, resp, label: str = ""):
        usage = getattr(resp, "usage", None)
        if usage is None:
            return
        in_tok = getattr(usage, "input_tokens", 0) or 0
        out_tok = getattr(usage, "output_tokens", 0) or 0
        cache_create = getattr(usage, "cache_creation_input_tokens", 0) or 0
        cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
        self.total_input_tokens += in_tok
        self.total_output_tokens += out_tok
        self.total_cache_creation_tokens += cache_create
        self.total_cache_read_tokens += cache_read
        self.call_log.append({"label": label, "input": in_tok, "output": out_tok,
                               "cache_creation": cache_create, "cache_read": cache_read})

    def cost_summary(self, input_price_per_mtok: float = 3.0, output_price_per_mtok: float = 15.0) -> dict:
        """Real cost from accumulated usage -- Sonnet 4.6 pricing by default."""
        input_cost = self.total_input_tokens / 1_000_000 * input_price_per_mtok
        output_cost = self.total_output_tokens / 1_000_000 * output_price_per_mtok
        return {
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_cache_creation_tokens": self.total_cache_creation_tokens,
            "total_cache_read_tokens": self.total_cache_read_tokens,
            "input_cost_usd": round(input_cost, 6),
            "output_cost_usd": round(output_cost, 6),
            "total_cost_usd": round(input_cost + output_cost, 6),
            "call_count": len(self.call_log),
            "calls": self.call_log,
        }

    def complete_text(self, system: str, user: str, max_tokens: int = 600, label: str = "") -> str:
        """
        Same call as complete_json() but returns the raw response text, unparsed --
        for agents that need plain prose back (e.g. agents/style_guide.py's
        "SCORE: [X/10]" / "REASON: [...]" format), not JSON.
        """
        if not self._client:
            raise RuntimeError("No live LLM client configured")

        resp = self._client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        self._record_usage(resp, label)
        return "".join(block.text for block in resp.content if block.type == "text").strip()

    def complete_json(self, system: str, user: str, max_tokens: int = 1500, label: str = "") -> dict:
        """
        Calls the model asking for JSON-only output and parses it.
        Raises on failure -- callers are expected to catch and fall back to
        simulate mode, since a live-mode failure should never crash the crew.
        """
        if not self._client:
            raise RuntimeError("No live LLM client configured")

        resp = self._client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        self._record_usage(resp, label)
        text = "".join(block.text for block in resp.content if block.type == "text")
        raw_text = text
        text = text.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:]
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise LLMJSONError(f"model response was not valid JSON: {e}", raw_text) from e
