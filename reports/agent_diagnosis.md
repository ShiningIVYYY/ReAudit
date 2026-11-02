# Agent diagnosis before baseline continuation

The initial Qwen2.5-7B execution used the official minimal-agent notebook at AppWorld release v0.1.3.post1 / commit 66ad8099e12188ece0d3fe45e661dbc01880813b. 36/37 environment steps contained Python syntax errors; the final failure was context_overflow. The original execution, costs and failure are retained.

## Primary source comparison

|Behavior|Official minimal notebook|Official full ReAct|
|---|---|---|
|Model output handling|Pass complete response directly to world.execute|extract_code_format_output extracts fenced Python|
|Partial code fence|No special handling|Official partial_code_regex handling|
|Conversation trimming|None in this example|Official controller trims observations/history; official prompted LM truncates input|
|Default controller character cap|Not applicable|BaseReactController max_output_length=100000 characters|
|Default prompted LM character cap|Not applicable|AppworldPromptedLMModel max_prompt_length=24000 characters|
|Current measured performance|One failed execution|Not measured|

Sources:

- https://github.com/stonybrooknlp/appworld/blob/66ad8099e12188ece0d3fe45e661dbc01880813b/notebooks/minimal_agent.ipynb
- https://github.com/stonybrooknlp/appworld/blob/66ad8099e12188ece0d3fe45e661dbc01880813b/experiments/code/recoma/react_controller.py
- https://github.com/stonybrooknlp/appworld/blob/66ad8099e12188ece0d3fe45e661dbc01880813b/experiments/code/recoma/appworld_prompted_lm.py
- Official optional dependency: recoma==0.0.4, as declared by the released AppWorld package. Its BaseReactController defaults were read from the actual PyPI wheel, not guessed.

The formats and history policies differ. Switching between these agents changes the baseline and must not silently merge their results into one 16-run table. No parser was modified, no history window expanded, and no full-ReAct GPU trial has been performed.

The resume planner compares agent/model/decoding/environment/inference signatures. A failed execution fulfills its original repeat slot; it is not retried or dropped. Results from a different agent signature are not reused. Raw scoring details remain in git-ignored per-run traces. An official score obtained later from saved output may fill a previously unknown score, preserving status/failure_type and a separate zero-model-call enrichment record.

The user has been asked whether to switch official agent implementations. Until a switch is explicitly selected, continuation uses only the previously fixed minimal implementation. The controlled timeout uses a separately saved config and is excluded from baseline statistics by its distinct timeout signature. No other model or later project stage starts automatically.
