# MusicChain support agent — durable project context

The user's take-home brief in `docs/PROJECT_BRIEF.md` is authoritative unless the
user changes it. This is a LangChain Federal Deployed Engineer interview project.
Story: prototype → observable, testable, controlled, production-minded agent.
The workspace and GitHub repository are named `MusicChain`. The Python distribution
remains `chinook-support`, its import package is `agent`, and the Studio graph is
`support`. Historical experiment names and evidence remain unchanged.
Repository: https://github.com/realvivekganta/MusicChain (private, branch `main`).
The workspace rename, GitHub push and fresh-clone installation/database build were
verified on 2026-09-24; 139 tests and Ruff passed in the clean environment. The local
Studio server was restarted from MusicChain and a real purchase request passed.

## Scope and architecture

- Work incrementally. Current scope is **Phase 5 interview presentation and rehearsal**,
  authorized on 2026-09-24. The fictional music store/agent is called **MusicChain**
  in the interview. Preserve existing package, graph and historical experiment names;
  the presentation brand does not require renaming implementation identifiers.
  Purchase support, music discovery and human-reviewed mock support requests are implemented.
  Phase 1 live model, hosted tracing and five Studio scenarios passed on
  2026-09-23; evidence is in `docs/PHASE1_STATUS.md`. Phase 2 also passed 65 offline
  tests, real model/hosted trace checks for all three tools and four Studio discovery
  scenarios on that date; evidence is in `docs/PHASE2_STATUS.md`.
  On 2026-09-24 the user authorized Phase 3 implementation following the outline
  in `docs/PHASE3_PLAN.md`. Keep documentation current as implementation progresses.
  Phase 3 is now verified: 99 offline tests, all six live scenarios and Studio
  approve/reject/edit passed. See `docs/PHASE3_STATUS.md` for trace/case evidence.
  Phase 4 is complete: 136 offline tests, 15 cases repeated twice per experiment,
  preserved baseline 28/30 → candidate 30/30 with identical corrected graders.
  Requested artist variety improved 0/2 → 2/2; optional different_artists selects
  one eligible track per artist in SQL. See docs/PHASE4_STATUS.md for artifacts,
  hosted comparison, calibration-run disclosure and limits. Phase 5 now includes a
  native Google Slides deck and docs/INTERVIEW_DEMO.md; a timed rehearsal remains pending.
  A subsequent end-to-end audit fixed oversized runtime customer IDs: require a
  positive signed-64-bit SQLite integer before model execution. Now 139 offline
  tests pass, six fresh live/hosted-trace checks pass, and five Agent Server API
  scenarios pass. See docs/CODE_AUDIT.md. The 136-test Phase 4 record and archived
  experiments remain historical evidence; do not overwrite them with later counts.
- Use Python and LangChain `create_agent()` as the primary abstraction. Its graph
  runs on LangGraph. Consult current official LangChain docs before new APIs.
- No generic text-to-SQL. The model chooses a business capability; application
  code owns SQL and authorization. Use parameterized SQL and bounded responses.
- Customer identity comes from trusted invocation context, never conversation
  state or a model-controlled tool argument. Every sensitive query scopes by it.
- Studio is a trusted local operator interface with simulated authentication,
  not a customer login system. A real adapter must authenticate callers and
  authorize thread/checkpoint access. Never reuse a thread for another customer.
- Keep state to standard messages and framework middleware state. Let the local
  Agent Server manage persistence; do not install a separate checkpointer there.
- Keep Chinook read-only. Phase 3 support writes go to a separate mock store and
  must require HITL approval before execution, with ownership checked again.
- Middleware must solve a concrete problem: four proposals per invocation, twenty
  per thread (run count resets on resume), and approve/edit/reject before support writes.
- No Deep Agents, subagents, shell/filesystem tools, RAG, custom frontend,
  deployment infrastructure, or extra workflows. Explain Deep Agents later as a
  fit for open-ended planning/context management, not this bounded workflow.

## Current interview preparation

5. MusicChain interview demo flow (~35 minutes plus questions), Google Slides deck,
   presenter notes, fallback evidence and explanation polish. Keep documentation
   current. Do not add product features or claim a rehearsal passed before running it.

## Engineering and verification

- Keep module responsibilities clear: `agent.py` wires the agent together,
  `system_prompt.py` holds model instructions, `tools.py` exposes business
  capabilities, `context.py` defines trusted runtime context and model-selected
  input rules, and `database.py` owns read-only Chinook SQL. Application code lives in
  `src/agent/`; root-level `app.py` is the credential-dependent graph export, while
  `agent.py` can be imported by offline tests.
  `support_store.py` owns separate writable mock cases with fresh ownership checks
  and transactional deduplication. Keep trusted identity and
  model-selected filters in clearly labeled sections of `context.py`; customer
  identity must never become a field of any model-selected query. Use `create_agent()` for the loop.
  Add a context builder only when
  there is real trusted application context to assemble beyond the customer ID.
- Prefer small explicit functions and meaningful authorization tests.
- Give every function, method and class a purpose/contract docstring, including
  test helpers and fixtures. Keep simple tests concise; document inputs, outputs,
  side effects and failures where they need explanation. Avoid line-by-line narration.
- Give every Python module a short purpose docstring and use labeled section
  dividers (`# --- Section name ---`) for meaningful groups. Explain boundaries
  and intent rather than narrating each line. Keep model-visible prompt text
  separate from commentary. Tool docstrings are also model-visible; annotation-only
  reviews must preserve those descriptions and SYSTEM_PROMPT. Use native headings
  in Markdown and comments only
  in configuration formats that support them; do not annotate JSON or vendor data.
- No secrets in version control. `.env` is local only. Never print key values.
- Model selection and credentials are environment-driven.
- Offline tests use a scripted model only to exercise the real graph/tool runtime;
  passing them does not prove live model behavior or hosted trace ingestion.
- Record actual friction and limitations in `FRICTION_LOG.md`. Do not claim live
  Studio or LangSmith verification without evidence.
- Keep README a short starting guide; detailed architecture, data notes and the
  Studio walkthrough belong in `docs/ARCHITECTURE.md`.
- Update README, architecture and scope documentation alongside implementation.
  Keep planned behavior separate from verified capabilities, preserve historical
  phase evidence, and record new verification results and real friction as they occur.
- Group `agent/`, `scripts/`, `evals/` and `data/` under `src/`. Keep tests, documentation,
  `.env` and project configuration at the repository root. Run developer commands
  as `python -m scripts.<command>` or `python -m evals.runner` after installing
  the project in editable mode. Evaluation support writes use isolated temporary
  stores. Keep baseline artifacts; never overwrite historical experiment evidence.
- Run `.venv/bin/pytest` and `.venv/bin/ruff check .` after relevant edits.

Official sources: https://docs.langchain.com/use-these-docs and links in README.
