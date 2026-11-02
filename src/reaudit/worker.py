"""One process owns exactly one freshly initialized world and one complete execution."""
import argparse
import ast
import traceback
from pathlib import Path
from .config import ROOT, load_config, runtime_environment
from .logging import Journal, digest, utc_now, write_json
from .adapter import OpenAIAdapter, ExecutionFailure
from .prompts import build_prompt, prompt_to_messages
from .snapshot import fingerprint


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--repeat-index", type=int, required=True)
    args = parser.parse_args()
    config = load_config(args.config)
    import os
    os.environ.update(runtime_environment(config))
    from appworld import AppWorld, load_task_ids
    from appworld.evaluator import evaluate_task
    from . import official_minimal_agent as official
    if args.task_id not in load_task_ids("train"):
        raise ValueError("Task is not in official train split.")
    run_dir = Path(args.run_dir)
    journal = Journal(run_dir / "events.jsonl", config["endpoint"]["api_key_env"])
    condition = config["experiment"]["condition"]
    skills = config["experiment"]["skills"]
    seed = config["experiment"]["sampling_seeds"][args.repeat_index]
    result = {"status": "error", "failure_type": None, "score": None, "sgc": None,
              "num_steps": 0, "syntax_error_steps": 0, "valid_code_steps": 0,
              "environment_snapshot_fingerprint": None, "full_input_hash": None}
    adapter = None
    experiment_name = run_dir.name
    result["experiment_name"] = experiment_name
    try:
        a = config["agent"]
        world = AppWorld(
            task_id=args.task_id, experiment_name=experiment_name,
            max_interactions=a["max_steps"], random_seed=a["environment_seed"],
            timeout_seconds=a["code_timeout_seconds"],
            load_ground_truth=config["agent"]["implementation"] == "official_full_react")
        with world:
            result["environment_snapshot_fingerprint"] = fingerprint(
                world, run_dir / "initial_dbs", config)
            if config["agent"]["implementation"] == "official_full_react":
                from .full_react import run_full_react
                adapter = OpenAIAdapter(config, journal, seed)
                journal.append("initial_state", **result)
                run_full_react(world, config, adapter, journal, run_dir, result)
            else:
                full_input = build_prompt(world.task, skills, condition)
                (run_dir / "full_input.txt").write_text(full_input)
                result["full_input_hash"] = digest(full_input)
                write_json(run_dir / "progress.json", result)
                adapter = OpenAIAdapter(config, journal, seed)
                official.call_llm = adapter.complete

                class Agent(official.MinimalReactAgent):
                    def prompt_messages(self):
                        return prompt_to_messages(build_prompt(self.task, skills, condition))

                agent = Agent(world.task)
                journal.append("initial_state", **result)
                output = None
                for step in range(a["max_steps"]):
                    code = agent.next_code_block(output)
                    # Observe Python syntax; pass the original output to world.execute unchanged.
                    try:
                        ast.parse(code)
                        result["valid_code_steps"] += 1
                        syntax_ok = True
                    except SyntaxError:
                        result["syntax_error_steps"] += 1
                        syntax_ok = False
                    result["num_steps"] += 1
                    journal.append("environment_start", step=step + 1, code=code,
                                   syntax_ok=syntax_ok)
                    output = world.execute(code)
                    journal.append("environment_end", step=step + 1, output=output)
                    write_json(run_dir / "progress.json", result)
                    if world.task_completed():
                        break
        # Official evaluator reloads the on-disk output; no ground truth in agent process input.
        tracker = evaluate_task(task_id=args.task_id, experiment_name=experiment_name,
                                suppress_errors=True, save_report=True)
        evaluation = tracker.to_dict(stats_only=False)
        write_json(run_dir / "evaluation.json", evaluation)
        result["score"] = int(tracker.success)
        if tracker.success:
            result.update(status="completed", failure_type=None)
        elif result["num_steps"] and result["valid_code_steps"] == 0:
            result.update(status="error", failure_type="parse_error")
        else:
            result.update(status="completed", failure_type="task_failed")
        journal.append("official_evaluation", evaluation=evaluation)
    except ExecutionFailure as error:
        result.update(status="error", failure_type=error.failure_type, error=str(error))
        journal.append("failure", failure_type=error.failure_type, detail=str(error))
    except Exception as error:
        result.update(status="error", failure_type="environment_error",
                      error=f"{type(error).__name__}: {error}")
        journal.append("failure", failure_type="environment_error",
                       detail=str(error), traceback=traceback.format_exc())
    finally:
        if adapter:
            adapter.close()
        result["finished_at"] = utc_now()
        write_json(run_dir / "result.json", result)
    return 0


if __name__ == "__main__":
    main()
