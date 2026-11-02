#!/usr/bin/env python3
"""Start/status/stop only the model service owned by this project."""
import argparse
import json
import os
import signal
import socket
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse
from reaudit.config import ROOT, load_config, runtime_environment
from reaudit.logging import write_json

STATE = ROOT / "runtime/vllm-service.json"


def start(config):
    if STATE.exists():
        state = json.loads(STATE.read_text())
        if Path(f"/proc/{state['pid']}").exists():
            raise RuntimeError("Recorded service PID still exists; inspect status first.")
    inference = config["inference"]
    for index in inference["gpu_indices"]:
        p = subprocess.run(
            ["nvidia-smi", f"--id={index}",
             "--query-gpu=uuid,name,memory.used,utilization.gpu",
             "--format=csv,noheader,nounits"], check=True, capture_output=True, text=True)
        values = [v.strip() for v in p.stdout.strip().split(",")]
        if values[0] != inference["gpu_uuids"][str(index)]:
            raise RuntimeError("GPU UUID changed.")
        if int(values[2]) > inference["idle_memory_threshold_mib"] or int(values[3]) != 0:
            raise RuntimeError(f"GPU {index} is occupied; no service started.")
    url = urlparse(config["endpoint"]["base_url"])
    with socket.socket() as probe:
        try:
            probe.bind((url.hostname, url.port))
        except OSError as error:
            raise RuntimeError("Configured port is occupied; do not stop its owner.") from error
    model_path = Path(config["model"]["local_path"])
    if not model_path.is_dir():
        raise RuntimeError("Configured offline model snapshot is missing.")
    env = runtime_environment(config)
    env["CUDA_VISIBLE_DEVICES"] = ",".join(map(str, inference["gpu_indices"]))
    command = [
        inference["python"], "-B", "-m", "vllm.entrypoints.openai.api_server",
        "--host", url.hostname, "--port", str(url.port),
        "--model", str(model_path), "--tokenizer", str(model_path),
        "--served-model-name", config["model"]["model_id"],
        "--revision", config["model"]["hf_commit"],
        "--dtype", config["model"]["dtype"],
        "--max-model-len", str(inference["max_model_len"]),
        "--tensor-parallel-size", str(inference["tensor_parallel_size"]),
        "--gpu-memory-utilization", str(inference["gpu_memory_utilization"]),
        "--max-num-seqs", str(inference["max_num_seqs"]),
        "--max-num-batched-tokens", str(inference["max_num_batched_tokens"]),
        "--seed", str(inference["seed"]),
        "--generation-config", inference["generation_config"],
    ]
    if inference["enforce_eager"]:
        command.append("--enforce-eager")
    path = ROOT / "runtime/vllm-service.log"
    with path.open("a") as output:
        process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=output,
                                   stderr=subprocess.STDOUT, start_new_session=True)
    # /proc start ticks prevent accidentally operating on a reused PID.
    ticks = Path(f"/proc/{process.pid}/stat").read_text().split()[21]
    state = {"pid": process.pid, "start_ticks": ticks, "command": command,
             "started_unix": time.time(), "log": str(path.relative_to(ROOT))}
    write_json(STATE, state)
    print(json.dumps(state, indent=2))


def stop(config):
    if not STATE.exists():
        print("No service recorded.")
        return
    state = json.loads(STATE.read_text())
    proc = Path(f"/proc/{state['pid']}")
    if not proc.exists():
        print("Recorded service has exited.")
        return
    if (proc.stat().st_uid != os.getuid() or
            (proc / "stat").read_text().split()[21] != state["start_ticks"] or
            b"vllm.entrypoints.openai.api_server" not in (proc / "cmdline").read_bytes()):
        raise RuntimeError("PID ownership/identity mismatch; refusing to signal.")
    os.killpg(state["pid"], signal.SIGTERM)
    print("Sent SIGTERM only to this project's recorded service process group.")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("action", choices=["start", "status", "stop"])
    p.add_argument("--config")
    a = p.parse_args()
    c = load_config(a.config)
    if a.action == "start":
        start(c)
    elif a.action == "stop":
        stop(c)
    else:
        print(STATE.read_text() if STATE.exists() else "No service recorded.")
