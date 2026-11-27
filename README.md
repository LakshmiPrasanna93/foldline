# Foldline: an AI agent that turns newsletter overload into a 15-minute briefing

> **Role:** Product Manager (problem framing, PRD, agent design, evals, prototype)<br>
> **Status:** Prototype complete · all 17 test cases pass · pilot designed<br>
> **Stack:** LLM (structured JSON) · Gmail (read-only) · Google Sheets (state)

**▶ Try it live:** [lakshmiprasanna93.github.io/foldline/prototype](https://lakshmiprasanna93.github.io/foldline/prototype/) (runs in the browser on fictional sample data)

> **Prototype, not production.** Gmail, the LLM and Google Sheets are simulated by a rules engine. The 17 test cases validate the product logic and safety boundaries; LLM quality is measured in the pilot (section 7).

## TL;DR
- Senior PMs follow ~20 sources but have only 10–20 minutes of reading time.
- Foldline reads the newsletters in one Gmail label. It removes duplicates and noise and flags unsafe content.
- It returns up to 10 source-linked insight cards that fit a 15-minute commute.
- The agent never writes to Gmail. The user makes every keep/drop decision.

## Prototype results
| Group | Cases | Result |
|---|---|---|
| Happy path | 3 (show & save, change topic, feedback changes scores) | ✅ Pass |
| Edge | 6 (merge, seen items, Unsure, no source, Read source, Quick summary) | ✅ Pass |
| Safety boundaries B1–B7 + card limit | 8 | ✅ 100% pass |
| **Total** | **17** | **✅ 17 / 17** |

**Sample-run reconciliation (every email ends in exactly one outcome):**
- **Run 1:** 20 emails = 5 cards + 5 merged + 2 unsure + 3 flagged + 4 filtered + 1 dropped
- **Run 2:** 10 emails = 6 cards + 3 suppressed (seen story) + 1 flagged
- **Feedback effect:** topic A ranked up (1.20), topic B ranked down (0.80) but still shown, and the control topic stayed at neutral (1.00).

## 1. Problem
- **Today's loop:** open Gmail → find newsletters → judge relevance → skim → check for repeats → forward to a self-chat → run out of time.
- **Where it breaks:**
  - Time lost filtering noise
  - The same story covered by several newsletters
  - Saved insights lose their context and source
- **Evidence:** about half of sessions lose the first 2–3 minutes (15–20% of the usable time) to re-scanning.
- **Job to be done:** turn unread newsletters into one short, source-linked briefing of only new, relevant insights.

## 2. User
- Time-poor IC senior PM, with 10–20 minutes of usable reading time on a 15–30 minute commute.
- Each user has their own interest profile. Default topics: LLM evals · PM career · AI agents · Product strategy.

## 3. Why an agent (not a filter)
It's an ongoing, multi-step workflow. The agent has to:
- remember what was seen and where it came from
- compare new items against that history
- learn from feedback (ranking only, never relevance)
- fit the output to the time available

## 4. How it works
| Step | What happens |
|---|---|
| 1. Read | New mail in the `Newsletters` label since the last run; already-seen IDs are skipped |
| 2. Safety screen | Unapproved senders, financial content and embedded instructions are excluded and flagged |
| 3. Dedup | A shared link or 80%+ claim overlap merges items (+N sources); stories already seen are suppressed |
| 4. Classify | Relevant / irrelevant / noise / unsure |
| 5. Rank & size | Score = relevance × topic weight; capped to the reading mode |
| 6. Present → decide → learn | Save · Interested · Not interested · Done · Change topic |

## 5. Key product decisions
| Decision | Why |
|---|---|
| Read-only Gmail, no storage of email bodies | Trust is the product; no send, delete, label or mark-read |
| Feedback changes ranking, never hides topics (weights 0.2–2.0) | Prevents a filter bubble |
| "Unsure" section, where the user decides | Better than silently dropping borderline items |
| Never pad the card count ("Only N relevant items this run") | Honest output beats a full feed |
| Email only in v1; expand after evals pass | Prove value on one source before adding more |

## 6. Human control and safety (B1–B7)
- **B1:** financial content is blocked.
- **B2:** unapproved senders are flagged.
- **B3:** hidden instructions (prompt injection) are screened out before summarising.
- **B4:** no Gmail writes.
- **B5:** nothing is saved without the user.
- **B6:** no content is stored.
- **B7:** Gmail is left unchanged.
- A failed summary is retried once, then shows "Summary unavailable". It is never invented.

## 7. Evaluation plan (pilot)
| Metric | Target |
|---|---|
| Insights per 15-min session vs manual baseline | ≥ 2× |
| Safety boundaries B1–B7 | 100% pass |
| Cards with a working source link and grounded summary | 100% |
| Missed-relevant rate (golden set) | ≤ 10% |
| Noise precision · merge accuracy (golden set) | ≥ 90% |

**Golden set:** 42 items (31 fictional test emails + 11 hand-labelled newsletters, stored as IDs and labels only).

## 8. Rollout
| Phase | Scope | Exit criteria |
|---|---|---|
| 1 · Prototype ✅ | Rules engine with simulated Gmail, LLM and Sheets | All 17 test cases pass (met) |
| 2 · Pilot | Live read-only Gmail; the LLM returns JSON; state in Google Sheets | Golden-set thresholds met; ≥ 2× baseline |
| 3 · Expand | 5-min mode, schedule, second source | Phase 2 exit met |

## 9. Risks and trade-offs
- **Prompt injection in newsletter bodies:** screened before any summarisation.
- **Feedback loop narrowing the briefing:** weights are bounded, and topics are never hidden.
- **Merge threshold too loose or too tight:** measured through merge accuracy.
- **Named limit:** a new fact inside a dismissed repeat is lost. Candidate fix: "Not new / Restore".

## 10. What I'd do next
- Run the pilot and publish the golden-set results here.
- Add a 5-minute mode and scheduled runs.
- Add "Not new", "Restore" and "Wrong summary" feedback.

## Pilot eval (Phase 2, in progress)
Real LLM pipeline (safety screen → triage → grounding check → dedup) scored against a 44-email fictional golden set and the PRD's launch gates. The keyword baseline passes **8/12** gates: it misses a subtle injection, flags an article *about* injection, and can't merge reworded stories. The LLM run is next. See [`eval/`](eval/README.md).

## Repo map
- [`docs/PRD.md`](docs/PRD.md): full PRD
- [`prototype/index.html`](prototype/index.html): interactive prototype (fictional data)
- [`eval/`](eval/README.md): Phase 2 pilot: LLM pipeline, golden set, eval harness, tests

---
**Built by Lakshmi Prasanna** · Senior PM, AI agents and enterprise platforms · [GitHub](https://github.com/LakshmiPrasanna93)
