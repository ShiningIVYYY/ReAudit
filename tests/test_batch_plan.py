import copy
import csv
from reaudit.batch import experiment_signature, plan_runs
from reaudit.config import ROOT, load_config


def tasks():
    return [r["task_id"] for r in csv.DictReader((ROOT / "data/task_manifest.csv").open())]


def test_failed_trial_is_reused_without_retry_or_double_cost():
    config = load_config()
    first = tasks()[0]
    row = {"run_id": "existing_failed_trial", "task_id": first,
           "repeat_index": "0", "sampling_seed": str(config["experiment"]["sampling_seeds"][0]),
           "status": "error", "failure_type": "context_overflow"}
    plan = plan_runs(config, tasks(), [row], lambda _: config)
    assert len(plan) == 16
    assert sum(p["existing_run_id"] is None for p in plan) == 15
    assert plan[0]["existing_run_id"] == "existing_failed_trial"


def test_different_agent_results_are_not_mixed_into_baseline():
    config = load_config()
    old = copy.deepcopy(config)
    old["agent"]["implementation"] = "different_official_implementation"
    row = {"run_id": "old_trial", "task_id": tasks()[0],
           "repeat_index": "0", "sampling_seed": str(config["experiment"]["sampling_seeds"][0])}
    assert all(p["existing_run_id"] is None
               for p in plan_runs(config, tasks(), [row], lambda _: old))


def test_timeout_check_not_mixed_into_baseline():
    config = load_config()
    changed = copy.deepcopy(config)
    changed["agent"]["run_timeout_seconds"] = 0.05
    assert experiment_signature(config) != experiment_signature(changed)


def test_gpu_assignment_only_does_not_change_agent_signature():
    config = load_config()
    changed = copy.deepcopy(config)
    changed["inference"]["gpu_indices"] = [0]
    changed["inference"]["gpu_uuids"] = {"0": "another-device"}
    assert experiment_signature(config) == experiment_signature(changed)
