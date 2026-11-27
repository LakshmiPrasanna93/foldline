"""Two interchangeable providers behind one interface:

- BaselineProvider: keyword rules (what the Phase 1 prototype approximates).
  Runs with no API key, so the harness always works end to end.
- ClaudeProvider: real LLM calls with forced-tool JSON output.

Interface: screen(email) -> dict, triage(email, feedback=None) -> dict,
group_stories(cards) -> list[list[str]], plus a `usage` record.
"""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field

from . import prompts


@dataclass
class Usage:
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    latencies_s: list = field(default_factory=list)

    def as_dict(self) -> dict:
        lat = sorted(self.latencies_s)

        def pct(p):
            return round(lat[min(len(lat) - 1, int(p * len(lat)))], 3) if lat else 0.0

        return {
            "calls": self.calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "latency_p50_s": pct(0.5),
            "latency_p95_s": pct(0.95),
        }


# ---------------------------------------------------------------- baseline

# Generic rules, NOT tuned on the golden set. Topic keywords come from the profile.
NOISE_RE = re.compile(r"sponsor|% off|register|webinar|book a demo|subscribe|top \d+|hacks", re.I)
FINANCIAL_RE = re.compile(r"\bstocks?\b|invest|crypto|\btoken\b|wallet|brokerage|trading", re.I)
INJECTION_RE = re.compile(r"ignore (all |your )?(previous|prior) instructions|you are an (ai|automated)|system:", re.I)
UNSURE_RE = re.compile(r"\bdraft\b|proposed|unclear|rumou?r", re.I)
STOP = set("a an the and or of to in for on with by is are was were be it this that as at from their its".split())


def content_words(text: str) -> set:
    return {w for w in re.findall(r"[a-z0-9%]+", text.lower()) if w not in STOP and len(w) > 2}


def first_sentence(text: str) -> str:
    return re.split(r"(?<=[.!?])\s+", text.strip())[0]


class BaselineProvider:
    name = "baseline"

    def __init__(self, profile: dict):
        self.profile = profile
        self.usage = Usage()
        self.topic_words = {
            t["id"]: content_words(t["name"] + " " + t["description"]) for t in profile["topics"]
        }

    def screen(self, email: dict) -> dict:
        text = email["subject"] + " " + email["body"]
        return {
            "financial": bool(FINANCIAL_RE.search(text)),
            "embedded_instructions": bool(INJECTION_RE.search(text)),
            "rationale": "keyword rules",
        }

    def triage(self, email: dict, feedback: str | None = None) -> dict:
        text = (email["subject"] + " " + email["body"]).lower()
        words = content_words(text)
        hits = {t: len(words & kws) for t, kws in self.topic_words.items()}
        topic, n = max(hits.items(), key=lambda kv: kv[1])
        if NOISE_RE.search(text):
            label = "noise"
        elif n == 0:
            label = "irrelevant"
        elif UNSURE_RE.search(text):
            label = "unsure"
        else:
            label = "relevant"
        lead = first_sentence(email["body"])
        card = label in ("relevant", "unsure")
        return {
            "label": label,
            "topic": topic if n else None,
            "confidence": min(1.0, n / 3),
            "headline": " ".join(email["subject"].split()[:12]) if card else "",
            "why_it_matters": " ".join(lead.split()[:20]) if card else "",
            "whats_new": "New fact" if card else "",
            "key_claim": lead if card else "",
            "evidence": [lead] if card else [],
        }

    def group_stories(self, cards: list) -> list:
        """Merge by Jaccard overlap of key-claim words (>= 0.5)."""
        groups: list = []
        for c in cards:
            words = content_words(c["key_claim"])
            for g in groups:
                if any(_jaccard(words, content_words(o["key_claim"])) >= 0.5 for o in g):
                    g.append(c)
                    break
            else:
                groups.append([c])
        return [[c["id"] for c in g] for g in groups]


def _jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a | b else 0.0


# ---------------------------------------------------------------- LLM

class ClaudeProvider:
    name = "claude"

    def __init__(self, profile: dict, model: str = "claude-haiku-5-5", client=None):
        self.profile = profile
        self.model = model
        self.usage = Usage()
        if client is None:
            import anthropic  # imported lazily so baseline runs need no SDK

            if not os.environ.get("ANTHROPIC_API_KEY"):
                raise SystemExit("ANTHROPIC_API_KEY is not set. Use --provider baseline, or export a key.")
            client = anthropic.Anthropic(max_retries=3)
        self.client = client
        self.triage_system = prompts.TRIAGE_SYSTEM.format(topics=prompts.format_topics(profile))

    def _call(self, system: str, user: str, tool: dict, max_tokens: int = 600) -> dict:
        t0 = time.perf_counter()
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=0,
            system=system,
            tools=[tool],
            tool_choice={"type": "tool", "name": tool["name"]},
            messages=[{"role": "user", "content": user}],
        )
        self.usage.latencies_s.append(time.perf_counter() - t0)
        self.usage.calls += 1
        self.usage.input_tokens += resp.usage.input_tokens
        self.usage.output_tokens += resp.usage.output_tokens
        for block in resp.content:
            if getattr(block, "type", None) == "tool_use" and block.name == tool["name"]:
                return dict(block.input)
        raise RuntimeError(f"Model did not call {tool['name']}")

    def screen(self, email: dict) -> dict:
        return self._call(prompts.SCREEN_SYSTEM, prompts.email_block(email), prompts.SCREEN_TOOL, 200)

    def triage(self, email: dict, feedback: str | None = None) -> dict:
        user = prompts.email_block(email)
        if feedback:
            user += "\n\n" + prompts.GROUNDING_RETRY_NOTE.format(problem=feedback)
        out = self._call(self.triage_system, user, prompts.TRIAGE_TOOL)
        out.setdefault("evidence", [])
        return out

    def group_stories(self, cards: list) -> list:
        if len(cards) < 2:
            return [[c["id"] for c in cards]]
        listing = json.dumps(
            [{"id": c["id"], "headline": c["headline"], "key_claim": c["key_claim"]} for c in cards], indent=1
        )
        out = self._call(prompts.DEDUP_SYSTEM, f"<cards>\n{listing}\n</cards>", prompts.DEDUP_TOOL, 800)
        return _repair_groups(out.get("groups", []), [c["id"] for c in cards])


def _repair_groups(groups: list, ids: list) -> list:
    """Make groups a valid partition: drop unknown/duplicate ids, add missing ones as singletons."""
    seen, fixed = set(), []
    for g in groups:
        g2 = [i for i in g if i in ids and i not in seen]
        seen.update(g2)
        if g2:
            fixed.append(g2)
    fixed += [[i] for i in ids if i not in seen]
    return fixed


def make_provider(name: str, profile: dict, model: str):
    if name == "baseline":
        return BaselineProvider(profile)
    if name == "claude":
        return ClaudeProvider(profile, model=model)
    raise ValueError(name)
