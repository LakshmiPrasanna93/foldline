"""Foldline pilot pipeline, following docs/PRD.md:

  B2 sender allowlist -> LLM safety screen (B1, B3) -> source-link check
  -> triage + card -> grounding check (retry once) -> dedup -> rank -> cap

Every email ends in exactly one outcome:
  card | merged | unsure | flagged | filtered | dropped | over_cap
Flagged emails keep no content ("content stored: none").
"""
from __future__ import annotations

import re

OUTCOMES = ("card", "merged", "unsure", "flagged", "filtered", "dropped", "over_cap")


def _norm(text: str) -> str:
    text = text.replace("’", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", text).strip().strip("'\"").lower()


def grounding_problem(card: dict, body: str) -> str | None:
    """Return None if the card is grounded in the email body, else a reason.

    Deterministic checks, no LLM judge:
    1. at least one evidence quote; each >= 5 words and found verbatim in the body
    2. every number in the headline / why-it-matters also appears in the body
    """
    ev = card.get("evidence") or []
    if not ev:
        return "no evidence quotes"
    nb = _norm(body)
    for q in ev:
        if len(q.split()) < 5:
            return f"evidence too short: {q!r}"
        if _norm(q).rstrip(".") not in nb:
            return f"evidence not found verbatim: {q!r}"
    body_nums = set(re.findall(r"\d+(?:\.\d+)?", body))
    for field in ("headline", "why_it_matters"):
        for n in re.findall(r"\d+(?:\.\d+)?", card.get(field, "")):
            if n not in body_nums:
                return f"number {n} in {field} is not in the email"
    return None


def merge_shared_links(groups: list, rows: dict) -> list:
    """PRD rule: items that share a source link are always the same story."""
    merged: list = []
    for g in groups:
        links = {rows[i]["source"] for i in g}
        target = next((m for m in merged if links & {rows[i]["source"] for i in m}), None)
        if target is None:
            merged.append(list(g))
        else:
            target.extend(g)
    return merged


def word_count(s: str) -> int:
    return len(s.split())


def run_pipeline(emails: list, profile: dict, provider) -> dict:
    approved = set(profile["approved_senders"])
    weights = profile["weights"]
    max_cards = profile["mode"]["max_cards"]
    rows: dict = {}
    candidates: list = []

    for e in emails:
        row = {"id": e["id"], "outcome": None, "flags": [], "label": None, "topic": None,
               "headline": "", "why_it_matters": "", "score": None, "source": None,
               "grounding": None, "summary_unavailable": False, "merged_into": None, "plus_sources": 0}
        rows[e["id"]] = row

        # B2: unapproved sender. Content is never sent to the model.
        if e["sender"] not in approved:
            row.update(outcome="flagged", flags=["unapproved_sender"])
            continue

        # B1 / B3: separate screen call, flags only.
        s = provider.screen(e)
        flags = [f for f, on in (("financial", s.get("financial")), ("injection", s.get("embedded_instructions"))) if on]
        if flags:
            row.update(outcome="flagged", flags=flags)
            continue

        if not e.get("links"):
            row.update(outcome="dropped", flags=["no_source"])
            continue

        t = provider.triage(e)
        problem = grounding_problem(t, e["body"]) if t["label"] in ("relevant", "unsure") else None
        retried = False
        if problem:
            retried = True
            t = provider.triage(e, feedback=problem)
            problem = grounding_problem(t, e["body"]) if t["label"] in ("relevant", "unsure") else None

        row.update(label=t["label"], topic=t.get("topic"), source=e["links"][0])
        if t["label"] in ("noise", "irrelevant"):
            row["outcome"] = "filtered"
            continue

        if problem:  # PRD: retry once, then "Summary unavailable", never invent
            row.update(summary_unavailable=True, headline="Summary unavailable, read source",
                       why_it_matters="", grounding="failed_after_retry")
        else:
            row.update(headline=t["headline"], why_it_matters=t["why_it_matters"],
                       grounding="passed_after_retry" if retried else "passed")
        row["key_claim"] = t.get("key_claim", "")
        row["score"] = round(float(t.get("confidence", 0)) * weights.get(t.get("topic") or "", 1.0), 3)

        if t["label"] == "unsure":
            row["outcome"] = "unsure"
        else:
            candidates.append(row)

    # Dedup across relevant cards
    groups = provider.group_stories([
        {"id": r["id"], "headline": r["headline"], "key_claim": r.get("key_claim", "")} for r in candidates
    ]) if candidates else []
    groups = merge_shared_links(groups, rows)
    primaries = []
    for g in groups:
        members = sorted((rows[i] for i in g), key=lambda r: -(r["score"] or 0))
        lead = members[0]
        lead["plus_sources"] = len(members) - 1
        primaries.append(lead)
        for m in members[1:]:
            m.update(outcome="merged", merged_into=lead["id"])

    # Rank and cap. Never pad.
    primaries.sort(key=lambda r: -(r["score"] or 0))
    for i, r in enumerate(primaries):
        r["outcome"] = "card" if i < max_cards else "over_cap"

    out = [rows[e["id"]] for e in emails]
    for r in out:
        r.pop("key_claim", None)
    counts = {o: sum(r["outcome"] == o for r in out) for o in OUTCOMES}
    shown = counts["card"]
    banner = f"Only {shown} relevant items this run" if shown < 8 else f"Showing top {shown}"
    return {"rows": out, "counts": counts, "banner": banner, "groups": groups}
