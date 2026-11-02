"""Instrumentation around the unchanged official full ReAct controller and search."""
import ast
from pathlib import Path
from recoma.models.core.generator import LMGenerator, GenerationOutputs
from recoma.search.search import BestFirstSearch
from experiments.code.recoma.react_controller import AppworldReactController
from experiments.code.recoma.appworld_prompted_lm import AppworldPromptedLMModel
from experiments.code.recoma.appworld_env_models import AppworldEnvironmentModel, AppworldAnswerer, MaximumEnvironmentCalls
from experiments.code.recoma.appworld_reader import AppWorldExample
from experiments.code.recoma.singleton_appworld import SingletonAppWorld
from .adapter import ExecutionFailure
from .logging import digest, write_json
from .prompts import build_prompt, selected_skills

_CONTEXT = None


@LMGenerator.register("reaudit_logged_openai")
class LoggedGenerator(LMGenerator):
    """Only the model backend changes; official role parsing is inherited."""
    def generate(self, input_str, current_state):
        c = _CONTEXT
        c["result"]["num_model_calls"] += 1
        count = c["result"]["num_model_calls"]
        current_state.data["openai.reaudit.calls"] = count
        c["journal"].append("full_prompt", model_call=count, text=input_str, sha256=digest(input_str))
        if count == 1:
            expected = build_prompt(c["world"].task, c["skills"], c["condition"])
            if input_str != expected:
                raise ExecutionFailure("environment_error", "build_prompt differs from official initial input.")
            (c["run_dir"] / "full_input.txt").write_text(input_str)
            c["result"]["full_input_hash"] = digest(input_str)
        try:
            messages = self.extract_role_messages(input_str)
        except (ValueError, TypeError) as error:
            raise ExecutionFailure("parse_error", str(error)) from error
        write_json(c["run_dir"] / "progress.json", c["result"])
        return GenerationOutputs(outputs=[c["adapter"].complete(messages)])


class InstrumentedPromptedLM(AppworldPromptedLMModel):
    """Official history truncation runs before the literal skill-text block."""
    def truncate_input(self, input_str):
        core = super().truncate_input(input_str)
        c = _CONTEXT
        active = selected_skills(c["skills"], c["condition"])
        if active:
            core += "\n\nAdditional skills:\n\n" + "\n\n".join(s["text"] for s in active)
        return core


class InstrumentedEnvironment(AppworldEnvironmentModel):
    """Observe the exact code produced by the unchanged official parser."""
    def generate_output(self, state):
        c = _CONTEXT
        code = state.get_open_node().input_str
        result = c["result"]
        try:
            ast.parse(code)
            result["valid_code_steps"] += 1
            syntax_ok = True
        except SyntaxError:
            result["syntax_error_steps"] += 1
            syntax_ok = False
        result["num_steps"] += 1
        c["journal"].append("environment_start", step=result["num_steps"], code=code, syntax_ok=syntax_ok)
        output = super().generate_output(state)
        c["journal"].append("environment_end", step=result["num_steps"], output=output.outputs[0])
        write_json(c["run_dir"] / "progress.json", result)
        return output


def run_full_react(world, config, adapter, journal, run_dir, result):
    global _CONTEXT
    settings = config["agent"]["full_react"]
    condition = {**config["experiment"]["condition"],
                 "agent_implementation": "official_full_react",
                 "action_prefix": settings["action_prefix"]}
    result["num_model_calls"] = 0
    _CONTEXT = dict(world=world, config=config, adapter=adapter, journal=journal,
                    run_dir=run_dir, result=result,
                    skills=config["experiment"]["skills"], condition=condition)
    SingletonAppWorld(world=world)
    controller = AppworldReactController(
        action_model="action", observation_model="environment",
        max_steps=config["agent"]["max_steps"], add_roles=settings["add_roles"],
        max_output_length=settings["max_history_characters"],
        action_prefix=settings["action_prefix"], obs_prefix=settings["observation_prefix"],
        eoq=settings["end_of_query"], ignore_multiple_calls=settings["ignore_multiple_calls"])
    prompted = InstrumentedPromptedLM(
        prompt_file=str(Path(__file__).with_name("official_react_prompt.txt")),
        generator_params={"type": "reaudit_logged_openai"},
        max_prompt_length=settings["max_prompt_characters"])
    search = BestFirstSearch(
        model_list={"react": controller, "action": prompted, "environment": InstrumentedEnvironment()},
        start_model="react", answerer={"type": "appworld_answerer"},
        stopping_conditions=[
            {"type": "max_env_calls", "max_env_calls": config["agent"]["max_steps"]},
            {"type": "max_llm_calls", "max_llm_calls": config["agent"]["max_steps"]},
            {"type": "max_search_iters", "max_search_iters": settings["max_search_iterations"]},
            {"type": "max_search_depth", "max_search_depth": settings["max_search_depth"]},
        ])
    example = AppWorldExample(task_id=world.task_id, task_description=world.task.instruction, gold_answer="N/A")
    prediction = search.predict(example)
    evaluation = prediction.final_state.data.get("test_tracker")
    if evaluation is not None:
        write_json(run_dir / "evaluation.from_official_answerer.json", evaluation)
    _CONTEXT = None
