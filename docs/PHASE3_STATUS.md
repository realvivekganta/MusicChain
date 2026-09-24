# Phase 3 verification — 2026-09-24

**Phase 3 is complete:** controlled mock support requests, approval middleware,
separate storage, offline checks, live OpenAI calls, hosted traces and Studio
approve/reject/edit walkthroughs passed. These are bounded verification checks;
production authentication and the Phase 4 evaluation suite are not implemented.

## Implemented behavior

- Fourth tool: `create_support_request(invoice_id, reason)`. Customer identity is
  injected through trusted runtime context, never selected by the model.
- Built-in HITL middleware pauses before executing support actions. Only approve,
  edit and reject are enabled. Read-only requests remain autonomous.
- Final arguments and ownership are checked after review. Human approval cannot
  authorize an invoice belonging to another customer. Missing/foreign invoices
  return the same `no_authorized_records` result.
- `support_store.py` owns the separate writable SQLite store. An atomic transaction
  and unique customer/invoice constraint return one unchanged case on retries or
  concurrent submissions. A case is confirmed only after commit.
- Chinook stays read-only. Support-store paths cannot alias it directly or through
  symlinks/hardlinks. The runtime Chinook hash was unchanged during the walkthrough.
- Four tool proposals per invocation, twenty per thread. The persisted thread cap
  is necessary because the framework's run count resets on interrupt resume.
- Support requests are local mock records. No refund is executed and no external
  ticket, email or other communication is sent.

One new application module (`support_store.py`) and one new test file
(`test_support.py`) were added. Existing context, tools, agent, prompt, database,
test fixtures and live verifier were extended; no new dependency or agent layer.

## Offline evidence

**99 tests pass** on Python 3.12. Ruff lint and formatting checks pass. New tests
cover pre-approval absence of writes, rejection, reviewed edits, invalid inputs,
fresh ownership checks, forged runtime/identity arguments, missing resume context,
async execution, ordered batch decisions, invalid decisions, over-limit batches,
the persisted thread limit, duplicate/replayed/concurrent submissions, rollback,
database failures and source-file aliases. All Phase 1/2 tests remain passing.

The source database and case stores used by tests are temporary fixtures; tests
neither call providers nor send traces. The 99 count is the entire offline suite,
not a separate LangSmith evaluation dataset.

## Live helper and hosted traces

The three support scenarios use real `openai:gpt-6-luna`, a fresh temporary support
database and a fixed scripted reviewer decision. Each checked the actual stored
rows and final model response. Hosted resumed traces were read back successfully;
approval/edit include executed tool spans, while rejection skips tool execution.

| Scenario | Observed outcome | Resumed trace |
| --- | --- | --- |
| Approve | Paused before store creation, then saved one open invoice-98 case and returned its ID with a mock/no-refund explanation. | [Passed](https://smith.langchain.com/o/5f568ee9-1df1-4bb1-b236-8b92e9002c82/projects/p/e3f1f3f8-5d27-452c-b044-fdb61ecf2fa6/trace/beca7975-892c-4935-85bd-2cab6a17dce9/run/beca7975-892c-4935-85bd-2cab6a17dce9) |
| Reject | Created no store or case. Model correctly said it did not create a request. | [Passed](https://smith.langchain.com/o/5f568ee9-1df1-4bb1-b236-8b92e9002c82/projects/p/e3f1f3f8-5d27-452c-b044-fdb61ecf2fa6/trace/4b07790e-fe96-4690-a3b3-507fe2f052ba/run/4b07790e-fe96-4690-a3b3-507fe2f052ba) |
| Edit | Changed proposal from invoice 98 to 382 and saved the exact reviewed reason. Model described invoice 382 correctly. | [Passed](https://smith.langchain.com/o/5f568ee9-1df1-4bb1-b236-8b92e9002c82/projects/p/e3f1f3f8-5d27-452c-b044-fdb61ecf2fa6/trace/0c226a34-db33-42d2-b954-39cfe6cc24a6/run/0c226a34-db33-42d2-b954-39cfe6cc24a6) |

Proposal run IDs, in the same order: `ad67c569-e25f-45fc-8242-1223ac237254`,
`f3013518-84e1-49e8-8fd8-b9718fb83ab3`, `dfb4130a-1a7a-4d1a-938f-ba8a695202d4`.
The helper prints proposal and resume separately because resuming creates another
run. Temporary smoke-test stores are removed after verification.

Existing tools also passed live regression checks after the new middleware/prompt:

- [Purchase lookup](https://smith.langchain.com/o/5f568ee9-1df1-4bb1-b236-8b92e9002c82/projects/p/e3f1f3f8-5d27-452c-b044-fdb61ecf2fa6/trace/8058c6bc-acc1-4d7f-a572-5a6a3ac73793/run/8058c6bc-acc1-4d7f-a572-5a6a3ac73793): correct invoice-98 episodes, date and total.
- [Catalog search](https://smith.langchain.com/o/5f568ee9-1df1-4bb1-b236-8b92e9002c82/projects/p/e3f1f3f8-5d27-452c-b044-fdb61ecf2fa6/trace/99c57f7f-24e1-469b-be75-00d6d2551aad/run/99c57f7f-24e1-469b-be75-00d6d2551aad): Miles Davis Jazz IDs 597–599.
- [Recommendations](https://smith.langchain.com/o/5f568ee9-1df1-4bb1-b236-8b92e9002c82/projects/p/e3f1f3f8-5d27-452c-b044-fdb61ecf2fa6/trace/331267c4-7115-4727-854b-4c22eea35aac/run/331267c4-7115-4727-854b-4c22eea35aac): unowned Rock IDs 1146–1148 with accurate purchase counts.

## Studio and persisted case evidence

Used the saved customer-1 assistant, with new Phase 3 threads. Studio showed the
HITL interrupt and allowed decision types. Decisions were entered in its generic
resume editor. The successful resumed traces below were independently verified
through the hosted SDK, and actual SQLite rows were inspected after each action.

| Scenario | Persisted outcome | Hosted resumed trace |
| --- | --- | --- |
| Approve invoice 98 | Case `a13af962-0d0a-4380-8c1b-ca3a6a7a877f`, open, reason “I do not recognize this invoice.” | [Passed](https://smith.langchain.com/o/5f568ee9-1df1-4bb1-b236-8b92e9002c82/projects/p/e3f1f3f8-5d27-452c-b044-fdb61ecf2fa6/trace/01a0d444-89ad-76b2-aa25-f5c444e20417/run/01a0d444-89ad-76b2-aa25-f5c444e20417) |
| Reject invoice 121 | No invoice-121 case; existing invoice-98 case unchanged. | [Passed](https://smith.langchain.com/o/5f568ee9-1df1-4bb1-b236-8b92e9002c82/projects/p/e3f1f3f8-5d27-452c-b044-fdb61ecf2fa6/trace/01a0d445-acc2-74a3-a1d6-09b527680e8a/run/01a0d445-acc2-74a3-a1d6-09b527680e8a) |
| Edit invoice 143 proposal to 382 | Case `fab02178-2be5-442c-a7d7-9601c6e6ab43`, open, reason “Reviewed demo: please investigate invoice 382.” No invoice-143 case. | [Passed](https://smith.langchain.com/o/5f568ee9-1df1-4bb1-b236-8b92e9002c82/projects/p/e3f1f3f8-5d27-452c-b044-fdb61ecf2fa6/trace/01a0d44c-9812-76a2-ac72-81c67defbfe8/run/01a0d44c-9812-76a2-ac72-81c67defbfe8) |

Approve/reject thread: `01a0d444-2f0e-75d0-8ba8-aa701334cb2b`.
Successful edit thread: `01a0d44b-af71-7663-b981-f2c7482cff3c`.
The normal gitignored store retains the two successful demo cases. Repeating these
invoice requests will return `already_exists` after review, preserving their reasons.

The first Studio edit submission reached the server with only `type: edit`, missing
`edited_action`, and failed before any write (run
`01a0d447-bea5-76a3-823f-34738519b4c3`). Retained this evidence. A fresh thread and
pasting/verifying the complete value before clicking Resume succeeded; the recorded
server command contained the full edited action. Rapid typing/submission also
produced one empty-message diagnostic run. This is an observed UI-entry timing
issue, not an authorization bypass; the precise frontend cause was not established.
See [friction log](../FRICTION_LOG.md).

## Limits and next work

- Studio simulates authentication; the trusted caller must maintain customer/thread
  binding and pass the same context on resume. Reviewer access and thread/checkpoint
  ACLs belong in a real authenticated adapter. Missing context fails closed; a
  trusted operator deliberately changing context is outside that guarantee.
- Approval gates the agent tool path. Internal storage functions are not public
  APIs and do not independently authenticate a reviewer.
- One open case per invoice; no closing/reopening or refund execution. Traces are
  demo evidence, not a tamper-proof approval ledger.
- Invalid resume payloads can remain consumed in a failed checkpoint. Validate the
  complete payload before resuming; after this error, use a fresh demo thread and
  inspect existing cases before retrying.
- Live checks inspect persisted outcomes and manually review final wording. They
  do not replace a broader model evaluation suite.

Next is **Phase 4**: LangSmith evaluation cases and a preserved baseline → improvement
comparison. Phase 5 is interview/demo polish. Neither is implemented in this phase.

## Reproduce

```sh
source .venv/bin/activate
python -B -m pytest -q -p no:cacheprovider
ruff check --no-cache .
ruff format --check --no-cache .
python -B -m scripts.verify_live --scenario support-approve --verify-trace
python -B -m scripts.verify_live --scenario support-reject --verify-trace
python -B -m scripts.verify_live --scenario support-edit --verify-trace
langgraph dev --no-browser
```

Follow the [Studio approval walkthrough](ARCHITECTURE.md#support-approval-in-studio).
Live commands use configured services and normal model usage. Hosted links require
workspace access; no public sharing was enabled.
