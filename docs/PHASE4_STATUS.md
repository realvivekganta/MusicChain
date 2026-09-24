# Phase 4 — evaluations and measured improvement

Completed on **2026-09-24**. The agent now has a repeatable LangSmith evaluation
workflow and a preserved, measured improvement. **136 offline tests pass**;
Ruff lint/format checks pass. Historical Phase 1–3 evidence remains unchanged.

## Result

The original tool could return three tracks from the same artist even when the
customer requested three different artists. The model accurately described that
limitation, but could not fulfill the request with the candidates it received.

The improvement adds `different_artists=True` to `recommend_music`. The prompt
maps an explicit variety request to this argument. SQL selects each artist's best
eligible track before the final ranking/limit. Default recommendations retain the
original ordering; ownership, music-only eligibility and genre remain mandatory.
No new model, framework, dependency, tool or agent was added.

[Open the hosted comparison: baseline A → candidate B](https://smith.langchain.com/o/5f568ee9-1df1-4bb1-b236-8b92e9002c82/datasets/c7b3b648-0ab9-45a8-aca9-80f196c7573a/compare?selectedSessions=7fd76605-fe36-495a-ba26-fa8547e7427e%2C096157df-6a2c-4bbe-8310-2fb005bac817&source=7fd76605-fe36-495a-ba26-fa8547e7427e).

| Applicable checks | Baseline passed | Candidate passed |
| --- | ---: | ---: |
| Entire case contract | 28/30 | 30/30 |
| Explicit different-artists request | 0/2 | 2/2 |
| Narrow final-answer contract | 29/30 | 30/30 |
| Purchase results | 8/8 | 8/8 |
| Required tool and expected status | 24/24 | 24/24 |
| Catalog grounding / music eligibility / genre | 12/12 each | 12/12 each |
| Unowned recommendations | 8/8 | 8/8 |
| Approval gate and support-store outcome | 10/10 each | 10/10 each |
| Unexpected execution errors | 0 | 0 |

These are **15 cases × two repetitions per version**, not 30 independent customer
scenarios. Both variety failures belong to the same scenario. Baseline overall
success was 93.3%; candidate success was 100% on this suite. All other cases passed
both times. No production reliability or statistical-significance claim is made.

For customer 1, the changed request returned:

| Track | Artist | ID |
| --- | --- | ---: |
| Welcome to the Jungle | Guns N' Roses | 1146 |
| Detroit Rock City | Kiss | 436 |
| Bark at the Moon | Ozzy Osbourne | 2093 |

## Dataset and ownership

`src/data/eval_cases.json` contains inputs and grader-only reference contracts:

| Area | Cases |
| --- | --- |
| Purchases | Owned invoice 98; foreign invoice 1; missing invoice 999999; chat identity-switch attempt |
| Catalog | Three Miles Davis Jazz tracks; literal no-match search |
| Recommendations | Unowned Rock; explicit Jazz; non-music TV Shows exclusion; three different artists |
| Support | Awaiting review; approve; reject; edit invoice/reason; unauthorized customer |

`src/evals/runner.py` owns dataset synchronization, real-agent execution, temporary
stores/threads, fixed reviewer decisions, LangSmith publishing and source artifacts.
`src/evals/evaluators.py` owns deterministic scores against raw Chinook facts and
observed execution evidence. `tests/test_evaluators.py` deliberately corrupts
results to verify that graders reject them, and exercises runner isolation through
the real graph with an offline scripted model.

Only `inputs` reach the target. The target passes the prompt to the model and the
fixture's customer ID to trusted runtime context. References never enter the
conversation. Support decisions simulate a trusted reviewer outside chat. Every
trial gets a fresh thread, in-memory checkpointer and temporary support store;
trials run sequentially because the store path is temporarily environment-driven.
The normal Studio case store is not used or modified by evaluations.

## Preserved experiments and reproducibility

| Version | Hosted experiment | Local evidence |
| --- | --- | --- |
| Initial grader calibration | [phase4-baseline-8be5ee0b](https://smith.langchain.com/o/5f568ee9-1df1-4bb1-b236-8b92e9002c82/datasets/c7b3b648-0ab9-45a8-aca9-80f196c7573a/compare?selectedSessions=ab3eaa30-3cb8-47e7-bcd3-67b352dedb0e) | [Manifest](../artifacts/phase4/20260924T173218Z-baseline/manifest.json) |
| Comparison baseline | [phase4-baseline-normalized-a77cfbe6](https://smith.langchain.com/o/5f568ee9-1df1-4bb1-b236-8b92e9002c82/datasets/c7b3b648-0ab9-45a8-aca9-80f196c7573a/compare?selectedSessions=7fd76605-fe36-495a-ba26-fa8547e7427e) | [Manifest](../artifacts/phase4/20260924T173557Z-baseline-normalized/manifest.json) · [Results](../artifacts/phase4/20260924T173557Z-baseline-normalized/results.json) · [Source](../artifacts/phase4/20260924T173557Z-baseline-normalized/source.zip) |
| Artist-variety improvement | [phase4-artist-variety-ee0a74f9](https://smith.langchain.com/o/5f568ee9-1df1-4bb1-b236-8b92e9002c82/datasets/c7b3b648-0ab9-45a8-aca9-80f196c7573a/compare?selectedSessions=096157df-6a2c-4bbe-8310-2fb005bac817) | [Manifest](../artifacts/phase4/20260924T173957Z-artist-variety/manifest.json) · [Results](../artifacts/phase4/20260924T173957Z-artist-variety/results.json) · [Source](../artifacts/phase4/20260924T173957Z-artist-variety/source.zip) |

The first run exposed false failures caused by smart apostrophes in otherwise
accurate names. It remains preserved, but its 25/30 result is **not** the improvement
baseline. The grader now normalizes typographic quotes and whitespace while still
rejecting altered names. After adding a regression test, the unchanged application
was run again. Only then was artist variety implemented. This separates evaluator
calibration from an application improvement; see [friction log](../FRICTION_LOG.md).

The two comparison manifests have matching:

- Dataset ID: `c7b3b648-0ab9-45a8-aca9-80f196c7573a`.
- Cases SHA-256: `59fde1c8b3d5ce95e297949fe4eb6a0b6803f2e844429b469403716a7ee638c5`.
- Evaluator SHA-256: `a8c705a59bb8a718d9415713af55e42cad4daa489e479f1d3ae6d6a12b42b363`.
- Database SHA-256: `9bd892696e956e57c8cfabd90fcf1675d583ba8e961e968ec53c8da7c08c2669`.
- Dataset version, model `openai:gpt-6-luna`, runner and repetition count.

Source differences are limited to the prompt, tool/input option, recommendation
SQL and related application tests. Each source ZIP includes pinned SQL, dependency
lock and evaluators; it excludes `.env`, SQLite stores and checkpoints. Extract an
old ZIP into a separate directory to rerun that version. Running the command below
in the main project always evaluates the **current** code, regardless of label:

```sh
python -m evals.runner --label my-experiment --repetitions 2
```

## Verification and limits

- Hosted experiment pages show both comparison experiments completed 30/30 runs,
  with feedback scores matching the improvement. The two-experiment comparison
  was opened and inspected in LangSmith, not merely inferred from upload calls.
  Row 14 shows the failing baseline and successful candidate side by side; both
  hosted execution trees show the model, middleware and recommendation tool.
  Direct examples: [baseline trace](https://smith.langchain.com/o/5f568ee9-1df1-4bb1-b236-8b92e9002c82/projects/p/7fd76605-fe36-495a-ba26-fa8547e7427e/trace/01a0d47d-7eda-7a21-bae4-fcd283e6253b/run/01a0d47d-7eda-7a21-bae4-fcd283e6253b)
  and [candidate trace](https://smith.langchain.com/o/5f568ee9-1df1-4bb1-b236-8b92e9002c82/projects/p/096157df-6a2c-4bbe-8310-2fb005bac817/trace/01a0d481-1955-7892-87f6-e914e41cda58/run/01a0d481-1955-7892-87f6-e914e41cda58).
- All 30 candidate answers and both failing baseline variety answers were manually
  reviewed against their tool/store evidence. The varied lists are grounded;
  support approval/edit/rejection wording matches observed outcomes, and negative
  purchase answers do not disclose the foreign invoice's items.
- Offline application checks cover all 59 customers with artist variety both on
  and off, unchanged default ranking, genre shortage, strict boolean validation
  and full-graph option forwarding, alongside existing authorization/HITL tests.
- Automated answer checks are deliberately narrow. Discovery prompts request
  `[track:ID]` markers for unambiguous list extraction. Graders verify selected
  IDs/names and specific disclosure contracts, not every prose statement,
  subjective taste or helpfulness. No LLM judge was needed for this objective
  improvement. A safe refusal without a required lookup can fail task completion
  while still preserving authorization.
- The runner is sequential and local; it is not production customer/reviewer
  authentication, persistent multi-user serving or a concurrent evaluation service.
  Provider behavior can vary across reruns even with identical source/configuration.
- No extra model trials were discarded to make the comparison look better. All
  90 trials (calibration, baseline and candidate) remain in their own experiments.

## Documentation review after the experiments

A subsequent documentation-only pass reviewed all 20 maintained Python modules,
113 functions/methods and six classes. It completed purpose/contract docstrings,
section dividers and boundary explanations, including test fixtures and helpers.
An AST comparison with docstrings removed confirmed unchanged executable
statements and literal SQL/prompt content; all four tool descriptions were also
preserved verbatim. All 136 offline tests and Ruff checks passed afterward.

Current source-byte hashes now differ because of these annotations. The original
experiment ZIPs, manifests, dataset and results remain unchanged; the comparison
above still refers to those exact archived versions. No new live experiment was
needed or claimed for this documentation pass.

## What remains

Phase 5 is now underway under the **MusicChain** presentation name. The native
Google Slides deck and [interview guide](INTERVIEW_DEMO.md) cover the ~35-minute
flow, Studio prompts, trace/evaluation comparison, framework tradeoffs and fallback
evidence. A timed rehearsal and final interview-day preflight remain. No deployment
or custom frontend is needed; the Phase 4 experiment evidence above is unchanged.
