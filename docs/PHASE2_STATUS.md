# Phase 2 verification — 2026-09-23

**Purchase support, catalog search and grounded unowned music recommendations are
implemented and verified offline and live.** These are bounded checks, not a
completed model evaluation suite or a production-readiness claim.

## What changed

- Added `search_music_catalog` for literal catalog search and exact genre filtering.
- Added `recommend_music` for customer-specific recommendations. SQL excludes all
  owned tracks using full purchase history, restricts candidates to music, and
  returns the genre/artist purchase counts used to rank them.
- Extended the existing context, database, tool and prompt modules. The agent is
  still one `create_agent()` loop with a shared four-tool-call limit. No new runtime
  dependencies or application layers were added.
- Extended the live verifier with catalog and recommendation scenarios; added
  `tests/test_discovery.py` and runtime tests for the new tools.

## Offline verification

**65 tests pass** on Python 3.12; lint and formatting checks pass. The suite retains
Phase 1 authorization checks and adds:

- Independent ownership and purchase-count checks for all 59 customers.
- Full catalog pagination over 3,289 music tracks, with canonical catalog fields.
- Music filtering that rejects video even when its genre is Alternative, plus
  unknown/missing classifications and audio tagged as non-music.
- Literal search, exact genres, strict limits, duplicate-purchase handling,
  old-invoice ownership exclusion, video-only history and exhausted genres.
- Hidden customer identity, forged argument/chat identity attacks on recommendations,
  mixed parallel tool batches, and database failure handling for all three tools.

Fixtures with modified purchase history use temporary database copies. The runtime
Chinook database remains read-only.

## Real model and hosted tracing

All three commands below passed with the configured `openai:gpt-6-luna`, using
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

## Studio walkthrough

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

## Limitations and next boundary

- Ranking uses distinct genre/artist purchase counts and track-ID tie-breaking.
  It can return several tracks from one artist/album, as observed for customer 1.
  Artist diversity and subjective quality need later evaluation.
- Genre names are exact matches; search is a literal substring, not semantic
  retrieval. Classification allowlists must be reviewed if the dataset changes.
- Catalog search does not check ownership. Only `recommend_music` makes the
  unowned-candidate guarantee.
- The live helper checks expected tool records and completed traces, not every
  final-answer claim. The Studio walkthrough is a small manually reviewed sample.
- Support writes and human approval (Phase 3), a LangSmith evaluation dataset and
  baseline/improvement comparison (Phase 4), and interview polish (Phase 5) remain.

That list records the Phase 2 boundary. Phase 3 was subsequently implemented and
verified; see [Phase 3 status](PHASE3_STATUS.md). Phases 4 and 5 remain future work.

## Reproduce

```sh
source .venv/bin/activate
python -B -m pytest -q -p no:cacheprovider
ruff check --no-cache .
ruff format --check --no-cache .
python -B -m scripts.verify_live --verify-trace
python -B -m scripts.verify_live --scenario catalog --verify-trace
python -B -m scripts.verify_live --scenario recommendations --verify-trace
langgraph dev --no-browser
```

The live commands use configured services and incur normal model usage. See the
[architecture walkthrough](ARCHITECTURE.md) for file ownership, ranking rules and
Studio setup, and [friction log](../FRICTION_LOG.md) for observed implementation issues.
