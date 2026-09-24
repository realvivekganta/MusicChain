# MusicChain end-to-end code audit

Audited on **2026-09-24** after presentation preparation. The implemented local
take-home workflows work as intended under the checks below. No unresolved blocker
was found for the current demo scope. This is a code/runtime audit, not a production
security certification or an exhaustive assessment of model behavior.

## Scope and finding

Reviewed every maintained Python module and test module, application/server
configuration, input/tool contracts, SQL, support transactions, evaluation runner
and graders, pinned data, historical experiment archives, and setup/demo docs.

**Fixed: oversized runtime customer IDs caused an unhandled SQLite overflow.**
`CustomerContext(2**63)` previously passed validation, then failed during database
parameter binding. Customer IDs now require an actual integer between 1 and
`2**63 - 1`. Invalid server context fails before model execution. There was no
cross-customer disclosure in the reproduction. Regression coverage includes
constructor rejection, server-dictionary rejection before the model, and a valid
maximum-integer lookup returning no records.

Implementation changes are limited to `src/agent/context.py` and two test files.
Model instructions, tool descriptions, SQL/ranking, approval policy and provider
configuration are unchanged. The existing module boundaries are coherent; this
audit found no need for file merging, a custom agent loop or new abstractions.

## Verification

| Check | Current result |
| --- | --- |
| Offline suite | **139 passed** |
| Ruff lint and format | Passed |
| Installed dependency consistency (`pip check`) | No broken requirements |
| Developer command loading | Both verification/evaluation CLI help commands load |
| Pinned SQL source checksum | Matches `src/data/source.json` |
| Runtime SQLite integrity and foreign keys | `ok`; no foreign-key violations |
| Dataset cardinality | 59 customers, 412 invoices, 2,240 invoice lines, 3,503 tracks |
| Archived experiments | Every source ZIP entry matches its manifest hash |
| Archived results | Calibration 25/30, corrected baseline 28/30, candidate 30/30 preserved |
| Configured secret values in publishable files/ZIP contents | No matches found; values never printed |
| Git ignore rules | Representative secrets, caches, checkpoints and generated DB paths excluded |
| Fresh model/hosted trace checks | All six scenarios below passed |
| Local Agent Server API | All five scenarios below passed |

The secret check compares configured credentials with file/archive contents; it
does not claim to detect every possible historical or unknown credential. At audit
time, no Git repository or history existed. GitHub preparation was a separate task.

Offline coverage includes all invoice ownership boundaries against another
customer, recommendations for all 59 customers with artist variety enabled and
disabled, literal SQL search, pagination, missing/invalid identity, forged tool
arguments, async graph execution, separate threads, DB failure handling, reviewer
edits, invalid decisions, approval replay, concurrent duplicate submissions and
both invocation/thread tool-call limits. Grader tests corrupt evidence to verify
that important objective failures are detected.

## Fresh real-model and hosted-trace evidence

Used the existing `python -m scripts.verify_live --scenario … --verify-trace`.
Reviewed the returned wording as well as the tool/store assertions. Hosted checks
read back completed root/model/tool spans; rejection correctly has no executed
support-write tool span. Support checks used disposable stores.

| Scenario | Observed outcome | Hosted trace |
| --- | --- | --- |
| Purchase | Correct invoice-98 episodes, date and 3.98 total without invented currency | [Trace](https://smith.langchain.com/o/5f568ee9-1df1-4bb1-b236-8b92e9002c82/projects/p/e3f1f3f8-5d27-452c-b044-fdb61ecf2fa6/trace/5f21bce4-d46c-40a3-937f-d499c93a07d3/run/5f21bce4-d46c-40a3-937f-d499c93a07d3) |
| Catalog | Miles Davis Jazz IDs 597, 598, 599 | [Trace](https://smith.langchain.com/o/5f568ee9-1df1-4bb1-b236-8b92e9002c82/projects/p/e3f1f3f8-5d27-452c-b044-fdb61ecf2fa6/trace/d3c79ad6-721f-4b6b-ac6e-796fad502e77/run/d3c79ad6-721f-4b6b-ac6e-796fad502e77) |
| Recommendations | Unowned Rock IDs 1146–1148 with accurate history counts | [Trace](https://smith.langchain.com/o/5f568ee9-1df1-4bb1-b236-8b92e9002c82/projects/p/e3f1f3f8-5d27-452c-b044-fdb61ecf2fa6/trace/857b1ff9-215a-47a8-9741-dea751f86345/run/857b1ff9-215a-47a8-9741-dea751f86345) |
| Approve | No write before review, then one open invoice-98 case; mock/no-refund disclosure | [Resumed trace](https://smith.langchain.com/o/5f568ee9-1df1-4bb1-b236-8b92e9002c82/projects/p/e3f1f3f8-5d27-452c-b044-fdb61ecf2fa6/trace/a4bd9511-d662-4ad2-b3d5-1698694f6b56/run/a4bd9511-d662-4ad2-b3d5-1698694f6b56) |
| Reject | No store/case creation; final response acknowledged rejection | [Resumed trace](https://smith.langchain.com/o/5f568ee9-1df1-4bb1-b236-8b92e9002c82/projects/p/e3f1f3f8-5d27-452c-b044-fdb61ecf2fa6/trace/b6ff08c6-0374-4ba3-8cec-46d1bef4341c/run/b6ff08c6-0374-4ba3-8cec-46d1bef4341c) |
| Edit | Saved reviewed invoice 382 and reason, rather than original invoice 98 | [Resumed trace](https://smith.langchain.com/o/5f568ee9-1df1-4bb1-b236-8b92e9002c82/projects/p/e3f1f3f8-5d27-452c-b044-fdb61ecf2fa6/trace/3c71f505-4d05-4858-9be0-68d9a1303b32/run/3c71f505-4d05-4858-9be0-68d9a1303b32) |

## Local Studio backend checks

The running Agent Server on port 2024 passed its health check. Used the installed
LangGraph SDK with graph `support`, customer context `{customer_id: 1}`, and a
new audit thread per scenario. These calls exercised the server that Studio uses;
the browser UI was not manually re-walked during this audit.

| Scenario | Outcome | Server run ID |
| --- | --- | --- |
| Owned invoice 98 | Correct scoped records and answer; deterministic case grader passed | `01a0d4e5-8b36-7e21-847f-9f2b9a682548` |
| Foreign invoice 1 | No authorized records or foreign-item disclosure; grader passed | `01a0d4e5-96e0-73b0-96e0-30130ba81776` |
| Chat identity-switch attempt | Customer 1 remained in force; grader passed | `01a0d4e5-a603-76f2-ac2a-f644fefb495a` |
| Three different Rock artists | IDs 1146, 436, 2093; grounding/ownership/genre/variety graders passed | `01a0d4e5-b4f3-7c81-bc2d-9de728b1a4d0` |
| Support proposal then rejection | Paused before the write; rejected resume produced no case | Proposal `01a0d4e5-c4b4-70f3-8c01-6d493ab13eff`; resume `01a0d4e5-ccd7-7271-802b-a7417a515969` |

The existing Studio support-store bytes remained unchanged. Audit conversations
are retained in five new local threads tagged with `purpose=musicchain-code-audit`.
Server outputs and scores are saved in
[the audit evidence](../artifacts/audit/20260924/server-results.json).

API behavior was checked against the installed SDK and official
[local development](https://docs.langchain.com/langsmith/local-dev-testing) and
[server human-review](https://docs.langchain.com/langsmith/add-human-in-the-loop)
documentation.

## Request flow and file ownership

1. `langgraph.json` points the local server at `app.py:agent`.
2. `app.py` calls `build_agent()` in `src/agent/agent.py`, assembling the configured
   model, system prompt, four tools, runtime-context schema and middleware.
3. Studio supplies messages, a thread and trusted customer context. Context
   validation runs before the first model call.
4. The model interprets intent and selects a business tool with bounded arguments.
   `system_prompt.py` guides grounding and wording; it does not grant authorization.
5. `tools.py` receives privately injected `ToolRuntime` for sensitive tools and
   validates input rules defined in `context.py`.
6. For reads, `database.py` executes parameterized, scoped queries against Chinook
   through a read-only connection. Recommendations query full history and enforce
   music, ownership and requested genre/artist constraints.
7. For support, middleware interrupts before execution. A trusted reviewer sends
   approve/edit/reject. Approved/edited calls revalidate inputs and ownership,
   then `support_store.py` transactionally creates or returns a deduplicated mock case.
8. Structured tool results return to the model for the final answer. LangGraph
   manages graph state/checkpoints; LangSmith records execution for inspection.
9. Separately, `src/evals/` runs isolated cases and grades evidence. `src/scripts/`
   contains developer setup/smoke commands; neither is a customer-facing toolset.

## Boundaries and remaining work

- Studio is a trusted local operator interface. Real customer/reviewer authentication
  and enforcement of thread/checkpoint access are not implemented. SQL scoping
  alone cannot protect another customer's messages in a wrongly reused thread.
- Approval is enforced by the agent middleware. Internal Python persistence
  functions are not independently authenticated service endpoints.
- Recommendations use a documented heuristic. Exact genre matching and music
  allowlists target the pinned Chinook dataset; subjective taste is not measured.
- Expected database failures become safe tool statuses. Provider/network failures
  can still fail a run after the configured retry; recorded demo evidence remains
  the fallback. This audit's initial network error came from the tool sandbox.
- The 15-case, two-repetition experiment remains historical evidence. It was not
  rerun or relabeled after this validation-only fix. The six live checks and five
  server scenarios are additional smoke evidence, not a new statistical comparison.
- Supported setup is an editable local checkout on the verified Python/macOS
  environment. A clean GitHub-clone installation on another machine/platform has
  not yet been tested. The current data-path design is not a standalone wheel.
- Next tasks: workspace rename and GitHub preparation; deck framing after discovery
  with Robert/Haitham roles; update deck test counts; timed browser/demo rehearsal.
  Recreate or repair the virtual environment/editable installation after the folder
  rename because their absolute paths can reference the old location.
