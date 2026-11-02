import ast
import hashlib
import json
import time
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from freezegun import freeze_time

from reaudit import official_minimal_agent as official
from reaudit.adapter import ExecutionFailure, OpenAIAdapter
from reaudit.config import ROOT, load_config
from reaudit.logging import Journal, monotonic, read_events
from reaudit.prompts import build_prompt, prompt_to_messages
from reaudit.runner import usage_summary


def task():
    return SimpleNamespace(
        instruction="List my playlists.",
        supervisor={"first_name": "Example", "last_name": "User",
                    "email": "example@example.com", "phone_number": "0000000000"})


def test_official_class_and_template_preserved():
    provenance = json.loads((ROOT / "reports/evidence/official_agent_provenance.json").read_text())
    source = (ROOT / "src/reaudit/official_minimal_agent.py").read_text()
    tree = ast.parse(source)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef))
    assignment = next(n for n in tree.body if isinstance(n, ast.Assign))
    assert hashlib.sha256(ast.get_source_segment(source, cls).encode()).hexdigest() == provenance["agent_class_sha256"]
    assert hashlib.sha256(ast.get_source_segment(source, assignment).encode()).hexdigest() == provenance["prompt_assignment_sha256"]


def test_no_skill_input_matches_official_byte_for_byte():
    prompt = build_prompt(task(), [], {"name": "no_skill"})
    assert prompt_to_messages(prompt) == official.MinimalReactAgent(task()).history
    assert build_prompt(task(), [], {"name": "another_logging_condition"}) == prompt


def test_removal_drops_only_selected_skill_text():
    skills = [{"id": "A", "version": "old_unique_version", "text": "Check all pages."},
              {"id": "B", "version": "private_version_marker", "text": "Verify the final result."}]
    both = build_prompt(task(), skills, {"name": "oldA_withB"})
    removed = build_prompt(task(), skills, {"name": "oldA_withoutB", "removed_skill": "B"})
    assert both.replace("\n\nVerify the final result.", "") == removed
    assert "old_unique_version" not in both and "private_version_marker" not in both


def make_adapter(tmp_path, handler):
    config = load_config()
    journal = Journal(tmp_path / "events.jsonl")
    return OpenAIAdapter(config, journal, 123, httpx.MockTransport(handler)), journal.path


def test_exact_usage_and_no_automatic_retry(tmp_path):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={
            "choices": [{"message": {"content": "print(1)"}}],
            "usage": {"prompt_tokens": 31, "completion_tokens": 4}})
    adapter, path = make_adapter(tmp_path, handler)
    assert adapter.complete([{"role": "user", "content": "x"}]) == "print(1)"
    adapter.close()
    summary = usage_summary(read_events(path))
    assert (summary["prompt_tokens"], summary["completion_tokens"]) == (31, 4)
    assert summary["usage_complete"] and len(calls) == 1


@pytest.mark.parametrize("code,body,expected", [
    (400, {"error": {"message": "maximum context length exceeded"}}, "context_overflow"),
    (503, {"error": {"message": "not ready"}}, "service_error"),
    (200, {"choices": []}, "parse_error"),
])
def test_service_failures_are_not_task_failures(tmp_path, code, body, expected):
    adapter, path = make_adapter(tmp_path, lambda _: httpx.Response(code, json=body))
    with pytest.raises(ExecutionFailure) as caught:
        adapter.complete([{"role": "user", "content": "x"}])
    adapter.close()
    assert caught.value.failure_type == expected
    assert not usage_summary(read_events(path))["usage_complete"]


def test_request_timeout_preserves_unknown_usage(tmp_path):
    def handler(request):
        raise httpx.ReadTimeout("mock timeout", request=request)
    adapter, path = make_adapter(tmp_path, handler)
    with pytest.raises(ExecutionFailure) as caught:
        adapter.complete([{"role": "user", "content": "x"}])
    adapter.close()
    assert caught.value.failure_type == "timeout"
    summary = usage_summary(read_events(path))
    assert summary["prompt_tokens"] is None
    assert summary["completion_tokens"] is None


def test_interrupted_call_is_not_counted_as_zero_tokens():
    summary = usage_summary([{"event": "call_start", "call_id": "interrupted"}])
    assert summary["prompt_tokens"] is None and not summary["usage_complete"]


def test_real_clock_survives_task_time_freeze():
    with freeze_time("2020-01-01"):
        before = monotonic()
        time.sleep(0.02)
        assert monotonic() > before
