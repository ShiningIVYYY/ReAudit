"""Resume an approved fixed baseline without retrying or discarding failed runs."""
import csv
import json
import os
import subprocess
import time
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .config import ROOT, load_config, runtime_environment
from .logging import canonical, digest, write_json
from .runner import FIELDS, run_one


def experiment_signature(config):
    """GPU assignment and storage paths may differ; agent/model parameters may not."""
    inference = dict(config["inference"])
    for key in ("gpu_indices", "gpu_uuids", "python", "startup_timeout_seconds",
                "readiness_poll_seconds", "idle_memory_threshold_mib"):
        inference.pop(key, None)
    value = {key: config[key] for key in ("appworld", "model", "agent", "decoding")}
    value["inference"] = inference
    value["condition"] = config["experiment"]["condition"]
    value["skills"] = config["experiment"]["skills"]
    value["endpoint_request_extras"] = config["endpoint"]["request_extras"]
    return digest(canonical(value))


def plan_runs(config, task_ids, rows, config_for_row):
    signature = experiment_signature(config)
    done, ids = {}, set()
    for row in rows:
        if row["run_id"] in ids:
            raise ValueError("Duplicate run_id in execution ledger.")
        ids.add(row["run_id"])
        if row["task_id"] not in task_ids:
            continue
        saved = config_for_row(row)
        if experiment_signature(saved) != signature:
            continue
        index = int(row["repeat_index"])
        if index >= len(config["experiment"]["sampling_seeds"]):
            raise ValueError("Repeat index outside fixed config.")
        if int(row["sampling_seed"]) != config["experiment"]["sampling_seeds"][index]:
            raise ValueError("Recorded seed differs from repeat slot.")
        key = (row["task_id"], index)
        if key in done:
            raise ValueError("Multiple executions for one baseline slot; do not cherry-pick.")
        done[key] = row["run_id"]
    return [{"task_id": task, "repeat_index": index,
             "sampling_seed": seed, "existing_run_id": done.get((task, index))}
            for task in task_ids
            for index, seed in enumerate(config["experiment"]["sampling_seeds"])]


def ledger(config):
    path = ROOT / config["paths"]["runs_csv"]
    return list(csv.DictReader(path.open())) if path.exists() else []


def saved_config(row):
    return load_config(ROOT / row["trace_path"] / "config.json")


def enrich_official_score(row, config):
    """Official evaluation of saved output; preserve the original failure classification."""
    run_dir = ROOT / row["trace_path"]
    if row.get("score") not in (None, ""):
        return row
    if not (run_dir / "initial_snapshot.json").exists():
        # A timeout before world initialization has no saved world to grade.
        return row
    code = (
        "import json;from appworld.evaluator import evaluate_task;"
        f"t=evaluate_task(task_id={row['task_id']!r},experiment_name={row['run_id']!r},"
        "suppress_errors=True,save_report=True);"
        "print(json.dumps(t.to_dict(stats_only=True)))")
    started = time.monotonic()
    process = subprocess.run(
        [os.sys.executable, "-B", "-c", code], cwd=ROOT,
        env=runtime_environment(config), capture_output=True, text=True,
        timeout=config["validation"]["reset_timeout_seconds"])
    # Raw evaluator output is always local and git-ignored.
    write_json(run_dir / "posthoc_evaluation_raw.json", {
        "returncode": process.returncode, "stdout": process.stdout, "stderr": process.stderr})
    evidence = {"run_id": row["run_id"], "model_calls": 0,
                "elapsed_seconds": time.monotonic() - started,
                "original_score": row.get("score"),
                "failure_type_preserved": row["failure_type"],
                "returncode": process.returncode}
    if process.returncode == 0:
        try:
            stats = json.loads(process.stdout.strip().splitlines()[-1])
            evidence["official_summary"] = {
                k: stats[k] for k in ("success", "difficulty", "num_tests")}
            row["score"] = int(stats["success"])
        except (KeyError, ValueError, IndexError):
            evidence["error"] = "Cannot read official summary; score remains unknown."
    else:
        evidence["error"] = "Official evaluator error; raw details stay in local trace."
    write_json(run_dir / "score_enrichment.json", evidence)
    if row.get("score") not in (None, ""):
        path = ROOT / config["paths"]["runs_csv"]
        rows = ledger(config)
        before = path.read_bytes()
        (run_dir / "ledger_before_score_enrichment.csv").write_bytes(before)
        matched = 0
        for stored in rows:
            if stored["run_id"] == row["run_id"]:
                stored["score"] = row["score"]
                matched += 1
        if matched != 1:
            raise ValueError("Cannot uniquely enrich existing execution.")
        temporary = ROOT / "tmp/runs-score-enrichment.csv"
        with temporary.open("w") as output:
            writer = csv.DictWriter(output, fieldnames=FIELDS, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        os.replace(temporary, path)
        # Summaries are derived artifacts; the raw request/response journal is unchanged.
        write_json(run_dir / "summary.after_score_enrichment.json", row)
    return row


def write_batch_report(config, plan, extra_fault_run=None):
    rows = {r["run_id"]: r for r in ledger(config)}
    selected = [rows[p["existing_run_id"]] for p in plan
                if p.get("existing_run_id") in rows]
    unique = {row["run_id"]: row for row in selected}
    if len(unique) != len(selected):
        raise ValueError("Cost deduplication check failed.")
    evaluated = [r for r in selected if r["score"] not in (None, "")]
    successes = sum(int(r["score"]) for r in evaluated)
    failures = Counter(r["failure_type"] or "none" for r in selected)
    exact = [r for r in selected if str(r["usage_complete"]).lower() == "true"]
    result = {
        "model_id": config["model"]["model_id"],
        "agent_id": config["agent"]["implementation"],
        "experiment_signature": experiment_signature(config),
        "planned_slots": len(plan), "completed_slots": len(selected),
        "run_ids": list(unique), "cost_counted_unique_run_ids": len(unique),
        "known_scores": len(evaluated), "unknown_scores": len(selected) - len(evaluated),
        "successes": successes,
        "success_rate_evaluated": successes / len(evaluated) if evaluated else None,
        "confirmed_success_fraction_all_attempts": successes / len(selected) if selected else None,
        "failure_type_counts": dict(failures),
        "exact_usage_runs": len(exact),
        "known_prompt_tokens": sum(int(r["known_prompt_tokens"] or 0) for r in selected),
        "known_completion_tokens": sum(int(r["known_completion_tokens"] or 0) for r in selected),
        "mean_exact_prompt_tokens": sum(int(r["prompt_tokens"]) for r in exact) / len(exact) if exact else None,
        "mean_exact_completion_tokens": sum(int(r["completion_tokens"]) for r in exact) / len(exact) if exact else None,
        "mean_latency_seconds": sum(float(r["latency_seconds"]) for r in selected) / len(selected) if selected else None,
        "fault_injection_run_id": extra_fault_run,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }
    per_task = []
    for task_id in dict.fromkeys(p["task_id"] for p in plan):
        group = [r for r in selected if r["task_id"] == task_id]
        per_task.append({"task_id": task_id, "executions": len(group),
                         "successes": sum(int(r["score"]) for r in group if r["score"] not in (None, "")),
                         "unknown_scores": sum(r["score"] in (None, "") for r in group)})
    result["per_task"] = per_task
    write_json(ROOT / "reports/evidence/qwen25_batch_summary.json", result)
    lines = ["# Qwen2.5-7B fixed baseline", "",
             f"Agent: {result['agent_id']}. Completed {len(selected)}/{len(plan)} baseline slots.",
             "Failure rows count as completed executions and are never silently retried.",
             "Official saved-state TGC may be filled after an infrastructure failure; failure_type is preserved.",
             "", "|task_id|executions|successes|unknown scores|",
             "|---|---:|---:|---:|"]
    for item in per_task:
        lines.append(f"|{item['task_id']}|{item['executions']}|{item['successes']}|{item['unknown_scores']}|")
    lines += ["", f"Known-score success rate: {result['success_rate_evaluated']}; "
              f"scores known {len(evaluated)}/{len(selected)}.",
              f"Failure types: {dict(failures)}.",
              f"Exact token usage available for {len(exact)}/{len(selected)} runs. "
              f"Known token totals (lower bounds where usage is missing): "
              f"{result['known_prompt_tokens']} prompt / {result['known_completion_tokens']} completion.",
              f"Mean exact-usage subset tokens: prompt={result['mean_exact_prompt_tokens']}, "
              f"completion={result['mean_exact_completion_tokens']}. "
              "These subset means are not estimates for runs with missing usage.",
              f"Mean execution latency: {result['mean_latency_seconds']} seconds. "
              "Model loading/idle reservation and posthoc scoring are separate.",
              f"Fault-injection execution (excluded from baseline rates): {extra_fault_run}.",
              "", "See evidence/qwen25_batch_summary.json and server-local per-run traces.",
              "If performance is very low, it only establishes inadequacy under this fixed agent/config; "
              "do not generalize to all agent implementations."]
    (ROOT / "reports/qwen25_baseline.md").write_text("\n".join(lines) + "\n")
    return result


def verify_baseline(config, plan):
    """Read saved output again with official scoring; never send evaluation data to the LLM."""
    rows = {r["run_id"]: r for r in ledger(config)}
    initial = json.loads((ROOT / "reports/evidence/initial_state_checks.json").read_text())
    expected = {r["task_id"]: r["fingerprints"][0] for r in initial}
    checks = []
    for slot in plan:
        run_id = slot.get("existing_run_id")
        if not run_id:
            continue
        row = rows[run_id]
        run_dir = ROOT / row["trace_path"]
        code = (
            "import json;from appworld.evaluator import evaluate_task;"
            f"t=evaluate_task(task_id={row['task_id']!r},experiment_name={run_id!r},"
            "suppress_errors=True,save_report=False);print(json.dumps(t.to_dict(stats_only=True)))")
        replay = subprocess.run(
            [os.sys.executable, "-B", "-c", code], cwd=ROOT,
            env=runtime_environment(config), capture_output=True, text=True,
            timeout=config["validation"]["reset_timeout_seconds"])
        write_json(run_dir / "baseline_rescore_raw.json",
                   {"returncode": replay.returncode, "stdout": replay.stdout,
                    "stderr": replay.stderr, "model_calls": 0})
        stats = {}
        if replay.returncode == 0:
            try:
                stats = json.loads(replay.stdout.strip().splitlines()[-1])
            except (ValueError, IndexError):
                pass
        checks.append({
            "run_id": run_id, "task_id": row["task_id"],
            "snapshot_matches_initial_check":
                row["environment_snapshot_fingerprint"] == expected[row["task_id"]],
            "input_hash_matches_trace":
                digest((run_dir / "full_input.txt").read_text()) == row["full_input_hash"],
            "rescore_returncode": replay.returncode,
            "rescore_tgc": int(stats["success"]) if "success" in stats else None,
            "rescore_matches": str(int(stats["success"])) == str(row["score"])
                if "success" in stats and row["score"] not in ("", None) else None,
        })
    per_task = {}
    for item in checks:
        row = rows[item["run_id"]]
        per_task.setdefault(item["task_id"], []).append(row)
    repeat_hash_checks = [{
        "task_id": task,
        "executions": len(group),
        "same_initial_fingerprint": len({r["environment_snapshot_fingerprint"] for r in group}) == 1,
        "same_initial_prompt_hash": len({r["full_input_hash"] for r in group}) == 1,
    } for task, group in per_task.items()]
    result = {"checks": checks, "repeat_checks": repeat_hash_checks,
              "model_calls": 0,
              "all_snapshot_checks_pass": all(v["snapshot_matches_initial_check"] for v in checks),
              "all_input_hash_checks_pass": all(v["input_hash_matches_trace"] for v in checks),
              "all_known_scores_repeat": all(v["rescore_matches"] is True for v in checks)}
    write_json(ROOT / "reports/evidence/qwen25_batch_validation.json", result)
    return result


def publish_baseline(config):
    """Commit only reviewed summary artifacts, never raw trajectories or evaluator details."""
    import re
    env = runtime_environment(config)
    env.update(GIT_TERMINAL_PROMPT="0",
               GIT_SSH_COMMAND="ssh -i /home/shn/.ssh/id_ed25519 -o IdentitiesOnly=yes "
                               "-o BatchMode=yes -o StrictHostKeyChecking=yes -o UpdateHostKeys=no")
    audit = []
    def git(args, timeout=55):
        p = subprocess.run(["git", *args], cwd=ROOT, env=env, capture_output=True,
                           text=True, timeout=timeout)
        record = {"command": ["git", *args], "returncode": p.returncode,
                  "output": p.stdout + p.stderr}
        audit.append(record)
        if p.returncode:
            write_json(ROOT / "runtime/qwen25-batch-git.json", audit)
            raise RuntimeError(record["output"])
        return p.stdout
    if git(["diff", "--cached", "--name-only"]).strip():
        raise RuntimeError("Existing staged changes; refusing automatic commit.")
    paths = ["runs/runs.csv", "reports/qwen25_baseline.md",
             "reports/evidence/qwen25_batch_summary.json",
             "reports/evidence/qwen25_batch_validation.json",
             "reports/evidence/qwen25_batch_cleanup.json",
             "reports/milestone_report.md", "config/timeout_check.json"]
    present = [p for p in paths if (ROOT / p).exists()]
    git(["add", *present])
    git(["status"])
    git(["diff", "--cached", "--stat"])
    for path in filter(None, git(["diff", "--cached", "--name-only", "-z"]).split("\0")):
        blob = subprocess.check_output(["git", "show", ":" + path], cwd=ROOT)
        if len(blob) > 50 * 1024 * 1024:
            raise RuntimeError("Over 50 MiB staged: " + path)
        if re.search(
            rb"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9]{25,}|"
            rb"github_pat_[A-Za-z0-9_]{40,}|hf_[A-Za-z0-9]{25,}|sk-[A-Za-z0-9_\-]{25,}|"
            rb"https?://[^\s/]+:[^\s/@]+@", blob):
            raise RuntimeError("Possible sensitive staged content: " + path)
        if path.endswith(".json"):
            def check(value):
                if isinstance(value, dict):
                    if any(k in value for k in ("trace", "passes", "private_data",
                                                "ground_truth_answer", "rescore_output")):
                        raise RuntimeError("Raw evaluator data in summary: " + path)
                    for v in value.values():
                        check(v)
                elif isinstance(value, list):
                    for v in value:
                        check(v)
            check(json.loads(blob))
    git(["diff", "--cached", "--check"])
    if git(["diff", "--cached", "--name-only"]).strip():
        git(["commit", "-m", "Record Qwen2.5 baseline outcomes and controlled timeout"])
    git(["push", "-u", "origin", "main"])
    head = git(["rev-parse", "HEAD"]).strip()
    remote = git(["ls-remote", "origin", "refs/heads/main"]).split()[0]
    write_json(ROOT / "runtime/qwen25-batch-git.json", audit)
    if head != remote:
        raise RuntimeError("Local/remote main differ after push.")
    return head
