"""Run the Foldline pilot eval.

  python run_eval.py --provider baseline            # no key needed
  python run_eval.py --provider claude              # needs ANTHROPIC_API_KEY
  python run_eval.py --provider claude --model claude-sonnet-5-5 --price-in 3 --price-out 15

Writes results/<provider>/{results.json, predictions.csv, REPORT.md}.
Exit code 1 if any gate fails and --strict is set (use in CI).
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from foldline_eval.metrics import score_run  # noqa: E402
from foldline_eval.pipeline import run_pipeline  # noqa: E402
from foldline_eval.providers import make_provider  # noqa: E402


def load(data_dir: Path):
    profile = json.loads((data_dir / "profile.json").read_text())
    emails = [json.loads(l) for l in (data_dir / "golden_emails.jsonl").read_text().splitlines() if l.strip()]
    return profile, emails


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", choices=["baseline", "claude"], default="baseline")
    ap.add_argument("--model", default="claude-haiku-5-5")
    ap.add_argument("--data", default=str(HERE / "data"))
    ap.add_argument("--out", default=str(HERE / "results"))
    ap.add_argument("--price-in", type=float, help="USD per million input tokens (optional)")
    ap.add_argument("--price-out", type=float, help="USD per million output tokens (optional)")
    ap.add_argument("--strict", action="store_true")
    a = ap.parse_args(argv)

    profile, emails = load(Path(a.data))
    provider = make_provider(a.provider, profile, a.model)
    run = run_pipeline([{k: v for k, v in e.items() if k != "gold"} for e in emails], profile, provider)
    scored = score_run(emails, run, profile)
    usage = provider.usage.as_dict()
    if a.price_in is not None and a.price_out is not None:
        usage["est_cost_usd"] = round(usage["input_tokens"] / 1e6 * a.price_in + usage["output_tokens"] / 1e6 * a.price_out, 4)

    meta = {
        "provider": a.provider,
        "model": a.model if a.provider == "claude" else "keyword-rules",
        "run_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "emails": len(emails),
    }
    out_dir = Path(a.out) / a.provider
    out_dir.mkdir(parents=True, exist_ok=True)
    result = {"meta": meta, "usage": usage, "counts": run["counts"], "banner": run["banner"], **scored, "rows": run["rows"]}
    (out_dir / "results.json").write_text(json.dumps(result, indent=2))
    write_predictions(out_dir / "predictions.csv", emails, run["rows"])
    (out_dir / "REPORT.md").write_text(render_report(result))

    passed = sum(g["pass"] for g in scored["gates"])
    print(f"{meta['model']}: {passed}/{len(scored['gates'])} gates pass -> {out_dir / 'REPORT.md'}")
    return 1 if a.strict and passed < len(scored["gates"]) else 0


def write_predictions(path: Path, emails: list, rows: list):
    gold = {e["id"]: e for e in emails}
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "subject", "gold_label", "gold_flags", "gold_story", "outcome", "pred_label",
                    "pred_flags", "pred_topic", "score", "headline", "grounding", "merged_into"])
        for r in rows:
            g = gold[r["id"]]["gold"]
            w.writerow([r["id"], gold[r["id"]]["subject"], g["label"], "|".join(g["flags"]), g["story_id"],
                        r["outcome"], r["label"], "|".join(r["flags"]), r["topic"], r["score"], r["headline"],
                        r["grounding"], r["merged_into"]])


def render_report(res: dict) -> str:
    meta, gates, m = res["meta"], res["gates"], res["metrics"]
    passed = sum(g["pass"] for g in gates)
    lines = [
        f"# Foldline pilot eval: {meta['model']}",
        "",
        f"Run {meta['run_at']} · {meta['emails']} fictional emails · **{passed}/{len(gates)} gates pass**",
        "",
        "## Launch gates",
        "| Metric | Value | Target | Source | Result |",
        "|---|---|---|---|---|",
    ]
    for g in gates:
        lines.append(f"| {g['metric']} | {g['value']} | {g['op']} {g['target']} | {g['source']} | {'✅' if g['pass'] else '❌'} |")
    lines += ["", "## Other metrics", "| Metric | Value |", "|---|---|"]
    gated = {g["metric"] for g in gates}
    lines += [f"| {k} | {v} |" for k, v in m.items() if k not in gated]
    lines += ["", "## Run reconciliation", f"{meta['emails']} emails = " + " + ".join(f"{v} {k}" for k, v in res["counts"].items() if v),
              "", f"Banner: \"{res['banner']}\"", "", "## Cost and latency", "| | |", "|---|---|"]
    lines += [f"| {k} | {v} |" for k, v in res["usage"].items()]
    lines += ["", "## Errors to review"]
    lines += [f"- `{e['id']}` {e['type']}" + (f" ({e['detail']})" if e.get("detail") else "") for e in res["errors"]] or ["- none"]
    lines += ["", "Per-email detail: `predictions.csv`."]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
