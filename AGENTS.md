# MusicChain contributor instructions

Read [project scope](docs/PROJECT_SCOPE.md) and [architecture](docs/ARCHITECTURE.md)
before changing behavior. Keep the application small and its boundaries explicit.

## Architecture and scope

- Use Python and LangChain `create_agent()` for the model/tool loop on LangGraph.
  Consult current official LangChain documentation before adopting new APIs.
- Keep one agent and four business tools. No generic text-to-SQL, Deep Agents,
  subagents, shell/filesystem tools, RAG, custom frontend or deployment infrastructure.
- Customer identity comes from trusted runtime context, never chat or tool arguments.
  Sensitive queries must scope by it. Studio simulates identity; a real adapter
  must authenticate callers and authorize thread/checkpoint access.
- Chinook stays read-only. Support writes go to a separate mock SQLite store,
  require human review through the agent, recheck ownership after review and
  deduplicate retries transactionally. No refunds or external tickets are issued.
- Keep standard message and middleware state. The local Agent Server owns
  checkpointing; standalone tests may inject a checkpointer.
- Preserve the four-call invocation limit and twenty-call thread limit. The run
  counter resets on resume; sensitive tools must validate runtime context again.
- The Python distribution is `chinook-support`, the import package is `agent`,
  and the exported Studio graph is `support`. Historical experiment names and
  artifact paths remain stable for reproducibility.

## File ownership and style

- `app.py` exports the provider-backed graph. `src/agent/agent.py` assembles it;
  `system_prompt.py` owns model instructions; `tools.py` exposes capabilities;
  `context.py` separates trusted identity from validated model-selected inputs;
  `database.py` owns read-only queries; `support_store.py` owns mock case writes.
- Keep `agent/`, `scripts/`, `evals/` and `data/` under `src/`. Tests, docs and
  configuration live at the root. Run developer commands as `python -m scripts.…`
  and `python -m evals.runner` after an editable install.
- Prefer small explicit functions, parameterized SQL and bounded results. Add
  abstractions only for concrete needs; a single customer ID needs no context builder.
- Give every module, function, method and class a purpose/contract docstring,
  including test helpers. Use labeled section dividers for meaningful groups;
  explain intent and failure boundaries without narrating each line.
- Tool docstrings and `SYSTEM_PROMPT` are model-visible behavior. Preserve them
  during documentation-only changes. Do not annotate JSON or vendor data.
- Keep secrets in the gitignored `.env`; never print credential values. Model and
  service configuration are environment-driven.

## Verification and documentation

- Run `.venv/bin/pytest`, `.venv/bin/ruff check .` and
  `.venv/bin/ruff format --check .` after relevant edits.
- Scripted offline models exercise the real graph but do not verify live model
  behavior or hosted ingestion. Claim live checks only with recorded evidence.
- Evaluation support writes use isolated temporary stores. Preserve archived
  experiment ZIPs, manifests, results, source hashes and original counts.
- Keep README a short entry point. Put component details in architecture,
  runnable examples in the walkthrough and results in verification/evaluation.
- Record actual technical friction in `FRICTION_LOG.md`. Keep personal planning,
  presentation scheduling and session history outside the shared repository.
- Update documentation when behavior changes. Distinguish historical checks from
  current capabilities and small regression suites from reliability estimates.

Official starting point: https://docs.langchain.com/use-these-docs
