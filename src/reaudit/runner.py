"""Serial complete-execution supervisor, real timeout, GPU samples and CSV summaries."""
import csv
import fcntl
import json
import os
import signal
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from .config import ROOT, load_config, runtime_environment
from .logging import canonical, read_events, write_json

FIELDS = [
    "run_id", "task_id", "scene_id", "condition", "skill_ids", "skill_versions",
    "removed_skill", "model_id", "decoding_config", "environment_snapshot_fingerprint",
    "full_input_hash", "sampling_seed", "score", "sgc", "prompt_tokens",
    "completion_tokens", "latency_seconds", "gpu_info", "num_steps", "status",
    "failure_type", "timestamp", "execution_mode", "usage_complete",
    "known_prompt_tokens", "known_completion_tokens", "llm_latency_seconds",
    "syntax_error_steps", "repeat_index", "config_sha256", "git_commit", "trace_path",
]


def gpu_samples(config, path, stop):
    indices = ",".join(str(v) for v in config["inference"]["gpu_indices"])
    while not stop.is_set():
        sample = {"timestamp_unix": time.time()}
        try:
            p = subprocess.run(
                ["nvidia-smi", f"--id={indices}",
                 "--query-gpu=index,uuid,name,memory.used,memory.total,utilization.gpu",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=config["monitoring"]["query_timeout_seconds"])
            sample.update(returncode=p.returncode, output=p.stdout, error=p.stderr)
        except subprocess.TimeoutExpired:
            sample["error"] = "GPU query timeout"
        with path.open("a") as f:
            f.write(canonical(sample) + "\n")
        stop.wait(config["monitoring"]["interval_seconds"])


def usage_summary(events):
    starts = {e["call_id"] for e in events if e["event"] == "call_start"}
    ends = {e["call_id"]: e for e in events if e["event"] == "call_end"}
    known_p = sum(v.get("prompt_tokens") or 0 for v in ends.values())
    known_c = sum(v.get("completion_tokens") or 0 for v in ends.values())
    complete = starts == set(ends) and all(
        isinstance(v.get("prompt_tokens"), int) and
        isinstance(v.get("completion_tokens"), int) for v in ends.values())
    return {"prompt_tokens": known_p if complete else None,
            "completion_tokens": known_c if complete else None,
            "known_prompt_tokens": known_p, "known_completion_tokens": known_c,
            "usage_complete": complete,
            "llm_latency_seconds": sum(v["latency_seconds"] for v in ends.values())}


def _run_one(task_id, repeat_index=0, config_path=None):
    from datetime import datetime, timezone
    from .logging import digest
    from .prompts import selected_skills
    config_path = Path(config_path or ROOT / "config/config.json").resolve()
    config = load_config(config_path)
    manifest = list(csv.DictReader((ROOT / "data/task_manifest.csv").open()))
    entry = next((v for v in manifest if v["task_id"] == task_id), None)
    if entry is None:
        raise ValueError("Task is absent from the fixed train manifest.")
    seed = config["experiment"]["sampling_seeds"][repeat_index]
    run_id = datetime.now(timezone.utc).strftime("run_%Y%m%dT%H%M%S_") + uuid.uuid4().hex
    run_dir = ROOT / "runs/traces" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    write_json(run_dir / "config.json", config)
    git_commit = subprocess.check_output(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
    write_json(run_dir / "code_provenance.json", {
        "commit": git_commit,
        "tracked_changes_at_start": subprocess.check_output(
            ["git", "-C", str(ROOT), "diff", "--stat"], text=True),
        "source_hashes": {
            str(p.relative_to(ROOT)): digest(p.read_text())
            for p in sorted((ROOT / "src").rglob("*.py"))}})
    timestamp = datetime.now(timezone.utc).isoformat()
    started = time.monotonic()
    stop = threading.Event()
    monitor = threading.Thread(target=gpu_samples,
                               args=(config, run_dir / "gpu.jsonl", stop), daemon=True)
    monitor.start()
    command = [sys.executable, "-B", "-m", "reaudit.worker", "--config", str(config_path),
               "--run-dir", str(run_dir), "--task-id", task_id,
               "--repeat-index", str(repeat_index)]
    timed_out = False
    with (run_dir / "worker.log").open("w") as log:
        process = subprocess.Popen(command, env=runtime_environment(config), cwd=ROOT,
                                   stdout=log, stderr=subprocess.STDOUT,
                                   start_new_session=True)
        try:
            process.wait(timeout=config["agent"]["run_timeout_seconds"])
        except subprocess.TimeoutExpired:
            timed_out = True
            # Only the process group created by this execution is terminated.
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=config["agent"]["termination_grace_seconds"])
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
    elapsed = time.monotonic() - started
    stop.set()
    monitor.join(timeout=config["monitoring"]["query_timeout_seconds"] + 1)
    progress_file = run_dir / "progress.json"
    result_file = run_dir / "result.json"
    result = json.loads((result_file if result_file.exists() else progress_file).read_text()) \
        if result_file.exists() or progress_file.exists() else {}
    if timed_out:
        result.update(status="error", failure_type="timeout", score=None)
    elif process.returncode or not result_file.exists():
        result.update(status="error", failure_type="environment_error", score=None,
                      error=f"worker exited {process.returncode} without a completed result")
    write_json(run_dir / "supervisor_result.json", result)
    condition = config["experiment"]["condition"]
    active = selected_skills(config["experiment"]["skills"], condition)
    row = dict.fromkeys(FIELDS)
    row.update(result)
    row.update({
        "run_id": run_id, "task_id": task_id, "scene_id": entry["scene_id"],
        "condition": condition["name"], "skill_ids": canonical([s["id"] for s in active]),
        "skill_versions": canonical({s["id"]: s["version"] for s in active}),
        "removed_skill": condition.get("removed_skill"),
        "model_id": config["model"]["model_id"],
        "decoding_config": canonical({**config["decoding"],
                                     **config["endpoint"]["request_extras"]}),
        "sampling_seed": seed, "latency_seconds": elapsed,
        "gpu_info": canonical({**config["inference"], "execution_mode": "serial",
                               "telemetry": str((run_dir / "gpu.jsonl").relative_to(ROOT))}),
        "timestamp": timestamp, "execution_mode": "serial", "repeat_index": repeat_index,
        "config_sha256": digest(canonical(config)), "git_commit": git_commit,
        "trace_path": str(run_dir.relative_to(ROOT)), **usage_summary(read_events(run_dir / "events.jsonl"))})
    row = {key: row.get(key) for key in FIELDS}
    write_json(run_dir / "summary.json", row)
    csv_path = ROOT / config["paths"]["runs_csv"]
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("a+") as output:
        fcntl.flock(output.fileno(), fcntl.LOCK_EX)
        output.seek(0, 2)
        writer = csv.DictWriter(output, fieldnames=FIELDS, lineterminator="\n")
        if output.tell() == 0:
            writer.writeheader()
        writer.writerow(row)
        output.flush()
        os.fsync(output.fileno())
    return row


def run_one(task_id, repeat_index=0, config_path=None):
    with (ROOT / "tmp/execution.lock").open("a") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return _run_one(task_id, repeat_index, config_path)
