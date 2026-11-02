#!/usr/bin/env python3
"""Detach-safe cleanup/reporting for ONE already-started smoke run; never starts a run."""
import argparse
import csv
import fcntl
import json
import os
import re
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from reaudit.config import ROOT, load_config, runtime_environment
from reaudit.logging import canonical, digest, read_events, write_json
from reaudit.runner import FIELDS, usage_summary

STATUS = ROOT / "tmp/background_smoke_status.json"


def status(stage, **details):
    write_json(STATUS, {"stage": stage, "timestamp": datetime.now(timezone.utc).isoformat(),
                       **details})


def command(args, config, timeout):
    env = runtime_environment(config)
    env.update(GIT_TERMINAL_PROMPT="0",
               GIT_SSH_COMMAND="ssh -i /home/shn/.ssh/id_ed25519 -o IdentitiesOnly=yes "
                               "-o BatchMode=yes -o StrictHostKeyChecking=yes -o UpdateHostKeys=no")
    p = subprocess.run(args, cwd=ROOT, env=env, capture_output=True, text=True, timeout=timeout)
    return {"command": args, "returncode": p.returncode, "output": p.stdout + p.stderr}


def existing_row(run_id):
    path = ROOT / "runs/runs.csv"
    if not path.exists():
        return None
    rows = [v for v in csv.DictReader(path.open()) if v["run_id"] == run_id]
    if len(rows) > 1:
        raise RuntimeError("Duplicate run_id; refusing to hide duplicate costs.")
    return rows[0] if rows else None


def recover_if_supervisor_lost(run_id, run_dir, config, timed_out):
    """Honest fallback: no fabricated elapsed time if original parent disappeared."""
    result_path = run_dir / "result.json"
    progress_path = run_dir / "progress.json"
    result = json.loads((result_path if result_path.exists() else progress_path).read_text()) \
        if result_path.exists() or progress_path.exists() else {}
    entry = next(v for v in csv.DictReader((ROOT / "data/task_manifest.csv").open())
                 if v["task_id"] == run_id_task(run_dir))
    row = dict.fromkeys(FIELDS)
    row.update(result)
    row.update({
        "run_id": run_id, "task_id": entry["task_id"], "scene_id": entry["scene_id"],
        "condition": config["experiment"]["condition"]["name"],
        "skill_ids": "[]", "skill_versions": "{}", "removed_skill": None,
        "model_id": config["model"]["model_id"],
        "decoding_config": canonical({**config["decoding"],
                                     **config["endpoint"]["request_extras"]}),
        "sampling_seed": config["experiment"]["sampling_seeds"][0],
        "latency_seconds": None,
        "gpu_info": canonical({**config["inference"], "execution_mode": "serial"}),
        "timestamp": datetime.strptime(run_id.split("_")[1], "%Y%m%dT%H%M%S")
                             .replace(tzinfo=timezone.utc).isoformat(),
        "execution_mode": "serial", "repeat_index": 0,
        "config_sha256": digest(canonical(config)),
        "git_commit": json.loads((run_dir / "code_provenance.json").read_text())["commit"],
        "trace_path": str(run_dir.relative_to(ROOT)),
        "status": "error", "failure_type": "timeout" if timed_out else "environment_error",
        **usage_summary(read_events(run_dir / "events.jsonl")),
    })
    row = {key: row.get(key) for key in FIELDS}
    write_json(run_dir / "recovery.json", {
        "reason": "Original execution supervisor ended before persisting CSV.",
        "exact_latency_unknown": True, "underlying_worker_result": result})
    write_json(run_dir / "summary.json", row)
    with (ROOT / "runs/runs.csv").open("a+") as output:
        fcntl.flock(output, fcntl.LOCK_EX)
        output.seek(0, 2)
        writer = csv.DictWriter(output, fieldnames=FIELDS, lineterminator="\n")
        if not output.tell():
            writer.writeheader()
        writer.writerow(row)
        output.flush()
        os.fsync(output.fileno())
    return row


def run_id_task(run_dir):
    events = read_events(run_dir / "events.jsonl")
    for event in events:
        if event["event"] == "initial_state":
            return event["experiment_name"] and json.loads(
                (run_dir / "initial_snapshot.json").read_text())["task_id"]
    raise RuntimeError("No task identity recorded; preserve logs and stop.")


def owned_worker(run_id):
    candidates = []
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            if proc.stat().st_uid != os.getuid():
                continue
            args = (proc / "cmdline").read_bytes().split(b"\0")
            if b"reaudit.worker" in args and any(
                    str(ROOT / "runs/traces" / run_id).encode() == arg for arg in args):
                candidates.append(int(proc.name))
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            pass
    return candidates


def main(run_id):
    global STATUS
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
    if not re.fullmatch(r"run_\d{8}T\d{6}_[a-f0-9]{32}", run_id):
        raise ValueError("Invalid run ID.")
    with (ROOT / "tmp/background-finish.lock").open("a") as once:
        fcntl.flock(once, fcntl.LOCK_EX | fcntl.LOCK_NB)
        run_dir = ROOT / "runs/traces" / run_id
        config = load_config(run_dir / "config.json")
        is_full = config["agent"]["implementation"] == "official_full_react"
        report_file = "full_react_pilot.md" if is_full else "smoke_report.md"
        checks_file = "full_react_pilot_checks.json" if is_full else "smoke_checks.json"
        if is_full:
            STATUS = ROOT / "tmp/background_full_react_pilot_status.json"

        status("monitoring_one_existing_run", run_id=run_id, background_pid=os.getpid())
        start = datetime.strptime(run_id.split("_")[1], "%Y%m%dT%H%M%S") \
            .replace(tzinfo=timezone.utc).timestamp()
        deadline = start + config["agent"]["run_timeout_seconds"]
        final_deadline = deadline + config["agent"]["termination_grace_seconds"] + 60
        timed_out = False
        while True:
            row = existing_row(run_id)
            if row:
                break
            workers = owned_worker(run_id)
            if time.time() > deadline + config["agent"]["termination_grace_seconds"]:
                timed_out = True
                for pid in workers:
                    if os.getpgid(pid) != pid:
                        raise RuntimeError("Worker PGID mismatch; refusing to signal.")
                    os.killpg(pid, signal.SIGTERM)
            with (ROOT / "tmp/execution.lock").open("a") as lock:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    if not owned_worker(run_id):
                        row = existing_row(run_id) or recover_if_supervisor_lost(
                            run_id, run_dir, config, timed_out)
                        break
                except BlockingIOError:
                    pass
            if time.time() > final_deadline:
                raise RuntimeError("Execution supervisor did not finish; no new run started.")
            time.sleep(config["inference"]["readiness_poll_seconds"])
        status("checking_results", run_id=run_id, background_pid=os.getpid())
        # Always release our own model service after the one execution, including failure.
        stopped = command([sys.executable, "-B", "scripts/serve_model.py", "stop"],
                          config, 20)
        write_json(run_dir / "service_stop.json", stopped)
        if stopped["returncode"]:
            raise RuntimeError("Service stop refused: " + stopped["output"])
        evaluation_path = run_dir / "evaluation.json"
        if evaluation_path.exists():
            rescore = command([sys.executable, "-B", "scripts/rescore_run.py", run_id],
                              config, config["validation"]["reset_timeout_seconds"])
            write_json(run_dir / "rescore_command.json", rescore)
        else:
            # Score saved state as a diagnostic; retain the original infrastructure failure.
            code = (
                "import json; from appworld.evaluator import evaluate_task;"
                f"t=evaluate_task(task_id={row['task_id']!r},experiment_name={run_id!r},"
                "suppress_errors=True,save_report=True);print(json.dumps(t.to_dict()))")
            rescore = command([sys.executable, "-B", "-c", code], config,
                              config["validation"]["reset_timeout_seconds"])
            write_json(run_dir / "diagnostic_evaluation_command.json", rescore)
        events = read_events(run_dir / "events.jsonl")
        starts = [e for e in events if e["event"] == "environment_start"]
        calls = [e for e in events if e["event"] == "call_end"]
        complete_usage = usage_summary(events)
        initial = json.loads((ROOT / "reports/evidence/initial_state_checks.json").read_text())
        reset = next(e for e in initial if e["task_id"] == row["task_id"])
        samples = []
        for sample in read_events(run_dir / "gpu.jsonl"):
            if sample.get("returncode") == 0:
                for line in sample["output"].splitlines():
                    parts = [v.strip() for v in line.split(",")]
                    samples.append({"memory_used_mib": int(parts[3]), "gpu_util_percent": int(parts[5])})
        evidence = {
            "run_id": run_id, "row": row,
            "model_calls_started": sum(e["event"] == "call_start" for e in events),
            "model_calls_returned": len(calls),
            "syntax_error_steps": sum(not e["syntax_ok"] for e in starts),
            "full_input_hash_matches": digest((run_dir / "full_input.txt").read_text()) == row["full_input_hash"],
            "initial_state_matches_both_resets": all(
                f == row["environment_snapshot_fingerprint"] for f in reset["fingerprints"]),
            "exact_usage": complete_usage,
            "required_columns_present": all(k in row for k in FIELDS),
            "run_id_unique": True, "rescore_returncode": rescore["returncode"],
            "rescore_summary": {"returncode": rescore["returncode"]},
            "raw_rescore_output_location": str(run_dir.relative_to(ROOT) / ("rescore_command.json" if evaluation_path.exists() else "diagnostic_evaluation_command.json")),
            "model_calls_during_rescore": 0,
            "gpu_memory_peak_mib": max((s["memory_used_mib"] for s in samples), default=None),
            "gpu_samples": len(samples), "service_stop": stopped,
            "trace_path": row["trace_path"],
            "cost_recovery_needed": (run_dir / "recovery.json").exists(),
        }
        write_json(ROOT / "reports/evidence" / checks_file, evidence)
        value = lambda key: row.get(key) if row.get(key) not in ("", None) else "未验证/未知"
        text = [
            "# Qwen2.5-7B single-run smoke", "",
            f"- Agent: {config['agent']['implementation']}; configuration: per-run snapshot.",
            f"- run_id：{run_id}",
            f"- task_id：{row['task_id']}（官方 train，固定清单第一个任务）",
            f"- status：{value('status')}；failure_type：{value('failure_type')}；官方 TGC：{value('score')}；SGC：单次执行不定义。",
            f"- 模型调用：{evidence['model_calls_started']}；环境步骤：{value('num_steps')}；语法错误步骤：{evidence['syntax_error_steps']}。",
            f"- prompt tokens：{value('prompt_tokens')}；completion tokens：{value('completion_tokens')}；usage_complete：{value('usage_complete')}。",
            f"- 已知部分：{complete_usage['known_prompt_tokens']} prompt / {complete_usage['known_completion_tokens']} completion tokens；不把未知部分记成零。",
            f"- 完整执行耗时：{value('latency_seconds')} 秒；LLM 调用耗时合计：{value('llm_latency_seconds')} 秒。",
            f"- GPU：物理卡 {config['inference']['gpu_indices']}，RTX 4090；采样显存峰值 {evidence['gpu_memory_peak_mib']} MiB；串行、单并发。",
            f"- 初始指纹与两次独立 reset 一致：{evidence['initial_state_matches_both_resets']}；完整输入哈希一致：{evidence['full_input_hash_matches']}。",
            f"- 重读官方评分退出码：{rescore['returncode']}；评分过程不调用模型。汇总见 evidence/smoke_checks.json；原始评分明细只保存在 git 忽略的本地轨迹中。",
            "- 当前 agent 配置只试跑这 1 次；旧 minimal 的 3 次单独保留，不混入新版基线；不能由单次试跑估计总体成功率。",
            "- 官方 agent 解析规则保持原文；完整版使用其自带代码块提取，minimal 直接执行原文。没有自定义修复模型输出。",
            "- 模型服务已收到本项目限定的停止信号；需结合 service_stop.json 和进程状态确认释放。",
            f"- 全轨迹：{row['trace_path']}（服务器本地、git 忽略）；小体积结果：runs/runs.csv。",
            "", "后台范围到此结束；没有自动扩大实验规模。下一步等待用户确认。",
        ]
        (ROOT / "reports" / report_file).write_text("\n".join(text) + "\n")
        milestone = ROOT / "reports/milestone_report.md"
        content = milestone.read_text()
        content = content.replace(
            "待单任务试跑返回后更新。当前不能报告成功率或典型成本。",
            f"单次执行已结束：run_id={run_id}，task_id={row['task_id']}，"
            f"status={row['status']}，failure_type={row['failure_type']}，score={value('score')}。"
            "结果和 token/耗时/初始状态/重评分证据见 smoke_report.md 与 evidence/smoke_checks.json。"
            "本次只完成 1 个完整执行，不能估计总体成功率或典型成本。")
        content = content.replace("尚未在此报告生成时开始模型完整执行。",
                                  "单次模型执行现已结束，详见结果。")
        if is_full:
            content += (
                "\n## Approved official full-ReAct pilot\n\n"
                + f"Agent=official_full_react; run_id={run_id}; "
                + f"status={row['status']}; failure_type={row['failure_type']}; score={value('score')}. "
                + "The old minimal queue was stopped at 3 executions on user selection; all original costs/results remain. "
                + "This is a distinct agent signature, not a retry or a continuation of the same 16-run baseline. "
                + "See full_react_pilot.md and evidence/full_react_pilot_checks.json. "
                + "Only one full-ReAct GPU execution was authorized and performed; stop for user confirmation.\n")
        milestone.write_text(content)
        # Scoped staging; runtime/traces/tmp are excluded.
        git_commands = [
            ["git", "add", "scripts/background_finish_smoke.py", "reports/milestone_report.md",
             str(Path("reports") / report_file), str(Path("reports/evidence") / checks_file), "runs/runs.csv"],
            ["git", "status"],
            ["git", "diff", "--cached", "--stat"],
        ]
        git_log = []
        for args in git_commands:
            result = command(args, config, 40)
            git_log.append(result)
            if result["returncode"]:
                raise RuntimeError(result["output"])
        staged = command(["git", "diff", "--cached", "--name-only", "-z"], config, 20)
        for name in filter(None, staged["output"].split("\0")):
            blob = subprocess.check_output(["git", "show", ":" + name], cwd=ROOT)
            if len(blob) > 50 * 1024 * 1024:
                raise RuntimeError("Over 50 MiB staged: " + name)
            if re.search(
                rb"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9]{25,}|"
                rb"github_pat_[A-Za-z0-9_]{40,}|hf_[A-Za-z0-9]{25,}|sk-[A-Za-z0-9_\-]{25,}|"
                rb"https?://[^\s/]+:[^\s/@]+@", blob):
                raise RuntimeError("Possible sensitive staged content: " + name)
        for args in [
            ["git", "commit", "-m", "Record single-task smoke result and detached cleanup"],
            ["git", "push", "-u", "origin", "main"],
        ]:
            result = command(args, config, 55)
            git_log.append(result)
            if result["returncode"]:
                write_json(ROOT / "tmp/background-git-log.json", git_log)
                raise RuntimeError(result["output"])
        head = command(["git", "rev-parse", "HEAD"], config, 20)["output"].strip()
        remote = command(["git", "ls-remote", "origin", "refs/heads/main"], config, 30)
        synced = remote["returncode"] == 0 and remote["output"].split()[0] == head
        write_json(ROOT / "tmp/background-git-log.json", git_log)
        status("finished" if synced else "sync_unverified", run_id=run_id,
               commit=head, remote_synced=synced,
               result_status=row["status"], failure_type=row["failure_type"],
               report=str(Path("reports") / report_file), next_step="Wait for user confirmation.")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--run-id", required=True)
    a = p.parse_args()
    try:
        main(a.run_id)
    except Exception as error:
        status("error", run_id=a.run_id, error=f"{type(error).__name__}: {error}")
        raise
