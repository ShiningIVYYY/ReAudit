import hashlib
import json
from types import SimpleNamespace
from jinja2 import Environment, meta
from recoma.models.core.generator import LMGenerator
from experiments.code.recoma.react_controller import AppworldReactController
from reaudit.config import ROOT
from reaudit.prompts import build_prompt


def test_full_controller_and_framework_methods_unchanged():
    provenance = json.loads((ROOT / "reports/evidence/full_react_provenance.json").read_text())
    for item in provenance["files"]:
        if item["unchanged"]:
            assert hashlib.sha256((ROOT / item["path"]).read_bytes()).hexdigest() == item["sha256"]


def test_official_parser_extracts_only_first_python_block():
    controller = AppworldReactController(action_model="action", observation_model="env")
    fence = chr(96) * 3
    raw = f"Reasoning.\n{fence}python\nprint(1)\n{fence}\nMore text.\n{fence}python\nprint(2)\n{fence}"
    node = SimpleNamespace(output=raw)
    assert controller.extract_code_format_output(node) == "print(1)"
    assert node.output == f"Reasoning.\n{fence}python\nprint(1)\n{fence}"


def test_no_code_is_not_silently_repaired():
    controller = AppworldReactController(action_model="action", observation_model="env")
    node = SimpleNamespace(output="I cannot produce code.")
    assert controller.extract_code_format_output(node) is None


def test_full_prompt_has_no_ground_truth_fields():
    template = (ROOT / "src/reaudit/official_react_prompt.txt").read_text()
    names = meta.find_undeclared_variables(Environment().parse(template))
    assert names == {"main_user", "app_descriptions", "input_str"}
    task = SimpleNamespace(instruction="List my playlists.",
        supervisor={"first_name":"Example","last_name":"User","email":"example@example.com","phone_number":"0000000000"},
        app_descriptions={"spotify":"Music"})
    text = build_prompt(task, [], {"name":"no_skill","agent_implementation":"official_full_react","action_prefix":""})
    messages = LMGenerator().extract_role_messages(text)
    assert messages[-1]["content"].endswith("Task: List my playlists.\n\n")
    assert "ground_truth" not in text and "gold_answer" not in text
