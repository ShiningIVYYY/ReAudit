import csv
import json
from types import SimpleNamespace
from pathlib import Path

from reaudit import batch
from reaudit.config import ROOT, load_config
from reaudit.runner import FIELDS


def setup_ledger(tmp_path, monkeypatch):
    config = load_config()
    real_tasks = list(csv.DictReader((ROOT / "data/task_manifest.csv").open()))
    trace_path = "runs/traces/mock_score_enrichment"
    trace = tmp_path / trace_path
    trace.mkdir(parents=True)
    (trace / "initial_snapshot.json").write_text(json.dumps({"task_id": real_tasks[0]["task_id"]}))
    (tmp_path / "tmp").mkdir()
    row = dict.fromkeys(FIELDS, "")
    row.update(run_id="mock_score_enrichment", task_id=real_tasks[0]["task_id"],
               trace_path=trace_path, score="", status="error",
               failure_type="context_overflow")
    path = tmp_path / config["paths"]["runs_csv"]
    with path.open("w") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerow(row)
    monkeypatch.setattr(batch, "ROOT", tmp_path)
    monkeypatch.setattr(batch, "runtime_environment", lambda _: {})
    return config, row, path, trace


def test_official_score_enrichment_preserves_failure_and_unique_cost(tmp_path, monkeypatch):
    config, row, path, trace = setup_ledger(tmp_path, monkeypatch)
    monkeypatch.setattr(batch.subprocess, "run", lambda *a, **k: SimpleNamespace(
        returncode=0, stdout=json.dumps({"success": False, "difficulty": 1, "num_tests": 9}),
        stderr=""))
    result = batch.enrich_official_score(row, config)
    stored = list(csv.DictReader(path.open()))
    assert len(stored) == 1
    assert stored[0]["run_id"] == "mock_score_enrichment"
    assert stored[0]["score"] == "0"
    assert result["failure_type"] == stored[0]["failure_type"] == "context_overflow"
    assert result["status"] == stored[0]["status"] == "error"
    evidence = json.loads((trace / "score_enrichment.json").read_text())
    assert evidence["model_calls"] == 0


def test_evaluator_error_does_not_become_false_zero_score(tmp_path, monkeypatch):
    config, row, path, trace = setup_ledger(tmp_path, monkeypatch)
    original = path.read_bytes()
    monkeypatch.setattr(batch.subprocess, "run", lambda *a, **k: SimpleNamespace(
        returncode=1, stdout="", stderr="mock evaluator unavailable"))
    result = batch.enrich_official_score(row, config)
    assert result["score"] == ""
    assert path.read_bytes() == original
    assert result["failure_type"] == "context_overflow"
    evidence = json.loads((trace / "score_enrichment.json").read_text())
    assert evidence["returncode"] == 1 and "error" in evidence
