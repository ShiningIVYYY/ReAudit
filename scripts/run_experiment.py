#!/usr/bin/env python3
import argparse
import json
from reaudit.runner import run_one

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--task-id", required=True)
    p.add_argument("--repeat-index", type=int, default=0)
    p.add_argument("--config")
    a = p.parse_args()
    print(json.dumps(run_one(a.task_id, a.repeat_index, a.config),
                     ensure_ascii=False, indent=2))
