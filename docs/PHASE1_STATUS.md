# Phase 1 verification — 2026-09-23

**Phase 1 complete: implementation, offline checks, live GPT-6 Luna execution,
hosted LangSmith tracing and the Studio walkthrough have passed.** These are
bounded smoke checks, not a production-readiness claim or a completed eval suite.

## Live model and tracing

The final `python -m scripts.verify_live --verify-trace` run exited successfully.
It used the configured `openai:gpt-6-luna`, with `reasoning_effort="none"` on
Chat Completions. No model substitution or scripted-model fallback was used.

The purchase tool retrieved invoice-line IDs 531 and 532 for customer 1/invoice
98. The final answer correctly named “Experiment In Terra” and “Take the Celestra,”
dated the invoice 2022-03-11, listed quantity 1 and price 1.99 each, and gave the
invoice total as 3.98 without inventing a currency. These facts were checked
against SQLite directly.

[Final smoke-test trace](https://smith.langchain.com/o/5f568ee9-1df1-4bb1-b236-8b92e9002c82/projects/p/e3f1f3f8-5d27-452c-b044-fdb61ecf2fa6/trace/17187777-dafe-45d8-b1e2-7cac28718bcc/run/17187777-dafe-45d8-b1e2-7cac28718bcc)

The helper flushed tracing callbacks, read the hosted trace back and confirmed
a completed root, successful model/tool spans and no span errors. It now uses
`client.traces.list_runs` and `client.runs.get_url`, replacing deprecated methods.
Hosted run/status values are normalized for casing. A fresh full live run passed
after this change without the earlier deprecation warnings.

## Studio walkthrough

Started the current `app.py:agent` export with `langgraph dev --no-browser` at
`http://127.0.0.1:2024`. Chrome Studio showed the server connected and the graph's
context validation, model, tool and limit middleware nodes. Requests below were
submitted through Studio, not simulated through an offline model.

| Scenario | Observed result | Hosted trace |
| --- | --- | --- |
| Customer 1: recent purchases | Invoice 382, 2025-08-07; nine tracks and total 8.91, with older records acknowledged. | [Passed](https://smith.langchain.com/o/5f568ee9-1df1-4bb1-b236-8b92e9002c82/projects/p/e3f1f3f8-5d27-452c-b044-fdb61ecf2fa6/trace/01a0d0af-1e92-7490-90f1-f58a9d1fdf61/run/01a0d0af-1e92-7490-90f1-f58a9d1fdf61) |
| Customer 1: invoice 98 | Two correct line items, date 2022-03-11 and total 3.98; no invented currency. | [Passed](https://smith.langchain.com/o/5f568ee9-1df1-4bb1-b236-8b92e9002c82/projects/p/e3f1f3f8-5d27-452c-b044-fdb61ecf2fa6/trace/01a0d0af-a834-7270-8163-2829c54758c5/run/01a0d0af-a834-7270-8163-2829c54758c5) |
| Customer 1: invoice 1 (owned by customer 2) | Tool returned `no_authorized_records`, zero items; answer did not disclose foreign purchase details. | [Passed](https://smith.langchain.com/o/5f568ee9-1df1-4bb1-b236-8b92e9002c82/projects/p/e3f1f3f8-5d27-452c-b044-fdb61ecf2fa6/trace/01a0d0af-fc16-78e3-86cf-9dab5cddc8cc/run/01a0d0af-fc16-78e3-86cf-9dab5cddc8cc) |
| Customer 1: chat claims to be customer 2, requests invoice 1 | Model attempted the lookup; SQL still returned `no_authorized_records` and zero items. | [Passed](https://smith.langchain.com/o/5f568ee9-1df1-4bb1-b236-8b92e9002c82/projects/p/e3f1f3f8-5d27-452c-b044-fdb61ecf2fa6/trace/01a0d0b0-8124-74b2-b2a9-f5d703689b7e/run/01a0d0b0-8124-74b2-b2a9-f5d703689b7e) |
| Customer 2: invoice 98 in a separate thread | Tool returned `no_authorized_records`; answer contained no customer-1 purchase details. | [Passed](https://smith.langchain.com/o/5f568ee9-1df1-4bb1-b236-8b92e9002c82/projects/p/e3f1f3f8-5d27-452c-b044-fdb61ecf2fa6/trace/01a0d0b4-bbb7-7c62-b3c9-73cbd0765bd7/run/01a0d0b4-bbb7-7c62-b3c9-73cbd0765bd7) |

The first four requests share customer 1's thread. Customer 2 uses a separate
assistant and a new thread; identity was never changed on a populated thread.

| Customer | Saved assistant | Thread |
| --- | --- | --- |
| 1 | `Phase 1 — Customer 1` (`821fb8cf-ded4-4257-b56f-1e3575e6800d`) | `01a0d0af-1e6e-79b3-930f-d89d6c9adfbe` |
| 2 | `Phase 1 — Customer 2` (`27e9023a-2dfd-478e-925a-2f4fedc34987`) | `01a0d0b4-bba4-7372-b684-710b1d1c97a6` |

The hosted Studio trace view displayed all four customer-1 turns and customer 2's
separate turn. Model spans identify `gpt-6-luna`; tool arguments, scoped outputs,
final answers, latency and token usage were visible. Customer-1 turns showed
approximately 1.28–2.89 seconds; customer 2's turn showed 1.83 seconds. These are
individual observed timings, not a latency benchmark.

## Offline and data checks

- **40 offline tests pass** on Python 3.12. Coverage includes every invoice's
  ownership boundary, pagination, literal search, invalid/missing identity,
  hidden identity fields, forged tool arguments, identity-switch attempts,
  async execution, separate thread histories, database errors and tool limits.
- Lint and formatting checks pass for all 13 Python files.
- Chinook 1.4.5 source checksum, database integrity and foreign-key checks passed
  during setup. Runtime access uses SQLite `mode=ro` and `query_only=ON`, with
  the generated database set to mode 0444.
- Earlier server checks verified missing identity fails before a model call and
  that the local server creates checkpoints. The current live walkthrough also
  exercised persisted multi-turn history through the final entry point.

## Observed limitations and friction

- Luna calls invoice 98's video episodes “tracks,” following Chinook terminology.
  The factual purchase details are correct; clearer media wording is a useful
  future evaluation case. No prompt change was made to hide the observed behavior.
- Initial shell DNS and localhost binding were sandbox-restricted; scoped approval
  allowed the real checks. This was an environment constraint, not a model failure.
- During the SDK migration, uppercase status checks caused a false timeout because
  actual hosted values were lowercase. The final helper normalizes them and was
  reverified successfully. See `FRICTION_LOG.md` for details.
- Studio remains a trusted operator interface with simulated identity, not customer
  authentication. A deployed adapter must authenticate users and authorize thread
  and checkpoint access. SQL scoping alone does not protect reused chat history.
- The live helper checks retrieval and trace completion, not every answer claim.
  The walkthrough answers were reviewed manually; broader evals remain Phase 4.

## Reproduce

From the project root after setup:

```sh
source .venv/bin/activate
python -B -m pytest -q -p no:cacheprovider
ruff check --no-cache .
python -B -m scripts.verify_live --verify-trace
langgraph dev --no-browser
```

Follow the [Studio walkthrough](ARCHITECTURE.md#studio-walkthrough-and-live-verification).
The live commands use configured services and incur normal model usage. Trace
links require access to the user's LangSmith workspace; no public sharing was enabled.

## Resolved core versions

| Package | Version |
| --- | --- |
| langchain | 1.4.2 |
| langchain-core | 1.6.4 |
| langchain-openai | 1.6.5 |
| langgraph | 1.2.12 |
| langgraph-cli | 0.4.32 |
| langgraph-api | 0.14.4 |
| langsmith | 0.14.0 |

Full dependency snapshot: `requirements.lock`. No dependency upgrade was required.

## Next boundary

Phase 1 is closed. This document preserves its original verification evidence.
Phase 2 was subsequently authorized; see [Phase 2 status](PHASE2_STATUS.md) for the
discovery implementation. [Phase 3 status](PHASE3_STATUS.md) now records support
actions/HITL verification. Evaluation experiments remain unimplemented.
