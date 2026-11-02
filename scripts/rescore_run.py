#!/usr/bin/env python3
"""Re-read saved output with the unmodified official evaluator; no model call."""
import argparse
import csv
import json
import os
from pathlib import Path
from reaudit.config import ROOT, load_config, runtime_environment

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("run_id")
    a = p.parse_args()
    rows = list(csv.DictReader((ROOT / "runs/runs.csv").open()))
    row = next(r for r in rows if r["run_id"] == a.run_id)
    c = load_config(ROOT / row["trace_path"] / "config.json")
    os.environ.update(runtime_environment(c))
    from appworld.evaluator import evaluate_task
    tracker = evaluate_task(task_id=row["task_id"], experiment_name=row["run_id"],
                            suppress_errors=True, save_report=False)
    old = json.loads((ROOT / row["trace_path"] / "evaluation.json").read_text())
    result = {"run_id": a.run_id, "score": int(tracker.success),
              "saved_score": int(old["success"]), "matches": tracker.success == old["success"],
              "model_calls": 0}
    path = ROOT / row["trace_path"] / "rescore.json"
    path.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    if not result["matches"]:
        raise SystemExit("Official re-score differs.")
