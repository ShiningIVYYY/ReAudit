#!/usr/bin/env python3
"""One model, serial resume, then one explicit timeout check; no other model starts."""
import argparse
import csv
import fcntl
import json
import os
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from reaudit.batch import (enrich_official_score, ledger, plan_runs, saved_config,
                           write_batch_report, verify_baseline, publish_baseline)
from reaudit.config import ROOT, load_config, runtime_environment
from reaudit.logging import write_json
from reaudit.runner import run_one


def main(args):
    config_path = Path(args.config or ROOT / "config/config.json").resolve()
    config = load_config(config_path)
    tasks = [r["task_id"] for r in csv.DictReader((ROOT / "data/task_manifest.csv").open())]
    plan = plan_runs(config, tasks, ledger(config), saved_config)
    print(json.dumps(plan, indent=2), flush=True)
    if not args.execute:
        return
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
    state_path = ROOT / "runtime/qwen25-batch-status.json"
    started_service = False
    timeout_id = None
    try:
        for slot in plan:
            if slot["existing_run_id"]:
                row = next(r for r in ledger(config) if r["run_id"] == slot["existing_run_id"])
                enrich_official_score(row, config)
        pending = [p for p in plan if not p["existing_run_id"]]
        if pending:
            p = subprocess.run(
                [sys.executable, "-B", "scripts/serve_model.py", "start", "--config", str(config_path)],
                cwd=ROOT, env=runtime_environment(config), capture_output=True, text=True)
            if p.returncode:
                raise RuntimeError(p.stdout + p.stderr)
            started_service = True
            deadline = time.monotonic() + config["inference"]["startup_timeout_seconds"]
            while True:
                try:
                    with urllib.request.urlopen(config["endpoint"]["base_url"] + "/models", timeout=config["monitoring"]["query_timeout_seconds"]):
                        break
                except OSError:
                    if time.monotonic() > deadline:
                        raise TimeoutError("Model service startup timeout.")
                    time.sleep(config["inference"]["readiness_poll_seconds"])
        for slot in plan:
            if slot["existing_run_id"]:
                continue
            if (ROOT / "runtime/pause-qwen25-batch.json").exists():
                write_json(state_path, {"stage": "paused_between_runs", "plan": plan})
                return
            write_json(state_path, {"stage": "running", "current": slot, "plan": plan})
            row = run_one(slot["task_id"], slot["repeat_index"], config_path)
            # run_one persists one row even when model/service/task fails.
            slot["existing_run_id"] = row["run_id"]
            row = enrich_official_score(row, config)
            summary = write_batch_report(config, plan)
            print(json.dumps({"progress": summary["completed_slots"], "total": len(plan),
                              "last_run_id": row["run_id"], "status": row["status"],
                              "failure_type": row["failure_type"], "score": row["score"]}), flush=True)
            if row["failure_type"] in ("environment_error", "service_error"):
                raise RuntimeError("Unexpected infrastructure failure; preserved row, stop to diagnose.")
        # This is an additional controlled exception, not a baseline repeat or a retry.
        fault = json.loads(json.dumps(config))
        fault["agent"]["run_timeout_seconds"] = config["validation"]["fault_timeout_seconds"]
        fault["experiment"]["purpose"] = "fault_injection_timeout"
        fault_path = ROOT / "config/timeout_check.json"
        write_json(fault_path, fault)
        timeout_row = run_one(tasks[0], 0, fault_path)
        timeout_id = timeout_row["run_id"]
        if timeout_row["failure_type"] != "timeout":
            raise RuntimeError("Controlled timeout did not receive failure_type=timeout.")
        summary = write_batch_report(config, plan, timeout_id)
        verify_baseline(config, plan)
        write_json(state_path, {"stage": "finished", "summary": summary, "plan": plan})
    except Exception as error:
        summary = write_batch_report(config, plan, timeout_id)
        write_json(state_path, {"stage": "error", "error": str(error), "summary": summary,
                               "plan": plan})
        raise
    finally:
        if started_service:
            p = subprocess.run(
                [sys.executable, "-B", "scripts/serve_model.py", "stop", "--config", str(config_path)],
                cwd=ROOT, env=runtime_environment(config), capture_output=True, text=True)
            write_json(ROOT / "runtime/qwen25-batch-service-stop.json",
                       {"returncode": p.returncode, "output": p.stdout + p.stderr})
        # Publish summaries even for a stopped/partial batch; never start another model.
        resource = {"service_started_by_this_batch": started_service,
                    "stop_result": {"returncode": p.returncode, "output": p.stdout + p.stderr}
                        if started_service else None}
        if started_service:
            service = json.loads((ROOT / "runtime/vllm-service.json").read_text())
            cleanup_deadline = time.monotonic() + config["validation"]["cleanup_timeout_seconds"]
            while Path(f"/proc/{service['pid']}").exists() and time.monotonic() < cleanup_deadline:
                time.sleep(config["inference"]["readiness_poll_seconds"])
            resource["service_pid_exists_after_stop"] = Path(f"/proc/{service['pid']}").exists()
            gpu = subprocess.run(["nvidia-smi",
                                  "--id=" + ",".join(map(str, config["inference"]["gpu_indices"])),
                                  "--query-gpu=index,uuid,memory.used,utilization.gpu",
                                  "--format=csv"], capture_output=True, text=True)
            resource["gpu_snapshot_after_stop"] = gpu.stdout
            resource["service_launch_unix"] = service["started_unix"]
            resource["cleanup_record_unix"] = time.time()
        write_json(ROOT / "reports/evidence/qwen25_batch_cleanup.json", resource)
        summary = write_batch_report(config, plan, timeout_id)
        milestone = ROOT / "reports/milestone_report.md"
        text = milestone.read_text()
        text += (
            "\n## Qwen2.5 fixed-baseline continuation\n\n"
            + json.dumps(summary, ensure_ascii=False, indent=2) + "\n\n"
            "Original failed executions are retained and counted once by run_id. "
            "Any later official saved-state score fills an unknown score without changing failure_type; "
            "score_enrichment.json is kept in each local trace. Posthoc evaluation cost is separate. "
            "Raw scoring outputs are not exported to git. "
            "No other model or later stage was started automatically.\n")
        milestone.write_text(text)
        current = json.loads(state_path.read_text()) if state_path.exists() else {}
        try:
            current["commit"] = publish_baseline(config)
            current["remote_synced"] = True
        except Exception as publish_error:
            current["publish_error"] = str(publish_error)
            current["remote_synced"] = False
        current["service_cleanup"] = resource
        current["summary"] = summary
        write_json(state_path, current)



if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config")
    parser.add_argument("--execute", action="store_true")
    arguments = parser.parse_args()
    if arguments.execute:
        with (ROOT / "tmp/qwen25-batch.lock").open("a") as batch_lock:
            fcntl.flock(batch_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            main(arguments)
    else:
        main(arguments)
