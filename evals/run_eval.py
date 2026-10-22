"""Run the eval set through the RUNNING endpoint and print a score you can compare between prompt versions.

    uvicorn main:app                         # terminal 1, with your real provider in .env
    python evals/run_eval.py                 # terminal 2 (core set: 8 calls, ~16 with repairs at worst)
    python evals/run_eval.py --set attacks   # the prompt-injection cases
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://localhost:8000")
    ap.add_argument("--set", choices=["core", "attacks", "all"], default="core")
    ap.add_argument("--pause", type=float, default=3.5, help="seconds between calls (OpenRouter free: 20/minute)")
    args = ap.parse_args()

    spec = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))
    cases = spec["core"] if args.set == "core" else spec["attacks"] if args.set == "attacks" else spec["core"] + spec["attacks"]
    key = spec["key_field"]
    rows, hits, prio_hits, prio_total = [], 0, 0, 0
    with httpx.Client(base_url=args.base_url, timeout=120) as http:
        for i, case in enumerate(cases):
            if i:
                time.sleep(args.pause)
            r = http.post("/triage", json={"text": case["text"]})
            got = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
            ok = r.status_code == 200 and got.get(key) == case["expected"][key]
            hits += ok
            if "priority" in case["expected"] and r.status_code == 200:
                prio_total += 1
                prio_hits += got.get("priority") == case["expected"]["priority"]
            rows.append({"id": case["id"], "kind": case["kind"], "status": r.status_code,
                         "source": r.headers.get("x-triage-source"), "model": r.headers.get("x-triage-model"),
                         "repaired": r.headers.get("x-triage-repaired"),
                         "expected": case["expected"], "got": {k: got.get(k) for k in (key, "priority", "confidence")},
                         "title": got.get("title"), "pass": ok})
            mark = "PASS" if ok else "FAIL"
            print(f"{mark}  {case['id']:<3} {case['kind']:<9} {r.status_code}  expected {case['expected'][key]:<8} "
                  f"got {str(got.get(key) or got.get('error', ''))[:60]}")

    sources = {r["source"] for r in rows}
    models = sorted({r["model"] for r in rows if r["model"]})
    score = f"{hits}/{len(cases)}"
    print(f"\n{key}: {score} ({hits / len(cases):.0%})   priority: {prio_hits}/{prio_total}")
    print("model(s):", ", ".join(models) or "-")
    if sources & {"stub", "fallback", "cache"}:
        print("NOTE: some answers came from stub/fallback/cache, not a fresh model call. Restart the API for a clean run.")
    if any(m.startswith("fake") for m in models):
        print("WARNING: this ran against tools/fake_llm.py (a keyword heuristic). It is NOT a model score.")
    failed = [r["id"] for r in rows if not r["pass"]]
    if failed:
        print("failed:", ", ".join(failed))

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out = HERE / "results" / f"{stamp}-{os.environ.get('TRIAGE_PROMPT', 'triage-v1')}-{args.set}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({"date": stamp, "set": args.set, "score": score, "priority": f"{prio_hits}/{prio_total}", "models": models,
                               "rows": rows}, indent=2), encoding="utf-8")
    print(f"saved {out.relative_to(HERE.parent)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
