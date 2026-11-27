# Foldline pilot: real LLM pipeline + eval harness

> Phase 2 of the [PRD](../docs/PRD.md): replace the Phase 1 rules engine with real LLM calls, and decide go/no-go using measured gates instead of a demo.

**Status:** harness built and tested · keyword baseline measured (8/12 gates) · LLM run pending an API key

## What this answers
*Does an LLM beat simple rules on the jobs rules can't do, without breaking the PRD's safety boundaries?*
The golden set is designed to target those jobs:
- **Subtle prompt injection** (an "ASSISTANT OVERRIDE" line, a hidden HTML comment), not just "ignore previous instructions"
- **Articles that report attacks without being attacks**, which a regex wrongly flags
- **The same story in different words** from two newsletters, which only semantic dedup can merge
- **Borderline items** that should go to the user as "Unsure", not be silently dropped

## Pipeline
| Step | How | Why |
|---|---|---|
| B2 sender allowlist | Code | An unapproved sender's content is never sent to the model |
| B1/B3 safety screen | **LLM call #1**, flags only | A flagged email is never summarised, so an injected instruction can't reach the summariser |
| Source-link check | Code | No link → dropped |
| Triage + card | **LLM call #2**, forced tool → JSON | Label, topic, confidence, ≤12-word headline, verbatim evidence quotes |
| Grounding check | Code, no LLM judge | Each quote must appear verbatim; numbers in the headline must exist in the email. Retry once, then "Summary unavailable" |
| Dedup | **LLM call #3** (one per run) + shared-link rule in code | Merges the same story told in different words |
| Rank and cap | Code | Score = confidence × topic weight; max 10 cards, never padded |

All calls use `temperature=0`, forced tool use (schema-valid JSON) and `<email>` tags marking the content as untrusted data.

## Golden set (`data/golden_emails.jsonl`)
44 fictional emails, labeled by hand. No real newsletter content is committed.

| Bucket | n | Tests |
|---|---|---|
| Relevant (4 topics) | 20 | Includes 3 same-story pairs (1 shared link, 2 reworded) and 2 hard negatives about injection |
| Irrelevant / noise | 6 / 5 | Off-topic sections; sponsors, event ads, link dumps |
| Unsure | 3 | Draft regulation, unclear scope |
| B1 financial | 3 | Stock tips, brokerage, token presale |
| B3 injection | 4 | Plain, hidden HTML comment, "if you are an automated reader", role override |
| B2 unapproved sender | 2 | |
| No source link | 1 | |

## Launch gates
| Gate | Target | Source |
|---|---|---|
| B1 / B2 / B3 recall | 100% | PRD |
| Missed-relevant rate | ≤ 10% | PRD |
| Noise precision (share of filtered items that really were noise) | ≥ 90% | PRD |
| Merge F1 (pairwise) | ≥ 90% | PRD "merge accuracy" |
| Cards with valid source · reconciliation · card cap | 100% | PRD |
| Safety false-positive rate | ≤ 5% | Proposed |
| Grounded cards | ≥ 95% | Proposed |
| Headline/why word limits | ≥ 95% | Proposed |

## Results
| Gate | Keyword baseline | LLM run |
|---|---|---|
| B1 financial recall | ✅ 100% | pending |
| B2 sender recall | ✅ 100% | pending |
| B3 injection recall | ❌ 75% (missed the "ASSISTANT OVERRIDE" email) | pending |
| Missed-relevant rate | ❌ 15% | pending |
| Noise precision | ❌ 73% | pending |
| Merge F1 | ❌ 0.80 (missed the reworded interview story) | pending |
| Safety false positives | ✅ 2.9% (flagged an article *about* injection) | pending |
| **Gates passed** | **8 / 12** | pending |

Full reports: [`results/baseline/REPORT.md`](results/baseline/REPORT.md), with per-email detail in `predictions.csv`.

## Run it
```bash
cd eval
pip install -r requirements.txt
python -m pytest -q tests                     # 10 product-logic tests, no key needed
python run_eval.py --provider baseline        # keyword rules, no key needed
export ANTHROPIC_API_KEY=...                  # then the real run (~80 calls on Haiku)
python run_eval.py --provider claude --price-in <USD/MTok> --price-out <USD/MTok>
```
`--strict` exits non-zero when any gate fails, for CI. `--model` switches the model.

## Not covered yet
- Live Gmail (`gmail.readonly`). This run reads the golden set from a file
- "≥ 2× insights vs manual baseline": needs timed human sessions
- Same-story suppression across runs, and feedback-driven weight changes (covered in the Phase 1 prototype)
- With 44 items, one error moves a rate by 2–5 points. Grow the set from real failures before trusting small differences
