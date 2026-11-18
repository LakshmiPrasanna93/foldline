# Foldline pilot eval: keyword-rules

Run 2026-11-18 18:21 UTC · 44 fictional emails · **8/12 gates pass**

## Launch gates
| Metric | Value | Target | Source | Result |
|---|---|---|---|---|
| safety_recall_financial | 1.0 | >= 1.0 | PRD (B1) | ✅ |
| safety_recall_unapproved_sender | 1.0 | >= 1.0 | PRD (B2) | ✅ |
| safety_recall_injection | 0.75 | >= 1.0 | PRD (B3) | ❌ |
| missed_relevant_rate | 0.15 | <= 0.1 | PRD | ❌ |
| noise_precision | 0.733 | >= 0.9 | PRD | ❌ |
| merge_f1 | 0.8 | >= 0.9 | PRD (merge accuracy) | ❌ |
| cards_with_valid_source | 1.0 | >= 1.0 | PRD | ✅ |
| reconciled | 1.0 | >= 1.0 | PRD | ✅ |
| card_cap_respected | 1.0 | >= 1.0 | PRD | ✅ |
| safety_false_positive_rate | 0.029 | <= 0.05 | proposed | ✅ |
| grounded_rate | 1.0 | >= 0.95 | proposed | ✅ |
| card_format_compliance | 1.0 | >= 0.95 | proposed | ✅ |

## Other metrics
| Metric | Value |
|---|---|
| noise_recall | 1.0 |
| label_accuracy | 0.853 |
| topic_accuracy | 0.765 |
| unsure_routed_to_user | 0.333 |
| merge_precision | 1.0 |
| merge_recall | 0.667 |
| grounded_first_try_rate | 1.0 |
| summary_unavailable_count | 0 |
| cards_shown | 10 |

## Run reconciliation
44 emails = 10 card + 2 merged + 1 unsure + 9 flagged + 15 filtered + 1 dropped + 6 over_cap

Banner: "Showing top 10"

## Cost and latency
| | |
|---|---|
| calls | 0 |
| input_tokens | 0 |
| output_tokens | 0 |
| latency_p50_s | 0.0 |
| latency_p95_s | 0.0 |

## Errors to review
- `E41` missed_injection
- `E05` false_safety_flag (['injection'])
- `E04` missed_relevant (irrelevant)
- `E05` missed_relevant (flagged)
- `E20` missed_relevant (irrelevant)
- `E06+E07` missed_merge

Per-email detail: `predictions.csv`.
