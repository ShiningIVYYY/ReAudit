#!/usr/bin/env python3
import csv
import hashlib
import json
import os
import random
import re
from reaudit.config import ROOT, load_config, runtime_environment

if __name__ == "__main__":
    c = load_config()
    os.environ.update(runtime_environment(c))
    from appworld import load_task_ids
    from appworld.task import Task, task_id_to_generator_id
    selection = c["task_selection"]
    task_ids = sorted(load_task_ids("train"))
    selected = random.Random(selection["seed"]).sample(task_ids, selection["count"])
    rows = []
    for index, task_id in enumerate(selected):
        task = Task.load(task_id, load_ground_truth=False)
        apps = [app for app in task.allowed_apps if app not in ("supervisor", "api_docs")]
        rows.append({
            "selection_order": index + 1, "task_id": task_id,
            "scene_id": task_id_to_generator_id(task_id), "split": "train",
            "selection_seed": selection["seed"], "selection_method": selection["method"],
            "allowed_apps": json.dumps(apps), "instruction_app_mentions": json.dumps(
                [app for app in apps if re.search(r"\b" + re.escape(app.replace("_", " ")) + r"\b", task.instruction, re.I)]), "instruction_sha256":
            hashlib.sha256(task.instruction.encode()).hexdigest()})
        task.close()
    apps = {a for r in rows for a in json.loads(r["instruction_app_mentions"])}
    if len(apps) < selection["minimum_distinct_apps"]:
        raise RuntimeError("Fixed sample does not meet app coverage; do not silently resample.")
    path = ROOT / "data/task_manifest.csv"
    if path.exists():
        raise SystemExit("Manifest already exists; refusing to silently replace selection.")
    with path.open("w") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({"tasks": rows, "distinct_allowed_apps": sorted(apps)}, indent=2))
