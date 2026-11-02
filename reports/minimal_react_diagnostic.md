# Qwen2.5-7B fixed baseline

Agent: official_minimal_react. Completed 3/16 baseline slots.
Failure rows count as completed executions and are never silently retried.
Official saved-state TGC may be filled after an infrastructure failure; failure_type is preserved.

|task_id|executions|successes|unknown scores|
|---|---:|---:|---:|
|e3d6c94_3|2|0|0|
|229360a_3|1|0|0|
|82e2fac_2|0|0|0|
|b7a9ee9_2|0|0|0|
|afc0fce_2|0|0|0|
|302c169_1|0|0|0|
|e7a10f8_2|0|0|0|
|22cc237_2|0|0|0|

Known-score success rate: 0.0; scores known 3/3.
Failure types: {'context_overflow': 2, 'task_failed': 1}.
Exact token usage available for 1/3 runs. Known token totals (lower bounds where usage is missing): 1802387 prompt / 80491 completion.
Mean exact-usage subset tokens: prompt=728644.0, completion=22621.0. These subset means are not estimates for runs with missing usage.
Mean execution latency: 501.157679160436 seconds. Model loading/idle reservation and posthoc scoring are separate.
Fault-injection execution (excluded from baseline rates): None.

See evidence/qwen25_batch_summary.json and server-local per-run traces.
If performance is very low, it only establishes inadequacy under this fixed agent/config; do not generalize to all agent implementations.
