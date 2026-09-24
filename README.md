# MusicChain customer support

A Python customer-support agent for **MusicChain**, the fictional music store in
this exercise, built with LangChain `create_agent()`, running on LangGraph and
using LangSmith Studio as its interface. Chinook remains the underlying dataset.

**Current scope: Phase 5 interview presentation and rehearsal.** Phases 1–4 are
complete. One agent handles
purchase lookup, catalog search, unowned recommendations and mock support requests.
Python controls SQL and customer authorization. Chinook stays read-only; approved
support cases go to a separate SQLite store. No refunds or external tickets are issued.

**139 offline tests pass.** The [end-to-end code audit](docs/CODE_AUDIT.md) records
the latest validation fix, six fresh live/trace checks and five local-server scenarios.
Real GPT-6 Luna approval, rejection and edited-request
checks passed, including Studio and hosted traces. See [Phase 3 evidence](docs/PHASE3_STATUS.md).
Earlier purchase/discovery evidence is preserved
in the [Phase 1](docs/PHASE1_STATUS.md) and [Phase 2](docs/PHASE2_STATUS.md) records.
The [Phase 3 plan](docs/PHASE3_PLAN.md) records the design and implementation decisions.
[Phase 4 evidence](docs/PHASE4_STATUS.md) records the 15-case live comparison:
**28/30 → 30/30** passing trials, with requested artist variety improving from
0/2 to 2/2. This is a small regression suite, not a production reliability estimate.

The [MusicChain interview deck](https://docs.google.com/presentation/d/1cWhNENJtuOZXzw06__CovPJRUEH7ZpUxzWaiYLsiDw4/edit?usp=drivesdk)
contains 13 main slides and four appendices, with a 35-minute walkthrough and
presenter notes. The [rehearsal guide](docs/INTERVIEW_DEMO.md) includes demo prompts,
review payloads, preflight checks and recorded-evidence fallbacks. A timed rehearsal
is still pending.

## Project map

```text
app.py                     Application entry point loaded by the local server
langgraph.json             Maps the support graph to app.py:agent

src/                       Implementation and local dataset
  agent/                   Application code
    agent.py               Wires the model, prompt, tools and middleware together
    system_prompt.py       Instructions for the model
    tools.py               Business capabilities the model can call
    context.py             Trusted customer context and validated tool inputs
    database.py            Read-only purchases, catalog queries and recommendation SQL
    support_store.py       Writable mock cases, fresh ownership checks and duplicate handling
    __init__.py            Marks agent as a Python package
  scripts/                 Developer commands; never exposed to the agent
    build_database.py      Builds the database from the pinned SQL snapshot
    verify_live.py         Checks real model execution and hosted trace ingestion
  evals/                   LangSmith experiments; separate from the running application
    runner.py              Runs isolated cases, publishes scores and saves source snapshots
    evaluators.py          Checks objective contracts against Chinook and execution evidence
  data/                    Chinook source/DB, mock support DB, eval cases, checksum and license

tests/                     Offline authorization and graph-runtime tests
  test_purchases.py        Query scoping, validation, pagination and read-only access
  test_discovery.py        Music filtering, ownership exclusion and ranking evidence
  test_support.py          Storage, approval/resume, edits, rejection and retry safety
  test_agent.py            Runtime injection, identity attacks and tool-call limits
  test_evaluators.py       Grader mutation tests and evaluation-runner isolation
  conftest.py              Shared fixtures; builds a fresh DB and disables tracing

docs/                      Architecture, original brief and verification evidence
artifacts/phase4/          Preserved experiment source, manifests and per-trial results
```

Read **app → agent → prompt → tools → database** to follow the application. The
[architecture walkthrough](docs/ARCHITECTURE.md) explains each file's ownership,
the framework responsibilities and a complete invoice lookup. `context.py` holds
the shared input definitions in two sections: trusted customer context and
model-selected business filters. Identity is supplied by application code and is
never part of the model's tool arguments. No context builder is needed for a
single customer ID.

Module/function docstrings and labeled section dividers explain the code in place.
See the [documentation conventions](docs/ARCHITECTURE.md#documentation-conventions)
for how comments, model-visible instructions and archived evidence are handled.

`agent.py` provides `build_agent()` so tests can inject a scripted model.
Root-level `app.py` calls it with the configured provider. Keeping that small entry point
separate lets tests import the application without credentials or provider calls.
`create_agent()` already supplies the model/tool loop.

`src/scripts/` holds commands you run during development: `build_database.py` prepares
the dataset and is also used by test fixtures; `verify_live.py` checks the real
model and LangSmith trace after setup. They are optional during normal agent
execution. Within `src/`, `agent/` is the running application, `scripts/` contains
developer commands, and `data/` contains dataset files. Run the commands below
from the project root after the editable install; Python imports remain `agent`
`scripts` and `evals`, without a `src.` prefix.

## Setup

Clone the repository and enter the workspace:

```sh
git clone https://github.com/realvivekganta/MusicChain.git
cd MusicChain
```

From the repository root, using Python 3.12 (verified; package supports 3.11–3.13):

```sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.lock
python -m pip install --no-build-isolation --no-deps -e .
python -m scripts.build_database
cp -n .env.example .env
```

Fill `OPENAI_API_KEY` and `LANGSMITH_API_KEY` in your local `.env`. It is gitignored.
`SUPPORT_MODEL` defaults to `openai:gpt-6-luna`. The factory sets
`reasoning_effort="none"` for Luna so tool calls work on Chat Completions, per
[OpenAI's model documentation](https://developers.openai.com/api/docs/models/gpt-6-luna).
Configure your LangSmith endpoint
and workspace ID if required. The local server loads `.env` over shell variables,
including blank values. Existing environments can skip creation and dependency
installation; re-run the editable install after package-layout changes.

## Run and verify

```sh
source .venv/bin/activate
pytest -q
ruff check .
python -m scripts.verify_live --verify-trace
python -m scripts.verify_live --scenario catalog --verify-trace
python -m scripts.verify_live --scenario recommendations --verify-trace
python -m scripts.verify_live --scenario support-approve --verify-trace
python -m scripts.verify_live --scenario support-reject --verify-trace
python -m scripts.verify_live --scenario support-edit --verify-trace
langgraph dev --no-browser
```

The live verification and server commands use configured services; offline tests need no keys.
Open [Studio](https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024),
select `support`, and set **Customer Id** to `1` in **Manage Assistants**.
Start a new thread and ask “What's on invoice 98?”
Then try “I liked the rock music I've bought. Recommend three tracks I don't
already own.” Recommendations exclude every track in the customer's purchase
history and return the counts used to rank them. Ask for “three different artists”
to have SQL select at most one eligible track per artist. Catalog search is separate:
it finds music but does not check ownership.

For support, ask “Please create a support request for invoice 98. Reason: I do not
recognize this invoice.” Studio pauses before the write. Review the proposal and
resume with `{"decisions":[{"type":"approve"}]}` or a reject/edit decision as shown
in the [approval walkthrough](docs/ARCHITECTURE.md#support-approval-in-studio).
`SUPPORT_DB_PATH` defaults to gitignored `src/data/support.sqlite`, created only
when an authorized action executes. Live helper support scenarios use temporary
stores and fixed reviewer decisions; they do not write into your Studio case store.

Studio is a trusted operator interface with simulated authentication. Each
customer needs a separate thread. A real customer-facing adapter must authenticate
callers and authorize thread/checkpoint access; SQL scoping alone does not protect
messages already present in a reused thread.

## Evaluate and compare

```sh
python -m evals.runner --label my-experiment --repetitions 2
```

This runs 15 scenarios twice using the real model, publishes a LangSmith experiment
and saves its source/configuration/results under `artifacts/phase4/`. Support cases
use temporary stores. The command evaluates the current code; the original
baseline is preserved in its source ZIP. See [Phase 4 evidence](docs/PHASE4_STATUS.md)
for experiment links, scores and the limits of this small regression suite.

## Root files and further reading

| File | Purpose |
| --- | --- |
| `app.py` | Constructs and exports the agent for the local server |
| `langgraph.json` | Points the local server to `app.py:agent` |
| `pyproject.toml` | Package definition, direct dependencies and test/lint settings |
| `requirements.lock` | Exact resolved dependencies, including local Studio/test tooling |
| `.env.example` | Configuration template without secrets |
| [AGENTS.md](AGENTS.md) | Durable instructions for coding assistants |
| [FRICTION_LOG.md](FRICTION_LOG.md) | Observed problems and resolutions |
| [Architecture and walkthrough](docs/ARCHITECTURE.md) | Request flow, security boundaries, Studio demo, data notes and official sources |
| [Phase 1 status](docs/PHASE1_STATUS.md) | Live trace evidence, Studio results and limitations |
| [Phase 2 status](docs/PHASE2_STATUS.md) | Catalog/recommendation checks, trace evidence and ranking limitations |
| [Phase 3 plan](docs/PHASE3_PLAN.md) | Support design, file ownership and implementation decisions |
| [Phase 3 status](docs/PHASE3_STATUS.md) | Approval/rejection/edit evidence, saved demo cases and limitations |
| [Phase 4 status](docs/PHASE4_STATUS.md) | Dataset, experiment comparison, source snapshots and evaluation limits |
| [Original brief](docs/PROJECT_BRIEF.md) | Authoritative assignment and scope |

The dependency snapshot was resolved on macOS arm64/Python 3.12; it is not a
cross-platform, hash-verified lock. `.venv/`, caches, `*.egg-info/` and
`.langgraph_api/` are generated local files, not application modules.
