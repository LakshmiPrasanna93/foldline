# PRD: Foldline Brief

| | |
|---|---|
| **Owner** | Lakshmi Prasanna |
| **Status** | Prototype complete (17/17 test cases pass) · pilot designed |
| **Version** | v1 (email-only) |
| **Last updated** | Nov 2026 |

> Template: Problem · Users · Goals & metrics · Scope · Non-goals · Risks & open questions, extended with Solution, Requirements, Human control, Evaluation and Rollout for an agent product. All prototype data is fictional.

---

## Problem
- Senior PMs follow ~20 sources (5–7 email newsletters/Substacks) to stay current on AI agents, LLM evals, product strategy and PM careers.
- Today's loop: open Gmail → find newsletters → open → judge relevance → skim → check for repeats → decide → forward to a self-chat → repeat → run out of time.
- **Where it breaks**
  - Time lost to filtering noise
  - Redundant coverage of the same story across newsletters
  - Saved insights lose context and source in the self-chat
- **Evidence:** about half of sessions lose the first 2–3 min (15–20% of the usable window) re-scanning.

**Job to be done:** turn unread newsletters into one short, source-linked briefing of only new, relevant insights, so the user can decide *Done, Save, Interested* or *Not interested*.

## Users
- **Primary:** time-poor IC senior PM.
  - 10–20 min usable reading time inside a 15–30 min commute.
  - Interest profile is per user, not fixed.
- **Default topics:** A · LLM evaluations, B · PM career, C · AI agents, D · Product strategy.

## Goals & metrics
**North-star:** relevant, non-duplicate, source-linked insights consumed in a fixed 15-minute session.

| Metric | Target |
|---|---|
| Insights per 15-min session vs manual baseline (3 sessions each) | ≥ 2× manual |
| Safety boundaries B1–B7 | 100% pass |
| Cards with a working source link + grounded summary | 100% |
| Missed-relevant rate (golden set) | ≤ 10% |
| Noise precision (golden set) | ≥ 90% |
| Merge accuracy (golden set) | ≥ 90% |
| Same-story suppression | Measured, target 85%+ later |

**Fails regardless:** missed-relevant > 10%, any safety breach (B1–B7), any card without a source.

## Scope
**v1 (in scope)**
- Only the 5–7 newsletters in personal Gmail, `Newsletters` label, `gmail.readonly`.
- Daily run at 6:00 am (user TZ) on mail since the last successful run; prototype uses a *Run now* button.
- Commute mode: 15 min, up to 10 cards, never padded.
- Briefing, Saved, Activity log, Settings tabs + Evaluator mode.

**Expansion criterion:** add a second platform only after email meets eval thresholds and beats the manual 15-min baseline.

## Non-goals
- WhatsApp, Reddit, LinkedIn, YouTube (that step of today's loop stays manual).
- Any Gmail write: send, delete, move, archive, label, unsubscribe, mark read.
- Storing email bodies, subjects, excerpts or personal details.
- Designed but not built in v1: schedule, 5-minute and at-home modes, text-to-speech, freshness windows, catch-up, settings screen, undo, resume, alerts, weekly snapshot.

---

## Solution
**Why an agent:** an ongoing multi-step workflow — remember what was seen and where it came from, compare against history, learn from feedback (ranking only, never relevance), fit output to the time available.

**Pipeline**
1. **Read:** labelled mail since `session_state`; skip IDs in `seen_log`.
2. **Safety screen:** unapproved sender, financial content, embedded instructions → excluded and flagged.
3. **Dedup:** shared link or 80%+ claim overlap with nothing new → merged (+N sources); seen story → suppressed.
4. **Classify:** relevant / irrelevant / noise / unsure.
5. **Freshness:** full design 7 / 21 / 45 days (not built).
6. **Rank & size:** score = relevance × topic weight; cap to mode.
7. **Present → review → decide → learn & log.**

**Observe · Decide · Produce · Check**
- **Observe:** new labelled email, interest profile, `seen_log`, `saved_history`.
- **Decide:** safety first, then dedup, classification, ranking.
- **Produce:** grounded cards, Unsure section, audit rows.
- **Check:** every claim traces to its email; every card has a working source link; no duplicate points; no unsafe content; card count fits mode; every email ends in exactly one outcome.

## Requirements

### Insight card (scannable in 10 s)
| Element | Rule |
|---|---|
| Headline | ≤ 12 words; opens Quick summary |
| Why it matters | ≤ 20 words |
| What's-new tag | New fact / New opinion / New way of use |
| Sources | Read source link + "+N" merged sources |
| Score | Score vs neutral 1.00 (shown from run 2) |
| Actions | Save, Interested, Not interested, Done, Change topic |

- Header shows mode + reconciled counts (every email = exactly one outcome).
- **Unsure (n):** "Safe items, relevance unclear — you decide" → Show as card / Not relevant.
- Fewer than 8 relevant: "Only N relevant items this run".

### Decisions
| Action | Effect |
|---|---|
| Save | Writes to `saved_history` immediately |
| Interested / Not interested | Topic weight ±0.2 (range 0.2–2.0), applies from next run; never hides a topic |
| Done | Permanent; later repeats (message ID, link hash, story ID) hidden and logged "dismissed" |
| Show as card | Adds Unsure item to briefing at once |
| Not relevant | Logged "unsure, rejected by you" |
| Quick summary / Read source | Changes nothing |

**Named limit:** a new fact inside a dismissed repeat is lost.

### Data
| Store | Persistence |
|---|---|
| `seen_log`, `audit_log` | Automatic, 45 days |
| Interest weights, metrics | Automatic |
| `saved_history`, topics, senders, rules | Only on user action |
| `session_state`, `approved_senders`, `golden_set` | Config |
| Bodies, subjects, excerpts, personal details | **Never** |
| Financial / unapproved-sender content | **Never** — content-free flag row only |

**Interest profile fields:** `topic_id`, `name`, `description`, `sub_topics`, `ignore_terms`, `weight` (starts 1.0).

### Stop conditions
| Condition | Behaviour |
|---|---|
| Unclear relevance | Unsure |
| Seen story | Suppressed |
| Grounding fails | Retry once → "Summary unavailable, read source" |
| No source link | Dropped |
| Gmail fails | Run stops; previous briefing stays |
| Financial / unapproved sender / embedded instructions | Excluded, flagged, "content stored: none" |
| Attempted Gmail write | "Stopped: write blocked" |

## Human control
- **Agent may:** classify, merge, suppress, rank, drop — logging every decision.
- **Human approves:** retention (Save), weight changes, every Unsure item, new senders, profile changes.

| ID | Safety boundary |
|---|---|
| B1 | No summarising/storing/acting on financial content |
| B2 | Unapproved senders screened out, content-free log |
| B3 | Embedded instructions never followed |
| B4 | No Gmail writes; attempt stops the run |
| B5 | Nothing retained without Save |
| B6 | No bodies, subjects, excerpts, personal details stored |
| B7 | Gmail state unchanged after every run |

## Evaluation
- **Golden set:** 42 items = 31 fictional test emails + 11 hand-labelled real newsletters (ID, sender, link, labels only).
- **Fictional inputs:** approved senders T1–T3, unapproved T9; 20 emails run 1, 10 run 2, R5 for the card-limit test.

**Expected sample runs**
| Run | Reconciliation |
|---|---|
| Run 1 at run | 20 = 5 cards + 5 merged + 2 unsure + 3 flagged + 4 filtered + 1 dropped |
| Run 1 after review | 20 = 4 cards + 5 merged + 1 dismissed + 1 promoted + 1 rejected + 3 flagged + 4 filtered + 1 dropped |
| Run 2 | 10 = 6 cards + 3 suppressed + 1 flagged |

Run 2 after feedback: Topic A above neutral, B below but never hidden, C unchanged.

**Test set (17 cases) — all pass**
| Group | Cases | Pass rule | Result |
|---|---|---|---|
| Happy path | TC1 insight shown & saved · TC1b change topic then Save · TC2 feedback changes scores | Match expected | ✅ |
| Edge | TC3 merge · TC4 seen items · TC5 Unsure · TC6 no source · TC15 Read source · TC16 Quick summary | Match expected | ✅ |
| Boundary | TC7 B1 financial · TC8 B3 hidden instructions · TC9 B2 unapproved sender · TC10 card limit (7/10/11) · TC11 B4 write attempt · TC12 B5 no Save · TC13 B6 storage · TC14 B7 Gmail unchanged | **100%** | ✅ |

## Rollout
| Phase | What | Exit criteria |
|---|---|---|
| 1 · Prototype ✅ | In-page deterministic rules engine; simulated Gmail, LLM, Sheets | All 17 test cases pass (met) |
| 2 · Pilot | Read-only Gmail, LLM with structured JSON, scoring in code, state in one Google Sheet | Golden-set thresholds met; ≥ 2× manual baseline over 3 sessions |
| 3 · Expand | 5-min mode, schedule, second platform | Phase 2 exit met |

## Risks & open questions
| Risk | Mitigation |
|---|---|
| Prompt injection in newsletter bodies | B3 screen before any summarisation; content never stored |
| Grounding errors / hallucinated summaries | Every claim traced to source; retry once, then "Summary unavailable" |
| Feedback loop narrows the briefing | Weights affect ranking only, bounded 0.2–2.0; topics never hidden |
| Dismissed repeat hides a genuinely new fact | Named limit; candidate for "Not new / Restore" later |
| Merge threshold (80% overlap) too loose or tight | Measured via merge accuracy on golden set |

**Open questions**
- Pass mark for same-story suppression (target 85%+)?
- When to build deferred decisions: Wrong summary, Not new, Split, Restore, Approve sender, Pause agent?
- Freshness windows (7/21/45 days): validate on pilot data?
