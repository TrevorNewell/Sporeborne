from dotenv import load_dotenv
load_dotenv()

#!/usr/bin/env python3
"""
Sporeborne Goal-Oriented Coding Agent
=======================================
Assignment #5 (ELVTR "Multi-Agent AI for Game Development", Class 7).

Raw orchestration -- no framework, no CrewAI-style Agent/AgentResult base
class (see agents/base.py) -- by design. The assignment specifically asks
for manual API calls, custom parsing, and full visibility into every
decision the agent makes before it writes a file into the game, rather
than the multi-agent-role pattern crew.py uses.

The loop:
    scan Source/Sporeborne_Rogue/  ->  parse the GDD's own build order
    (the G1-G6 gate table + MVP list in section 7)  ->  score every gap
    with priority_score()  ->  ask the model to write the top-priority
    missing feature  ->  validate + write  ->  re-scan  ->  repeat until
    --max-features is reached or nothing is left to build.

Usage:
    python3 goal_agent.py                  # writes one feature (default)
    python3 goal_agent.py --max-features 3 # writes up to three
    python3 goal_agent.py --dry-run        # scan+score+print only, no LLM
                                            # call, no files written
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone

from agents import LLMClient, LLMJSONError
from agents.retriever import _chunk_gdd

HERE = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(HERE, "output")
GDD_PATH = os.path.join(HERE, "design", "GDD_Sporeborne.md")
SOURCE_ROOT = os.path.normpath(os.path.join(HERE, "..", "Sporeborne_Rogue", "Source", "Sporeborne_Rogue"))
BUILD_CS_PATH = os.path.join(SOURCE_ROOT, "Sporeborne_Rogue.Build.cs")
STATE_PATH = os.path.join(OUTPUT_DIR, "goal_agent_state.md")
RESULT_PATH = os.path.join(OUTPUT_DIR, "goal_agent_result.json")
README_PATH = os.path.join(OUTPUT_DIR, "ASSIGNMENT5_README.md")

MAX_LLM_RETRIES = 1
ALLOWED_EXTENSIONS = (".h", ".cpp")

_WORD_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "to", "in", "on", "at", "is", "are",
    "with", "for", "all", "then", "this", "that", "it", "its", "per",
}
# Our own inference from GDD section 9 ("agents may only author JSON/CSV/
# code text, never binary uassets"), not a verbatim GDD list -- see
# priority_score()'s docstring.
_PENALTY_KEYWORDS = {
    "sprite", "animation", "flipbook", "paperzd", "widget", "umg", "ui",
    "menu", "screen", "hud",
}

MVP_HEADER_RE = re.compile(r"\*\*MVP.*?\*\*\s*\n((?:^- .+\n?)+)", re.M)
GATE_ROW_RE = re.compile(r'^\|\s*\*\*(G\d+)[^|*]*\*\*\s*\|\s*(.+?)\s*\|\s*$', re.M)
PAREN_RE = re.compile(r"\(([^)]*)\)")
CLASS_NAME_RE = re.compile(r"class\s+(?:\w+_API\s+)?([UAF][A-Za-z0-9_]*)\s*[:;]")
DEPENDENCY_RE = re.compile(r'PublicDependencyModuleNames\.AddRange\(new string\[\]\s*\{([^}]*)\}')


def log(msg):
    print(f"[goal_agent] {msg}")


# ---------------------------------------------------------------------------
# 1. File-system scanner ("codebase perception")
# ---------------------------------------------------------------------------

def list_files(root: str) -> list:
    """Relative .h/.cpp paths under `root`, forward-slashed."""
    if not os.path.isdir(root):
        return []
    found = []
    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            if name.endswith(ALLOWED_EXTENSIONS):
                rel = os.path.relpath(os.path.join(dirpath, name), root)
                found.append(rel.replace(os.sep, "/"))
    return sorted(found)


def read_file(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except (OSError, UnicodeDecodeError):
        return ""


def get_build_dependencies(build_cs_path: str) -> list:
    """Parses PublicDependencyModuleNames out of the module's Build.cs."""
    text = read_file(build_cs_path)
    match = DEPENDENCY_RE.search(text)
    if not match:
        return []
    return [s.strip().strip('"') for s in match.group(1).split(",") if s.strip()]


def build_codebase_index(source_root: str) -> dict:
    files = list_files(source_root)
    class_names = []
    content_parts = []
    for rel in files:
        text = read_file(os.path.join(source_root, rel))
        content_parts.append(text)
        if rel.endswith(".h"):
            class_names.extend(CLASS_NAME_RE.findall(text))
    return {
        "files": files,
        "class_names": class_names,
        "filename_blob": " ".join(files).lower(),
        "content_blob": " ".join(content_parts).lower(),
    }


# ---------------------------------------------------------------------------
# 2. GDD parser -- extract_required_features
# ---------------------------------------------------------------------------

def _find_section(gdd_text: str, heading_prefix: str) -> str:
    """Reuses retriever.py's exact '## ' chunking so both scripts see the
    same GDD sections the same way."""
    for section in _chunk_gdd(gdd_text):
        if section["id"].startswith(heading_prefix):
            return section["text"]
    return ""


def _extract_mvp_bullets(section_text: str) -> list:
    match = MVP_HEADER_RE.search(section_text)
    if not match:
        return []
    bullets = []
    for line in match.group(1).splitlines():
        line = line.strip()
        if line.startswith("- "):
            bullets.append(line[2:].strip())
    return bullets


def _split_gate_cell(cell_text: str):
    """
    Splits one Gate-table cell into distinct buildable systems.

    e.g. "Enemy AI + telegraphed projectiles + damage pipeline; one room
    is genuinely fun to clear." ->
        (["Enemy AI", "telegraphed projectiles", "damage pipeline"],
         "one room is genuinely fun to clear.",
         [])

    Returns (sub_features, gate_narrative, notes).
    """
    notes = [n.strip() for n in PAREN_RE.findall(cell_text) if n.strip()]
    cell = PAREN_RE.sub("", cell_text).strip()

    clauses = [c.strip() for c in cell.split(";") if c.strip()]
    if not clauses:
        return [], "", notes
    systems_clause = clauses[0]
    narrative = "; ".join(clauses[1:])

    if "+" in systems_clause:
        parts = [p.strip() for p in systems_clause.split("+")]
    else:
        parts = [p.strip() for p in systems_clause.split(",")]

    # The last item often carries a trailing qualifier on the whole list
    # ("... all feel good in an empty room.") rather than being part of
    # the list itself -- keep only the text before "all" when present.
    if parts:
        last = parts[-1]
        all_match = re.search(r"\ball\b", last)
        if all_match:
            parts[-1] = last[:all_match.start()].strip()

    cleaned = []
    for p in parts:
        p = re.sub(r"^(then|and)\s+", "", p, flags=re.I)
        p = p.rstrip(".").strip()
        if p:
            cleaned.append(p)
    return cleaned, narrative, notes


def extract_required_features(gdd_path: str) -> list:
    """
    Parses GDD section 7 ("Production Plan & Scope") into feature dicts:
    the flat MVP bullet list (ungated, confirms in-scope-not-stretch) plus
    the G1-G6 gate table (explicitly dependency-ordered -- "each gate must
    be provably true before the next opens").
    """
    with open(gdd_path, encoding="utf-8") as f:
        gdd_text = f.read()

    section = _find_section(gdd_text, "7 ")
    if not section:
        raise ValueError(
            "GDD section '7 - Production Plan & Scope' not found; "
            "the GDD's structure may have changed since this parser was written."
        )

    features = []

    for i, bullet in enumerate(_extract_mvp_bullets(section), start=1):
        features.append({
            "id": f"MVP-{i}",
            "gate": None,
            "gate_order": None,
            "description": bullet,
            "source": "mvp_list",
            "gate_narrative": "",
            "notes": [],
        })

    for gate_id, cell_text in GATE_ROW_RE.findall(section):
        gate_order = int(gate_id[1:])
        sub_features, narrative, notes = _split_gate_cell(cell_text)
        for j, desc in enumerate(sub_features, start=1):
            features.append({
                "id": f"{gate_id}-{j}",
                "gate": gate_id,
                "gate_order": gate_order,
                "description": desc,
                "source": "gate_table",
                "gate_narrative": narrative,
                "notes": notes,
            })

    return features


# ---------------------------------------------------------------------------
# 3. Gap detection
# ---------------------------------------------------------------------------

def extract_keywords(text: str) -> set:
    tokens = _WORD_RE.findall(text.lower())
    return {t for t in tokens if t not in _STOPWORDS and len(t) > 1}


def classify_build_state(feature: dict, codebase_index: dict) -> str:
    """Keyword-overlap heuristic against filenames/class names/file
    contents. Deliberately simple (no C++ parsing) -- this is codebase
    *perception*, a cheap signal to rank against, not ground truth."""
    keywords = extract_keywords(feature["description"])
    if not keywords:
        return "missing"
    haystack = (
        codebase_index["filename_blob"] + " " +
        " ".join(codebase_index["class_names"]).lower() + " " +
        codebase_index["content_blob"]
    )
    matched = sum(1 for k in keywords if k in haystack)
    ratio = matched / len(keywords)
    if ratio >= 0.6:
        return "built"
    if ratio > 0.0:
        return "partial"
    return "missing"


# ---------------------------------------------------------------------------
# 4. priority_score -- required by the assignment's own scaffold spec
# ---------------------------------------------------------------------------

def priority_score(feature: dict, codebase_state: dict) -> float:
    """
    Weighs four signals the GDD itself provides, plus one we infer:

      dependency  -- GDD section 7's Gate table (G1..G6) is an explicit,
                     sequential build order ("each gate must be provably
                     true before the next opens"). Earlier gates score
                     higher. Ungated MVP-only bullets aren't on that
                     critical path, so they get a neutral mid score.
      blocker     -- a feature is a blocker if some other still-missing
                     candidate sits at a strictly later gate; closing it
                     is a prerequisite for the rest of the build order.
      mvp_overlap -- does this feature's own wording show up in the GDD's
                     flat MVP bullet list? That confirms it's "the
                     contract," not stretch scope (GDD section 7's own
                     language), independent of which gate it's in.
      build_state -- missing beats partial beats built. (Built features
                     never actually reach this function -- they're
                     filtered out of the candidate list before scoring.)
      penalty     -- our own inference, NOT a GDD quote: section 9 says
                     agents may only author JSON/CSV/code text, never
                     binary uassets (Input Mapping Contexts, Paper2D
                     Flipbooks, Animation Blueprints, UMG widgets). A
                     feature whose own description implies one of those
                     can't be fully delivered as compilable C++, so it's
                     penalized rather than excluded outright.
    """
    gate_order = feature["gate_order"]
    dependency = 0.5 if gate_order is None else (7 - gate_order) / 6

    blocker = 0.0
    for other in codebase_state["all_features"]:
        if other is feature or other["build_state"] == "built":
            continue
        if other["gate_order"] is not None and gate_order is not None and other["gate_order"] > gate_order:
            blocker = 1.0
            break

    feature_kw = extract_keywords(feature["description"])
    mvp_kw = codebase_state["mvp_keywords"]
    mvp_overlap = (len(feature_kw & mvp_kw) / len(feature_kw)) if feature_kw else 0.0

    build_state_score = {"missing": 1.0, "partial": 0.6, "built": 0.0}[feature["build_state"]]

    penalty = 1.0 if feature_kw & _PENALTY_KEYWORDS else 0.0

    score = (
        0.35 * dependency +
        0.20 * blocker +
        0.15 * mvp_overlap +
        0.20 * build_state_score -
        0.25 * penalty
    )
    return max(0.0, score)


# ---------------------------------------------------------------------------
# 5. Code-writing step
# ---------------------------------------------------------------------------

def _safe_join(source_root: str, rel_path: str) -> str:
    """Resolves rel_path inside source_root or raises ValueError. Rejects
    absolute paths, '..' segments, and non-.h/.cpp extensions -- an LLM
    response is untrusted input, same as any other external data."""
    if not rel_path or os.path.isabs(rel_path):
        raise ValueError(f"rejected unsafe path: {rel_path!r}")
    normalized = rel_path.replace("\\", "/")
    if ".." in normalized.split("/"):
        raise ValueError(f"rejected unsafe path: {rel_path!r}")
    if not normalized.endswith(ALLOWED_EXTENSIONS):
        raise ValueError(f"rejected path with disallowed extension: {rel_path!r}")

    root_abs = os.path.normpath(os.path.abspath(source_root))
    candidate = os.path.normpath(os.path.join(root_abs, normalized.lstrip("/")))
    if candidate != root_abs and not candidate.startswith(root_abs + os.sep):
        raise ValueError(f"rejected path escaping source root: {rel_path!r}")
    return candidate


def build_codegen_prompt(feature: dict, codebase_index: dict, build_deps: list):
    system = (
        "You are writing Unreal Engine 5.8 C++ for the Sporeborne project. "
        "Respond with ONLY a JSON object, no prose, no markdown fences, "
        "shaped exactly like this:\n"
        '{"files": [{"path": "RelativeName.h", "content": "..."}, '
        '{"path": "RelativeName.cpp", "content": "..."}], '
        '"build_dependencies_needed": ["ModuleName", ...], '
        '"reasoning": "one paragraph explaining the approach"}\n\n'
        "Rules:\n"
        "- 'path' is relative to Source/Sporeborne_Rogue/ only: no leading "
        "slash, no '..', forward slashes, and must end in .h or .cpp.\n"
        "- The module currently depends on exactly these engine modules: "
        f"{', '.join(build_deps)}. Do not #include headers from any other "
        "module (e.g. Paper2D, PaperZD, EnhancedInput) unless you list that "
        "module's name in build_dependencies_needed -- it will NOT be added "
        "automatically, a human reviews and adds it manually.\n"
        "- Match Unreal naming conventions (U-prefixed UObject/UActorComponent "
        "classes, A-prefixed AActor classes, GENERATED_BODY()).\n"
        "- This module's actual include search path is Source/ (the modules' "
        "parent directory), not Source/Sporeborne_Rogue/ itself -- confirmed "
        "against the real compiler response file. Any include of a header in a "
        "subfolder of this module (including this feature's own files) MUST be "
        "prefixed with the module name, e.g. "
        "#include \"Sporeborne_Rogue/AI/Foo.h\", never the bare "
        "#include \"AI/Foo.h\" form.\n"
        "- When calling a member function through a pointer returned by an "
        "engine getter (e.g. GetCapsuleComponent(), GetMesh()), #include the "
        "component's own header (e.g. Components/CapsuleComponent.h) rather "
        "than relying on the forward declaration in the base class header -- "
        "a forward-declared type compiles for pointer storage but not for "
        "calling its methods.\n"
        "- Keep the change small and self-contained: one feature, not a "
        "sweeping refactor of unrelated files."
    )
    existing_files = "\n".join(f"  - {f}" for f in codebase_index["files"]) or "  (none yet -- empty module)"
    user = (
        "Implement this GDD-sourced feature for Morel's game, Sporeborne:\n\n"
        f"Feature: {feature['description']}\n"
        f"GDD gate: {feature['gate'] or '(ungated MVP scope item)'}\n"
        f"GDD context for this gate: {feature['gate_narrative'] or '(none)'}\n"
        f"GDD annotations: {'; '.join(feature['notes']) or '(none)'}\n\n"
        f"Current files in Source/Sporeborne_Rogue/:\n{existing_files}\n\n"
        "Write the smallest correct C++ implementation of this one feature."
    )
    return system, user


def _validate_envelope(envelope: dict) -> dict:
    if not isinstance(envelope, dict):
        raise ValueError("model response was not a JSON object")
    files = envelope.get("files")
    if not isinstance(files, list) or not files:
        raise ValueError("model response is missing a non-empty 'files' list")

    seen = {}
    for entry in files:
        if not isinstance(entry, dict):
            continue
        path = entry.get("path", "")
        content = entry.get("content", "")
        if not content or not content.strip():
            log(f"  skipping {path!r}: empty content")
            continue
        try:
            _safe_join(SOURCE_ROOT, path)
        except ValueError as e:
            log(f"  skipping unsafe file: {e}")
            continue
        if path in seen:
            log(f"  duplicate path {path!r} in response; keeping the later entry")
        seen[path] = content

    if not seen:
        raise ValueError("no valid files survived validation")

    envelope["files"] = [{"path": p, "content": c} for p, c in seen.items()]
    envelope.setdefault("build_dependencies_needed", [])
    envelope.setdefault("reasoning", "")
    return envelope


def generate_feature(llm, feature: dict, codebase_index: dict, build_deps: list) -> dict:
    system, user = build_codegen_prompt(feature, codebase_index, build_deps)
    last_error = None
    for attempt in range(1 + MAX_LLM_RETRIES):
        try:
            envelope = llm.complete_json(system, user, max_tokens=4000)
            return _validate_envelope(envelope)
        except LLMJSONError as e:
            last_error = e
            log(f"  live call returned unparseable JSON (attempt {attempt + 1}): {e}")
            log(f"  raw output was: {e.raw_text[:500]}")
        except Exception as e:
            last_error = e
            log(f"  generation attempt {attempt + 1} failed: {e}")
    raise RuntimeError(f"generation failed after {1 + MAX_LLM_RETRIES} attempt(s): {last_error}")


def write_feature_files(envelope: dict) -> list:
    written = []
    for entry in envelope["files"]:
        target = _safe_join(SOURCE_ROOT, entry["path"])
        if os.path.exists(target):
            log(f"  !! overwriting existing file: {entry['path']}")
        parent = os.path.dirname(target)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            f.write(entry["content"])
        written.append(entry["path"])
        log(f"  wrote {target}")
    return written


# ---------------------------------------------------------------------------
# 7. Persistent markdown state -- "the agent picks up where it left off"
# ---------------------------------------------------------------------------

STATE_SECTIONS = ["Built", "Decisions", "Next"]
# Display-only filler written when a section is empty -- must never be
# read back in as a real entry on the next run (that would make it
# permanent instead of disappearing once real content exists).
_PLACEHOLDER_LINES = {"- (none yet)", "- (nothing left to build)"}


def _read_state_sections(path: str) -> dict:
    if not os.path.exists(path):
        return {name: [] for name in STATE_SECTIONS}
    with open(path, encoding="utf-8") as f:
        text = f.read()
    sections = {name: [] for name in STATE_SECTIONS}
    for chunk in re.split(r"\n(?=## )", text):
        chunk = chunk.strip()
        m = re.match(r"##\s*(\w+)\s*\n(.*)", chunk, re.S)
        if not m:
            continue
        name, body = m.group(1), m.group(2)
        if name in sections:
            sections[name] = [
                line.strip() for line in body.splitlines()
                if line.strip().startswith("-") and line.strip() not in _PLACEHOLDER_LINES
            ]
    return sections


def _write_state_sections(path: str, sections: dict):
    lines = ["# Goal Agent State", ""]
    for name in STATE_SECTIONS:
        lines.append(f"## {name}")
        entries = sections.get(name) or ["- (none yet)"]
        lines.extend(entries)
        lines.append("")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def append_state_entry(sections: dict, section: str, text: str):
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    sections[section].append(f"- [{timestamp}] {text}")


def replace_next_section(sections: dict, candidates: list):
    sections["Next"] = [
        f"- {c['id']} (score={c['priority_score']:.3f}): {c['description']}"
        for c in candidates[:5]
    ] or ["- (nothing left to build)"]


CHANGED_HEADING = "## What I changed before accepting it"


def _write_readme(readme_path: str, built_iterations: list):
    """
    Assignment #5 requires a ReadMe explaining what the agent built, why it
    picked that feature, and what the human changed before accepting it.
    The first two are filled in from this run's own trace; the third is
    inherently a human judgment call made *after* reading the generated
    code and compiling it, so it's left as a TODO for the student -- never
    fabricated.
    """
    existing = read_file(readme_path)
    changed_section = CHANGED_HEADING in existing

    lines = []
    if not existing:
        lines.append("# Assignment #5 -- Goal-Oriented Coding Agent\n")
        lines.append(
            "Generated by `Claude/goal_agent.py`. Each run appends what it built "
            "and why below; fill in \"What I changed before accepting it\" "
            "yourself after reading the generated code.\n"
        )
    else:
        lines.append(existing.rstrip())
        lines.append("")

    for it in built_iterations:
        lines.append(f"## Built: {it['picked']}")
        lines.append(f"- **Why this feature**: ranked #1 by `priority_score()` "
                      f"among {len(it['ranked_candidates'])} GDD-derived candidates.")
        lines.append(f"- **Files written**: {', '.join(it.get('written_files', []))}")
        if it.get("build_dependencies_needed"):
            lines.append(f"- **Action required**: add to Build.cs -> "
                          f"{', '.join(it['build_dependencies_needed'])}")
        lines.append(f"- **Agent's reasoning**: {it.get('reasoning', '')}")
        lines.append("")

    if not changed_section:
        lines.append(CHANGED_HEADING)
        lines.append("_TODO: after reading the generated files and compiling, "
                      "note here what you changed and why._")
        lines.append("")

    with open(readme_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


# ---------------------------------------------------------------------------
# 6. Orchestration loop
# ---------------------------------------------------------------------------

def _scan_and_score(skipped_ids: set):
    codebase_index = build_codebase_index(SOURCE_ROOT)
    build_deps = get_build_dependencies(BUILD_CS_PATH)
    features = extract_required_features(GDD_PATH)
    for f in features:
        f["build_state"] = classify_build_state(f, codebase_index)

    mvp_keywords = set()
    for f in features:
        if f["source"] == "mvp_list":
            mvp_keywords |= extract_keywords(f["description"])

    codebase_state = {"all_features": features, "mvp_keywords": mvp_keywords}
    candidates = [f for f in features if f["build_state"] != "built" and f["id"] not in skipped_ids]
    for f in candidates:
        f["priority_score"] = priority_score(f, codebase_state)
    candidates.sort(key=lambda f: f["priority_score"], reverse=True)

    return codebase_index, build_deps, candidates


def run(max_features: int, dry_run: bool) -> dict:
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    llm = LLMClient()
    log(f"LLM mode: {'LIVE (ANTHROPIC_API_KEY found)' if llm.live else 'NO API KEY -- scoring only, cannot write code'}")

    state = _read_state_sections(STATE_PATH)
    trace = {"timestamp": datetime.now(timezone.utc).isoformat(), "iterations": []}

    skipped_ids = set()
    built_count = 0
    last_candidates = []

    while built_count < max_features:
        codebase_index, build_deps, candidates = _scan_and_score(skipped_ids)
        last_candidates = candidates

        if not candidates:
            log("No missing or partial features left to build.")
            break

        log(f"--- Scored {len(candidates)} candidate(s), ranked ---")
        for c in candidates[:8]:
            log(f"  {c['priority_score']:.3f}  {c['id']:<8}  ({c['build_state']})  {c['description']}")

        top = candidates[0]
        iteration = {
            "ranked_candidates": [
                {"id": c["id"], "description": c["description"], "gate": c["gate"],
                 "build_state": c["build_state"], "score": round(c["priority_score"], 4)}
                for c in candidates
            ],
            "picked": top["id"],
        }

        if dry_run:
            log(f"--dry-run: would build {top['id']} ({top['description']}); stopping before any LLM call.")
            trace["iterations"].append(iteration)
            break

        log(f"Picked {top['id']}: {top['description']} (score={top['priority_score']:.3f})")
        try:
            envelope = generate_feature(llm, top, codebase_index, build_deps)
            written = write_feature_files(envelope)
            append_state_entry(state, "Built", f"{top['id']} -- {top['description']} -> {', '.join(written)}")
            if envelope["reasoning"]:
                append_state_entry(state, "Decisions", f"{top['id']}: {envelope['reasoning']}")
            if envelope["build_dependencies_needed"]:
                deps = ", ".join(envelope["build_dependencies_needed"])
                log(f"  !! ACTION REQUIRED: add to Build.cs PublicDependencyModuleNames: {deps}")
                append_state_entry(state, "Decisions", f"!! ACTION REQUIRED for {top['id']}: add module dependency: {deps}")
            iteration["written_files"] = written
            iteration["reasoning"] = envelope["reasoning"]
            iteration["build_dependencies_needed"] = envelope["build_dependencies_needed"]
            built_count += 1
        except Exception as e:
            log(f"  generation for {top['id']} failed, skipping: {e}")
            append_state_entry(state, "Decisions", f"SKIPPED {top['id']} ({top['description']}): {e}")
            skipped_ids.add(top["id"])
            iteration["error"] = str(e)

        trace["iterations"].append(iteration)

    _, _, final_candidates = _scan_and_score(skipped_ids)
    replace_next_section(state, final_candidates or last_candidates)

    _write_state_sections(STATE_PATH, state)
    log(f"Wrote {STATE_PATH}")

    trace["built_count"] = built_count
    with open(RESULT_PATH, "w") as f:
        json.dump(trace, f, indent=2)
    log(f"Wrote {RESULT_PATH}")

    built_iterations = [it for it in trace["iterations"] if "written_files" in it]
    if built_iterations:
        _write_readme(README_PATH, built_iterations)
        log(f"Wrote {README_PATH}")

    return trace


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sporeborne goal-oriented coding agent (Assignment #5)")
    parser.add_argument("--max-features", type=int, default=1,
                         help="how many features to write in this run (default: 1)")
    parser.add_argument("--dry-run", action="store_true",
                         help="scan, parse, and score only -- no LLM call, no files written")
    args = parser.parse_args()

    run(max_features=args.max_features, dry_run=args.dry_run)
    sys.exit(0)
