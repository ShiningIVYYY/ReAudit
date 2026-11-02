# Qwen2.5-7B fixed baseline

Agent: official_full_react. Completed 16/16 baseline slots.
Failure rows count as completed executions and are never silently retried.
Official saved-state TGC may be filled after an infrastructure failure; failure_type is preserved.

|task_id|executions|successes|unknown scores|
|---|---:|---:|---:|
|e3d6c94_3|2|0|0|
|229360a_3|2|0|0|
|82e2fac_2|2|0|0|
|b7a9ee9_2|2|0|0|
|afc0fce_2|2|0|0|
|302c169_1|2|0|0|
|e7a10f8_2|2|0|0|
|22cc237_2|2|0|0|

Known-score success rate: 0.0; scores known 16/16.
Failure types: {'timeout': 1, 'task_failed': 15}.
Exact token usage available for 15/16 runs. Known token totals (lower bounds where usage is missing): 1524492 prompt / 102126 completion.
Mean exact-usage subset tokens: prompt=84283.46666666666, completion=4649.866666666667. These subset means are not estimates for runs with missing usage.
Mean execution latency: 127.92125538305845 seconds. Model loading/idle reservation and posthoc scoring are separate.
Fault-injection execution (excluded from baseline rates): run_20261102T232619_d1f788291b9e4596983df4b27ec84989.

See evidence/qwen25_batch_summary.json and server-local per-run traces.
If performance is very low, it only establishes inadequacy under this fixed agent/config; do not generalize to all agent implementations.
