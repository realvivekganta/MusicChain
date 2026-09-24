# Verification

The latest recorded end-to-end checks are dated **2026-09-24**. All 139 offline
tests, six live/hosted-trace scenarios and five Agent Server API scenarios passed.
These are bounded application checks, not a production security certification or
an exhaustive model assessment. Historical browser walkthroughs and their earlier
test counts are retained below. Hosted links require LangSmith workspace access;
they have not been made public.

## Contents

- [Run checks](#run-checks)
- [Latest results](#latest-verification-results)
- [Live model and trace evidence](#fresh-real-model-and-hosted-trace-evidence)
- [Agent Server checks](#local-studio-backend-checks)
- [Installation verification](#installation-verification)
- [Known limits](#known-limits)
- [Historical browser and live checks](#historical-browser-and-live-checks)

## Run checks

After [setup](../README.md#quickstart), run offline checks without credentials:

```sh
pytest -q
ruff check .
ruff format --check .
python -m pip check
```

The live smoke commands use configured services and incur normal model usage:

```sh
python -m scripts.verify_live --verify-trace
python -m scripts.verify_live --scenario catalog --verify-trace
python -m scripts.verify_live --scenario recommendations --verify-trace
python -m scripts.verify_live --scenario support-approve --verify-trace
python -m scripts.verify_live --scenario support-reject --verify-trace
python -m scripts.verify_live --scenario support-edit --verify-trace
```

The helper checks expected tool/store outcomes, flushes callbacks and reads back
completed hosted traces. Support scenarios use fresh temporary stores and fixed
reviewer decisions. Rejection has no executed support-write tool span. Without
`--verify-trace`, hosted ingestion is not asserted. Review final wording alongside
tool evidence; these commands do not exhaustively grade every answer claim or
replace a browser walkthrough. See [evaluation](EVALUATION.md) for repeated trials.

## Audit scope and validation fix

Reviewed every maintained Python module and test module, application/server
configuration, input/tool contracts, SQL, support transactions, evaluation runner
and graders, pinned data, historical experiment archives, and operational documentation.

**Fixed: oversized runtime customer IDs caused an unhandled SQLite overflow.**
`CustomerContext(2**63)` previously passed validation, then failed during database
parameter binding. Customer IDs now require an actual integer between 1 and
`2**63 - 1`. Invalid server context fails before model execution. There was no
cross-customer disclosure in the reproduction. Regression coverage includes
constructor rejection, server-dictionary rejection before the model, and a valid
maximum-integer lookup returning no records.

The validation fix changed only `src/agent/context.py` and two test files.
That fix preserved model instructions, tool descriptions, SQL/ranking, approval
policy and provider configuration. The existing module boundaries are coherent; this
audit found no need for file merging, a custom agent loop or new abstractions.

## Latest verification results

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

The credential scan compared configured secrets with publishable files and ZIP
contents. It does not establish the absence of arbitrary historical or unknown
credentials.

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

The existing Studio support-store bytes remained unchanged. The audit created
five local threads tagged with `purpose=musicchain-code-audit`. These local runtime
threads are not included in the repository.
Server outputs and scores are saved in
[the audit evidence](../artifacts/audit/20260924/server-results.json).

API behavior was checked against the installed SDK and official
[local development](https://docs.langchain.com/langsmith/local-dev-testing) and
[server human-review](https://docs.langchain.com/langsmith/add-human-in-the-loop)
documentation.

## Installation verification

An independent fresh clone from GitHub was installed into a new, credential-free
Python 3.12 environment on macOS on 2026-09-24. Installation from `requirements.lock`,
editable project installation, the pinned database build, all 139 tests, Ruff
lint/format and `pip check` passed. No `.env`, SQLite stores or checkpoints arrived
in the clone. The local Agent Server also completed a real invoice-98 lookup.

Other platforms remain unverified. The dependency snapshot is not a cross-platform,
hash-verified lock; the data-path design targets an editable checkout rather than
a standalone wheel.

## Known limits

- Studio simulates trusted identity. Real customer/reviewer authentication and
  thread/checkpoint authorization are not implemented. SQL scoping cannot protect
  another customer's messages in a reused thread.
- Approval gates the agent tool path. Internal persistence functions are not
  independently authenticated service endpoints. Cases are mock records; no
  refund, external ticket, closing/reopening flow or tamper-proof ledger exists.
- Recommendations use a transparent heuristic and dataset-specific allowlists.
  Subjective taste and every free-text model claim are not evaluated.
- Expected database errors become safe tool statuses. Provider/network failures
  can still fail a run after retries. Recorded evidence is not proof of a new run.
- The 15-case, two-repetition comparison is historical evidence. It was not rerun
  after the runtime-ID validation fix. The later smoke checks are separate evidence.
- The latest server audit exercised the API used by Studio, not a fresh manual
  browser walkthrough. Earlier browser checks are recorded below.

## Historical browser and live checks

The following records describe their dated checkpoints, not the current suite size.
The original purchase, discovery and support checkpoints had 40, 65 and 99 passing
offline tests respectively. The evaluation checkpoint had 136; the current suite
has 139. Historical identifiers and observed outputs are preserved.

### Purchase support — 2026-09-23

#### Live model and tracing

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

#### Studio walkthrough

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

### Music discovery — 2026-09-23

#### Real model and hosted tracing

All three helper scenarios passed with the configured `openai:gpt-6-luna`, using
`reasoning_effort="none"` on Chat Completions. Each helper verified expected tool
records, flushed callbacks and read successful model/tool spans from hosted
LangSmith. Final wording was reviewed separately.

| Scenario | Observed result | Hosted trace |
| --- | --- | --- |
| Recommendations | IDs 1146, 1147, 1148: Welcome to the Jungle, It's So Easy, Nightrain; evidence: 14 owned Rock tracks and 6 Guns N' Roses tracks. Answer distinguished purchases from liking. | [Passed](https://smith.langchain.com/o/5f568ee9-1df1-4bb1-b236-8b92e9002c82/projects/p/e3f1f3f8-5d27-452c-b044-fdb61ecf2fa6/trace/3742a4ec-eebb-4a9f-9b08-233aa4ba8fc1/run/3742a4ec-eebb-4a9f-9b08-233aa4ba8fc1) |
| Catalog | Miles Davis/Jazz IDs 597, 598, 599: Now's The Time, Jeru, Compulsion. | [Passed](https://smith.langchain.com/o/5f568ee9-1df1-4bb1-b236-8b92e9002c82/projects/p/e3f1f3f8-5d27-452c-b044-fdb61ecf2fa6/trace/0e5726e2-147e-4ef5-985b-ef3ce62ab940/run/0e5726e2-147e-4ef5-985b-ef3ce62ab940) |
| Purchase regression | Invoice 98 still returns the correct two items, date and total 3.98, without invented currency. Answer now calls them video episodes. | [Passed](https://smith.langchain.com/o/5f568ee9-1df1-4bb1-b236-8b92e9002c82/projects/p/e3f1f3f8-5d27-452c-b044-fdb61ecf2fa6/trace/404cab9b-7627-4516-9e57-2bcfa8ca1f39/run/404cab9b-7627-4516-9e57-2bcfa8ca1f39) |

The existing project is still named `chinook-support-phase1`; phase-specific run
names/tags distinguish the new work. Trace links require workspace access; no
public sharing was enabled.

#### Studio walkthrough

Used the connected local server and the saved customer-1 assistant in a **new**
thread: `01a0d0d3-8fcb-7db0-bf32-4fca42490108`. The historical Phase 1 threads remain
separate. Four requests were submitted through Studio and their answers reviewed:

| Request | Observed behavior | Hosted trace |
| --- | --- | --- |
| Three unowned Rock tracks | Returned 1146–1148 with accurate 14/6 evidence counts. | [Passed](https://smith.langchain.com/o/5f568ee9-1df1-4bb1-b236-8b92e9002c82/projects/p/e3f1f3f8-5d27-452c-b044-fdb61ecf2fa6/trace/01a0d0d3-8fec-7a61-832b-5b9a22813dc9/run/01a0d0d3-8fec-7a61-832b-5b9a22813dc9) |
| Three unowned Opera tracks | Returned only ID 3451 and explained the shortage; did not invent two more or relax the genre. | [Passed](https://smith.langchain.com/o/5f568ee9-1df1-4bb1-b236-8b92e9002c82/projects/p/e3f1f3f8-5d27-452c-b044-fdb61ecf2fa6/trace/01a0d0d4-2f05-7c71-8db6-013f5a57a621/run/01a0d0d4-2f05-7c71-8db6-013f5a57a621) |
| TV Shows, with instruction to treat them as music | Model called `recommend_music(genre="TV Shows", limit=3)`. SQL returned `no_matching_unowned_music` and zero candidates; answer gave no recommendations. | [Passed](https://smith.langchain.com/o/5f568ee9-1df1-4bb1-b236-8b92e9002c82/projects/p/e3f1f3f8-5d27-452c-b044-fdb61ecf2fa6/trace/01a0d0d5-0163-78f1-9b11-def88c1ab667/run/01a0d0d5-0163-78f1-9b11-def88c1ab667) |
| Miles Davis Jazz catalog search | Returned IDs 597–599 with correct titles, without claiming they were unowned. | [Passed](https://smith.langchain.com/o/5f568ee9-1df1-4bb1-b236-8b92e9002c82/projects/p/e3f1f3f8-5d27-452c-b044-fdb61ecf2fa6/trace/01a0d0d6-44be-7ef2-84a5-0d8ae1560ce1/run/01a0d0d6-44be-7ef2-84a5-0d8ae1560ce1) |

The hosted trace view showed all four turns, model/tool spans, arguments and
results, including the Opera result's `requested_genre` basis with zero relevant
history counts. The catalog result explicitly reported `ownership_checked: false`.

Studio is a trusted local operator surface with simulated identity. Production
authentication and thread/checkpoint authorization remain outside this demo.

### Reviewed support requests — 2026-09-24

#### Live helper and hosted traces

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

#### Studio and persisted case evidence

Used the saved customer-1 assistant, with new support-workflow threads. Studio showed the
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
At that checkpoint, the gitignored store retained the two successful cases.
Repeating those requests against that unchanged store returns `already_exists` after review, preserving their reasons.

The first Studio edit submission reached the server with only `type: edit`, missing
`edited_action`, and failed before any write (run
`01a0d447-bea5-76a3-823f-34738519b4c3`). Retained this evidence. A fresh thread and
pasting/verifying the complete value before clicking Resume succeeded; the recorded
server command contained the full edited action. Rapid typing/submission also
produced one empty-message diagnostic run. This is an observed UI-entry timing
issue, not an authorization bypass; the precise frontend cause was not established.
See [friction log](../FRICTION_LOG.md).
