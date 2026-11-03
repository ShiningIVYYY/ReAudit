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

## Failure diagnosis

Evidence: evidence/qwen25_failure_diagnostics.json, per-run event journals and worker logs.
All 16 saved-state scores repeat exactly, all initial snapshots match the independent reset checks,
and each task's two initial prompts match byte-for-byte. No service_error, context_overflow,
environment_error or primary parse_error occurred in this full-agent baseline.

There were 311 request starts and 310 returned responses (all HTTP 200); one pilot request was
interrupted by the 600-second watchdog. The maximum reported per-request prompt was 6,865 tokens,
below the configured 32,768-token context. All 297 executed Python blocks were syntactically valid.
This does not establish correct API use: trajectories contain nonexistent API/attribute use,
invalid API arguments and incorrect field access. The pilot repeatedly passed HTTP-style parameters
to the AppWorld API wrapper. These are agent-generated code errors, not a wrapper repair requirement.

Of the 15 normally completed failures, 13 executed supervisor.complete_task but still failed official
TGC. The other two reached the configured 50-model-call budget. Exact official-parser no-code log
messages occurred 11 times in 3 runs; they are intermediate failures, not 11 failed complete runs.
The original parser was not changed.

Configuration limits may contribute. The timeout pilot had 12 returned responses with finish_reason=length
under max_tokens=1024; all returned responses in the other 15 runs stopped normally.
Official 24,000-character prompt-history trimming was observed in 8/16 runs (166 call prompts).
The other 8 runs had no such trimming and also failed. Therefore neither service/context errors,
output truncation nor history trimming alone explains the complete result.

Interpretation: under this fixed full-ReAct configuration and these eight train tasks, Qwen2.5-7B
provides no positive-success baseline and is currently unsuitable for a useful skill-utility study.
Model API-use/planning limitations are the leading explanation supported by the trajectories,
but causality is not isolated from the agent/prompt/budget choices. Larger-model comparison,
budget ablations, an end-to-end successful real-agent control, and full weight-content hashes remain
unverified. Do not generalize 0/16 to all Qwen2.5-7B setups. No failed baseline slot was replaced.
