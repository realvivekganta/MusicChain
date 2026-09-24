# Engineering friction log

Observed during implementation and verification on 2026-09-23 and 2026-09-24.
See [verification](VERIFICATION.md) and [evaluation](EVALUATION.md) for evidence.

## Runtime identity bounds

- An oversized trusted customer ID (`2**63`) passed the original positive-integer
  check and then raised `OverflowError` when bound to SQLite. No data escaped its
  scope. Restricted runtime IDs to positive signed-64-bit integers, matching the
  database, and added coverage for the upper boundary and rejection before model
  execution. The suite now has 139 passing tests.

## Tool schemas and source data

| Observation | Resolution |
| --- | --- |
| A strict custom Pydantic `args_schema` without a runtime field rejected the runtime injected by ToolNode. The user-visible error was vague. | Full-graph tests caught seven failures that pure SQL tests missed. Switched to the documented signature-inferred `@tool` schema with `ToolRuntime` and constrained annotations; all graph tests pass. |
| Current Chinook 1.4.5 dates differ from older copies; invoice 98 is two video items, not music. | Inspect and pin the actual source. Do not memorize older demo dates or assume every Track is music. Purchase support returns real data; discovery filters both media type and genre. |
| Chinook prices have no currency column. | Return decimal strings and `currency: null`; prompt forbids invented currency symbols. |
| Studio context is not customer authentication. Its operator can edit configuration and state. | Clearly label mock identity; use separate threads per customer. Real thread/checkpoint ACLs belong at the authenticated application boundary. Do not claim this local slice is a production login system. |
| Assistant schema REST endpoint requires the assistant UUID; graph name `support` returned 422. | Read the UUID displayed by Studio for the schema check. Normal interaction still selects the `support` graph. |

## GPT-6 Luna configuration

An offline payload check showed that the installed LangChain OpenAI integration
automatically routes GPT-6 tool calls to Responses. To preserve the existing Chat
Completions flow, the Luna configuration explicitly sets `use_responses_api=False`
and `reasoning_effort="none"`. OpenAI documents the latter as required for Luna
function calling on Chat Completions. The corrected payload was verified locally;
real model execution and account access were subsequently verified successfully.

## Hosted trace verification

- The trace helper emitted deprecation warnings for `read_run` and `get_run_url`.
  Migrated to async `traces.list_runs` and `runs.get_url` using the official
  [migration guide](https://docs.langchain.com/langsmith/smithdb-sdk-migration-runs).
- That guide and SDK types describe uppercase run/status values, but actual
  hosted responses returned lowercase `llm`, `tool` and `success`. The first
  migrated check timed out despite a successful trace. Normalizing case fixed
  the verifier; a fresh complete live run then passed without those warnings.
- Luna called invoice 98's video episodes “tracks,” matching the generic Chinook
  table terminology. Titles, date, quantities and amounts were accurate. This is
  an observed wording limitation, not an authorization failure. Subsequent prompt
  changes and live checks distinguished video episodes from music.

## Discovery classification and tool limits

- A video track is classified as Alternative, so filtering music genres alone
  would admit non-music. Discovery now requires both a known audio media type and
  a music genre from the pinned snapshot; missing/unknown classifications fail
  closed. Tests cover the real Alternative video and altered temporary fixtures.
- The [middleware documentation](https://docs.langchain.com/oss/python/langchain/middleware/built-in#tool-call-limit)
  described `exit_behavior="end"` as a single-tool limitation at verification time. Installed
  LangChain 1.4.2 handles multi-call batches by cancelling every pending call when
  the batch exceeds the limit. Source inspection and full-graph regression tests
  verified mixed-tool batches below and above the global four-call limit. No
  custom middleware or dependency upgrade was necessary.
- Simple genre/artist frequency ranking gives customer 1 three Guns N' Roses
  tracks from the same album. This baseline was preserved for the measured
  artist-variety improvement recorded in [evaluation](EVALUATION.md).
- The expanded prompt distinguishes video episodes from music. The live purchase
  regression correctly called invoice 98's items video episodes. This one observed
  improvement is not a measured model-quality claim.

## Human review and resume semantics

- The installed HITL middleware emits action `args`; a documentation
  example showed `arguments`. Full-graph tests exposed the difference. Use the
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
- Studio's Chat view during verification renders a generic interrupt and resume-value editor.
  Approve/reject passed. An edit attempt submitted only `{"type":"edit"}` even
  though the editor displayed the full payload, leading to `KeyError('edited_action')`
  before any write. The local run's recorded command confirmed the missing fields;
  the Python edit smoke test passed. A fresh thread and pasting/verifying the full
  payload before clicking Resume succeeded, with the full action present in the
  server command and the correct edited row saved. Rapid entry/submission also
  produced an empty-message diagnostic run. Treat this as observed UI-entry timing
  friction; the exact frontend cause was not established. No application workaround
  or custom approval middleware was needed.

## Evaluator calibration and artist variety

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

## Local configuration behavior

The local server loads `.env` over shell overrides, including blank values.
Configuration and tracing checks must use the effective server environment.
