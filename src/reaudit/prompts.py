"""Full initial input; skill bookkeeping never enters model-visible text."""
import re
import json
from pathlib import Path
from jinja2 import Template
from .official_minimal_agent import PROMPT_TEMPLATE


def selected_skills(skills, condition):
    condition = condition if isinstance(condition, dict) else {"name": condition}
    loaded = condition.get("loaded_skill_ids")
    versions = condition.get("skill_versions", {})
    removed = condition.get("removed_skill")
    result, seen = [], set()
    for skill in skills:
        key = skill["id"]
        if key == removed or (loaded is not None and key not in loaded):
            continue
        if key in versions and str(skill["version"]) != str(versions[key]):
            continue
        if key in seen:
            raise ValueError(f"Ambiguous skill version for {key}")
        seen.add(key)
        result.append(skill)
    if loaded is not None and set(loaded) - {removed} - seen:
        raise ValueError("A requested skill/version is missing.")
    return result


def build_prompt(task, skills, condition):
    """Return complete UTF-8 role-tagged input, without version metadata."""
    profile = condition.get("agent_implementation") if isinstance(condition, dict) else None
    if profile == "official_full_react":
        template = Path(__file__).with_name("official_react_prompt.txt").read_text()
        prompt = Template(template).render({
            "main_user": task.supervisor,
            "app_descriptions": json.dumps(
                [{"name": k, "description": v} for k, v in task.app_descriptions.items()], indent=1),
            "input_str": task.instruction + "\n\n" + condition.get("action_prefix", "")})
    else:
        prompt = Template(PROMPT_TEMPLATE.lstrip()).render(
            {"supervisor": task.supervisor, "instruction": task.instruction})
    active = selected_skills(skills, condition)
    if active:
        prompt += "\n\nAdditional skills:\n\n" + "\n\n".join(s["text"] for s in active)
    return prompt


def prompt_to_messages(prompt):
    # Same role parsing as the vendored official prompt_messages method.
    messages = []
    last_start = 0
    for match in re.finditer("(USER|ASSISTANT|SYSTEM):\n", prompt):
        last_end = match.span()[0]
        if not messages:
            if last_end != 0:
                raise ValueError(f"Start of prompt has no assigned role: {prompt[:last_end]}")
        else:
            messages[-1]["content"] = prompt[last_start:last_end]
        messages.append({"role": match.group(1).lower(), "content": None})
        last_start = match.span()[1]
    if not messages:
        raise ValueError("Prompt has no assigned role.")
    messages[-1]["content"] = prompt[last_start:]
    return messages
