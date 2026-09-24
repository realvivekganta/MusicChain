# Friction log

## 2026-09-24 — End-to-end audit

- An oversized trusted customer ID (`2**63`) passed the original positive-integer
  check and then raised `OverflowError` when bound to SQLite. No data escaped its
  scope. Restricted runtime IDs to positive signed-64-bit integers, matching the
  database, and added coverage for the upper boundary and rejection before model
  execution. The suite now has 139 passing tests.
- The initial audit live check could not resolve provider/trace hosts from the
  restricted tool sandbox. After allowing network access, all six live smoke
  scenarios and hosted-trace checks passed. This was an execution-environment
  restriction, not an application/provider outage.
- Five additional Agent Server API scenarios passed against the local Studio
  backend. These verify the server contract, not a fresh browser UI walkthrough.
  See [the audit record](docs/CODE_AUDIT.md) for evidence and boundaries.

## 2026-09-23 — Phase 1

| Observation | Resolution / interview implication |
| --- | --- |
| Repository was empty; shell Python was 3.14, and `uv` was absent. | Used the available Python 3.12 interpreter and a local pip virtual environment. No global installation. Recorded resolved versions. |
| Shell network access and binding a localhost server were sandbox-restricted. | Requested scoped approval for source/dependency downloads and local server verification. These are environment constraints, not LangChain defects. |
| Some official documentation routes intermittently failed through the web reader. | Used official Markdown endpoints and inspected the installed supported API signatures as additional confirmation. |
| A strict custom Pydantic `args_schema` without a runtime field rejected the runtime injected by ToolNode. The user-visible error was vague. | Full-graph tests caught seven failures that pure SQL tests missed. Switched to the documented signature-inferred `@tool` schema with `ToolRuntime` and constrained annotations; all graph tests pass. |
| Current Chinook 1.4.5 dates differ from older copies; invoice 98 is two video items, not music. | Inspect and pin the actual source. Do not memorize older demo dates or assume every Track is music. Purchase support returns real data; future discovery must filter media. |
| Chinook prices have no currency column. | Return decimal strings and `currency: null`; prompt forbids invented currency symbols. |
| Studio context is not customer authentication. Its operator can edit configuration and state. | Clearly label mock identity; use separate threads per customer. Real thread/checkpoint ACLs belong at the authenticated application boundary. Do not claim this local slice is a production login system. |
| `langgraph dev` loads `.env` over shell overrides, including empty key values. | During initial setup, left the then-blank `.env` unchanged and used a separate temporary tracing-disabled config for startup/schema checks. That temporary config was later removed; credentials have since been supplied. |
| Assistant schema REST endpoint requires the assistant UUID; graph name `support` returned 422. | Read the UUID displayed by Studio for the schema check. Normal interaction still selects the `support` graph. |
| OpenAI and LangSmith keys were unavailable during initial implementation. | Credentials were later supplied. Live model execution, hosted traces and five Studio scenarios passed on September 23; evidence is in `docs/PHASE1_STATUS.md`. |

At Phase 1 closure: still one business tool, no Deep Agents, no
recommendations, no support writes, no evaluation dataset and no deployment.

## GPT-6 Luna configuration

An offline payload check showed that the installed LangChain OpenAI integration
automatically routes GPT-6 tool calls to Responses. To preserve the existing Chat
Completions flow, the Luna configuration explicitly sets `use_responses_api=False`
and `reasoning_effort="none"`. OpenAI documents the latter as required for Luna
function calling on Chat Completions. The corrected payload was verified locally;
real model execution and account access were subsequently verified successfully.

## Phase 1 live verification — 2026-09-23

- The first live command failed on sandbox DNS restrictions. Re-running with
  approved network access succeeded; this was not a credential or model failure.
- The trace helper emitted deprecation warnings for `read_run` and `get_run_url`.
  Migrated to async `traces.list_runs` and `runs.get_url` using the official
  [migration guide](https://docs.langchain.com/langsmith/smithdb-sdk-migration-runs).
- That guide and SDK types describe uppercase run/status values, but actual
  hosted responses returned lowercase `llm`, `tool` and `success`. The first
  migrated check timed out despite a successful trace. Normalizing case fixed
  the verifier; a fresh complete live run then passed without those warnings.
- Luna called invoice 98's video episodes “tracks,” matching the generic Chinook
  table terminology. Titles, date, quantities and amounts were accurate. This is
  a wording limitation to retain for later evaluation, not an authorization failure.

## Phase 2 — 2026-09-23

- A video track is classified as Alternative, so filtering music genres alone
  would admit non-music. Discovery now requires both a known audio media type and
  a music genre from the pinned snapshot; missing/unknown classifications fail
  closed. Tests cover the real Alternative video and altered temporary fixtures.
- The current [middleware documentation](https://docs.langchain.com/oss/python/langchain/middleware/built-in#tool-call-limit)
  still describes `exit_behavior="end"` as a single-tool limitation. Installed
  LangChain 1.4.2 handles multi-call batches by cancelling every pending call when
  the batch exceeds the limit. Source inspection and full-graph regression tests
  verified mixed-tool batches below and above the global four-call limit. No
  custom middleware or dependency upgrade was necessary.
- Simple genre/artist frequency ranking gives customer 1 three Guns N' Roses
  tracks from the same album. This is an explainable baseline, not a diversity
  optimizer. Preserve it for a later measured baseline/improvement comparison.
- The expanded prompt distinguishes video episodes from music. The live purchase
  regression correctly called invoice 98's items video episodes. This one observed
  improvement is not a measured model-quality claim.

## Phase 3 — 2026-09-24

- The installed HITL middleware emits action `args`; a current documentation
  example shows `arguments`. Full-graph tests exposed the difference. Use the
  installed shape and keep regression coverage for actual interrupts.
- Tool-call middleware stores its run counter in an untracked channel: interrupt
  resume resets that counter. Added its built-in persistent `thread_limit=20`
  alongside `run_limit=4`; tests prove a 21st proposal never reaches approval.
  Middleware registration puts limit enforcement before HITL in the reverse-order
  `after_model` chain. No custom counter/state layer was added.
- The initial context hook does not serve as a resume guard. Tools explicitly
  require context during execution and check ownership after review. Tests prove
  a missing resume context fails closed. Customer/thread binding is still the
  trusted caller's responsibility, not something simulated authentication enforces.
- The framework prepends a reviewer-edit notice to edited tool results. Kept it:
  the live model correctly described invoice 382 instead of the original invoice
  98. Verification reads persisted rows rather than assuming every tool message
  is an unadorned JSON string.
- Incomplete batch decisions fail before writes. A malformed consumed resume
  value can remain recorded in its checkpoint, so simply submitting a corrected
  value to the same failed task is not a reliable recovery path. Validate the
  decision count before submission; use a fresh demo thread after this error and
  inspect existing cases before retrying.
- Studio's current Chat view renders a generic interrupt and resume-value editor.
  Approve/reject passed. An edit attempt submitted only `{"type":"edit"}` even
  though the editor displayed the full payload, leading to `KeyError('edited_action')`
  before any write. The local run's recorded command confirmed the missing fields;
  the Python edit smoke test passed. A fresh thread and pasting/verifying the full
  payload before clicking Resume succeeded, with the full action present in the
  server command and the correct edited row saved. Rapid entry/submission also
  produced an empty-message diagnostic run. Treat this as observed UI-entry timing
  friction; the exact frontend cause was not established. No application workaround
  or custom approval middleware was needed.

## Phase 4 — 2026-09-24

- The first live evaluation exposed overly literal name grading: smart apostrophes
  in accurate titles/artists produced false negatives. Preserved that initial
  experiment, normalized typographic quotes/whitespace, added a regression test,
  and reran the unchanged baseline before any agent improvement. The comparison
  uses the same corrected grader on both baseline and candidate; initial scores
  are not presented as an agent-quality improvement.
- The baseline's real limitation was the candidate set: all three recommended Rock
  tracks came from one artist. More prompt pressure could not supply eligible
  alternatives that the tool had not returned. Added one optional artist constraint
  in the existing SQL/tool path, preserving default ranking and hard exclusions.
  With identical corrected graders/cases, artist variety improved 0/2 → 2/2 and
  whole-case success 28/30 → 30/30. This is a small regression comparison, not a
  general recommendation-quality claim.
