#!/usr/bin/env python3
"""CPU-only validation; these are environment resets, not LLM complete executions."""
import csv
import json
import os
import subprocess
import sys
from reaudit.config import ROOT, load_config, runtime_environment

if __name__ == "__main__":
    c = load_config()
    results = []
    for entry in csv.DictReader((ROOT / "data/task_manifest.csv").open()):
        prints = []
        for repeat in range(c["validation"]["initial_state_repeats"]):
            path = ROOT / "runtime/reset_checks" / entry["task_id"] / str(repeat)
            path.mkdir(parents=True, exist_ok=False)
            code = (
                "from pathlib import Path; from appworld import AppWorld;"
                "from reaudit.snapshot import fingerprint;"
                "from reaudit.config import load_config;"
                f"c=load_config(); w=AppWorld(task_id={entry['task_id']!r},"
                f"experiment_name={'reset_'+entry['task_id']+'_'+str(repeat)!r},"
                "load_ground_truth=False,random_seed=c['agent']['environment_seed'],"
                "timeout_seconds=c['agent']['code_timeout_seconds']);"
                f"print(fingerprint(w,Path({str(path / 'dbs')!r}),c));w.close()")
            p = subprocess.run([sys.executable, "-B", "-c", code],
                               env=runtime_environment(c), capture_output=True, text=True,
                               timeout=c["validation"]["reset_timeout_seconds"])
            if p.returncode:
                (path / "error.log").write_text(p.stdout + p.stderr)
                raise RuntimeError(f"Reset failed for {entry['task_id']}; see {path}")
            prints.append(p.stdout.strip().splitlines()[-1])
        results.append({"task_id": entry["task_id"], "fingerprints": prints,
                        "identical": len(set(prints)) == 1})
        print(json.dumps(results[-1]), flush=True)
    output = ROOT / "reports/evidence/initial_state_checks.json"
    output.write_text(json.dumps(results, indent=2) + "\n")
    if not all(r["identical"] for r in results):
        raise SystemExit("Initial state mismatch.")
