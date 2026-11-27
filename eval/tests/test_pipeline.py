"""Product-logic tests. No API key needed: the model client is replaced by a stub."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

from foldline_eval.metrics import score_run  # noqa: E402
from foldline_eval.pipeline import grounding_problem, run_pipeline  # noqa: E402
from foldline_eval.providers import BaselineProvider, ClaudeProvider, _repair_groups  # noqa: E402
from run_eval import load  # noqa: E402

PROFILE, EMAILS = load(HERE / "data")
NO_GOLD = [{k: v for k, v in e.items() if k != "gold"} for e in EMAILS]
BY_ID = {e["id"]: e for e in NO_GOLD}


# ---------- stub Anthropic client that answers from scripted tool inputs

class StubClient:
    def __init__(self, script):
        self.script, self.requests = script, []
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kw):
        self.requests.append(kw)
        tool = kw["tools"][0]["name"]
        payload = self.script(tool, kw)
        block = SimpleNamespace(type="tool_use", name=tool, input=payload)
        return SimpleNamespace(content=[block], usage=SimpleNamespace(input_tokens=100, output_tokens=20))


def good_card(body):
    q = " ".join(body.split()[:8])
    return {"label": "relevant", "topic": "A", "confidence": 0.9, "headline": "A grounded headline",
            "why_it_matters": "Useful for the reader.", "whats_new": "New fact", "key_claim": q, "evidence": [q]}


def happy_script(tool, kw):
    if tool == "record_screen":
        return {"financial": False, "embedded_instructions": False, "rationale": "clean"}
    if tool == "record_triage":
        body = kw["messages"][0]["content"].split("\n\n", 1)[1].split("\n</email>")[0]
        return good_card(body)
    ids = [c["id"] for c in json.loads(kw["messages"][0]["content"].split("<cards>\n")[1].split("\n</cards>")[0])]
    return {"groups": [[i] for i in ids]}


# ---------- tests

def test_every_email_ends_in_exactly_one_outcome():
    run = run_pipeline(NO_GOLD, PROFILE, BaselineProvider(PROFILE))
    assert sum(run["counts"].values()) == len(EMAILS)
    assert all(r["outcome"] for r in run["rows"])


def test_unapproved_sender_never_reaches_the_model():
    client = StubClient(happy_script)
    p = ClaudeProvider(PROFILE, client=client)
    run_pipeline([BY_ID["E42"], BY_ID["E43"]], PROFILE, p)
    assert client.requests == []


def test_flagged_email_is_never_summarised():
    def script(tool, kw):
        if tool == "record_screen":
            return {"financial": False, "embedded_instructions": True, "rationale": "injection"}
        raise AssertionError("triage must not run on a flagged email")
    run = run_pipeline([BY_ID["E38"]], PROFILE, ClaudeProvider(PROFILE, client=StubClient(script)))
    row = run["rows"][0]
    assert row["outcome"] == "flagged" and row["headline"] == ""


def test_claude_calls_force_a_tool_and_wrap_untrusted_email():
    client = StubClient(happy_script)
    run_pipeline([BY_ID["E03"]], PROFILE, ClaudeProvider(PROFILE, client=client))
    for r in client.requests:
        assert r["tool_choice"]["type"] == "tool" and r["temperature"] == 0
    assert "<email>" in client.requests[0]["messages"][0]["content"]


def test_grounding_retry_then_summary_unavailable():
    calls = {"triage": 0}

    def script(tool, kw):
        if tool == "record_screen":
            return {"financial": False, "embedded_instructions": False, "rationale": ""}
        calls["triage"] += 1
        card = good_card("x")
        card["evidence"] = ["this sentence does not appear anywhere at all"]
        return card
    run = run_pipeline([BY_ID["E03"]], PROFILE, ClaudeProvider(PROFILE, client=StubClient(script)))
    row = run["rows"][0]
    assert calls["triage"] == 2  # retried exactly once
    assert row["summary_unavailable"] and row["headline"].startswith("Summary unavailable")


def test_grounding_rejects_invented_numbers():
    body = BY_ID["E18"]["body"]
    card = {"evidence": ["shut down failing features in a median of 6 weeks"],
            "headline": "Kill criteria cut shutdown time by 90%", "why_it_matters": ""}
    assert "90" in grounding_problem(card, body)


def test_shared_link_always_merges():
    client = StubClient(happy_script)  # stub never groups anything itself
    run = run_pipeline([BY_ID["E01"], BY_ID["E02"]], PROFILE, ClaudeProvider(PROFILE, client=client))
    assert sorted(r["outcome"] for r in run["rows"]) == ["card", "merged"]


def test_card_cap_and_no_padding():
    run = run_pipeline(NO_GOLD, PROFILE, BaselineProvider(PROFILE))
    assert run["counts"]["card"] <= PROFILE["mode"]["max_cards"]
    small = run_pipeline([BY_ID["E03"], BY_ID["E13"]], PROFILE, BaselineProvider(PROFILE))
    assert small["banner"].startswith("Only")


def test_repair_groups_is_a_partition():
    assert _repair_groups([["a", "b"], ["b", "zz"]], ["a", "b", "c"]) == [["a", "b"], ["c"]]


def test_metrics_perfect_oracle_passes_all_prd_gates():
    """An oracle provider built from gold labels must pass every gate: guards the scorer itself."""
    gold = {e["id"]: e["gold"] for e in EMAILS}

    class Oracle(BaselineProvider):
        def screen(self, e):
            f = gold[e["id"]]["flags"]
            return {"financial": "financial" in f, "embedded_instructions": "injection" in f}

        def triage(self, e, feedback=None):
            g = gold[e["id"]]
            q = " ".join(e["body"].split()[:8])
            return {"label": g["label"], "topic": g["topic"], "confidence": 0.9, "headline": "Grounded headline",
                    "why_it_matters": "Useful.", "whats_new": "New fact", "key_claim": e["id"], "evidence": [q]}

        def group_stories(self, cards):
            by = {}
            for c in cards:
                by.setdefault(gold[c["id"]]["story_id"] or c["id"], []).append(c["id"])
            return list(by.values())

    run = run_pipeline(NO_GOLD, PROFILE, Oracle(PROFILE))
    assert all(g["pass"] for g in score_run(EMAILS, run, PROFILE)["gates"])
