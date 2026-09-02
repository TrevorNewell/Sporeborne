"""
Base class every agent in the Sporeborne crew inherits from.

Each agent implements exactly two methods:
  - build_prompt(context) -> (system, user)   # what to ask the real model
  - simulate(context)     -> dict              # deterministic stand-in output,
                                                  used when no API key is set
                                                  or the live call fails

`run()` is the same for every agent: try live, fall back to simulate,
never raise -- an agent that can't produce output returns a structured
failure dict instead of crashing the crew, which is what "coordinate
without crashing" requires in practice.
"""

from dataclasses import dataclass, field


@dataclass
class AgentResult:
    agent: str
    ok: bool
    output: dict = field(default_factory=dict)
    mode: str = "simulate"  # "live" or "simulate"
    error: str = ""


class Agent:
    name = "base-agent"

    def __init__(self, llm_client):
        self.llm = llm_client

    def build_prompt(self, context: dict):
        raise NotImplementedError

    def simulate(self, context: dict) -> dict:
        raise NotImplementedError

    def run(self, context: dict) -> AgentResult:
        if self.llm.live:
            try:
                system, user = self.build_prompt(context)
                output = self.llm.complete_json(system, user)
                return AgentResult(agent=self.name, ok=True, output=output, mode="live")
            except Exception as e:
                print(f"[{self.name}] live call failed ({e}); falling back to simulate mode.")

        try:
            output = self.simulate(context)
            return AgentResult(agent=self.name, ok=True, output=output, mode="simulate")
        except Exception as e:
            return AgentResult(agent=self.name, ok=False, error=str(e), mode="simulate")
