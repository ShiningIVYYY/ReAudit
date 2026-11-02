# Third-party source

src/reaudit/official_minimal_agent.py preserves the official AppWorld notebook PROMPT_TEMPLATE assignment and MinimalReactAgent class unchanged. Task is imported only for typing; call_llm is supplied by the adapter in each isolated worker.

Source: https://github.com/stonybrooknlp/appworld/blob/66ad8099e12188ece0d3fe45e661dbc01880813b/notebooks/minimal_agent.ipynb

Copyright 2024 The AppWorld Authors. Apache License 2.0; full license in LICENSE.appworld.

Official full ReAct source is vendored under src/experiments/code/recoma, and its prompt under src/reaudit/official_react_prompt.txt, from the same AppWorld release commit. Recoma 0.0.4 core/search source is vendored from its official PyPI wheel, with only package import entry points adjusted to avoid unused providers whose pinned LiteLLM version is unavailable. Agent/controller/parser/search methods are unchanged; provenance and hashes are in reports/evidence/full_react_provenance.json. Recoma license: LICENSE.recoma.
