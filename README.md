# MusicChain

A Python customer-support agent for a fictional digital music store, built with
LangChain `create_agent()`, LangGraph and LangSmith. MusicChain uses the pinned
Chinook sample dataset and runs locally through LangSmith Studio.

One agent supports three workflows:

- **Purchase support:** retrieve invoice details and purchase history scoped to
  the customer supplied by trusted runtime context.
- **Music discovery:** search the catalog and recommend unowned music, with an
  optional constraint for different artists.
- **Reviewed support requests:** pause for human approval, edits or rejection
  before saving a case in a separate mock store.

Python owns input validation, SQL and authorization. Chinook stays read-only.
Support cases are local records; no refunds or external tickets are issued.

## Quickstart

Use Python 3.12 for the verified setup (the package declares Python 3.11–3.13).
Repository access is required while the GitHub repository is private.

```sh
git clone https://github.com/realvivekganta/MusicChain.git
cd MusicChain
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.lock
python -m pip install --no-build-isolation --no-deps -e .
python -m scripts.build_database
cp -n .env.example .env
```

Set `OPENAI_API_KEY` and `LANGSMITH_API_KEY` in the gitignored `.env`. Configure
LangSmith endpoint/workspace settings if required by your account. The default model
is `openai:gpt-6-luna`, overridable with `SUPPORT_MODEL`. Its tool-calling configuration
is explained in [architecture](docs/ARCHITECTURE.md#what-the-frameworks-handle).

```sh
langgraph dev --no-browser
```

Open [Studio](https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024),
select `support`, set **Customer Id** to `1` in **Manage Assistants**, and start a
new thread. Ask **“What's on invoice 98?”** The [walkthrough](docs/WALKTHROUGH.md)
covers purchase isolation, recommendations and support approval payloads.

Studio provides simulated identity for a trusted local operator. It is not a
customer login system. Keep separate threads for each customer; a production
adapter must authenticate callers and authorize thread/checkpoint access.

## Project map

```text
app.py                     Agent Server entry point
langgraph.json             Maps the support graph to app.py:agent
src/
  agent/
    agent.py               Model, tools, prompt and middleware assembly
    system_prompt.py       Model instructions
    context.py             Trusted identity and validated business inputs
    tools.py               Four model-facing business capabilities
    database.py            Read-only Chinook queries and recommendation ranking
    support_store.py       Reviewed mock cases and transactional deduplication
  scripts/
    build_database.py      Build Chinook from the pinned SQL snapshot
    verify_live.py         Real-model smoke checks and hosted trace verification
  evals/
    runner.py              Isolated trials, LangSmith publishing and snapshots
    evaluators.py          Deterministic checks against data and execution evidence
  data/                    SQL source, provenance, license and evaluation cases
tests/                     Offline data-boundary and graph-runtime tests
docs/                      Scope, architecture, walkthrough and verification
artifacts/                 Preserved evaluation and audit evidence
```

Generated databases live in `src/data/` and are gitignored. Each agent module owns
a distinct part of the request flow. Read **app → agent → tools → database/support
store** alongside the prompt and context definitions. LangChain supplies the
model/tool loop; LangGraph supplies execution and checkpoints. Developer scripts
and evaluators are not tools exposed to the agent.

## Verify and evaluate

Offline tests require no credentials and use temporary databases:

```sh
pytest -q
ruff check .
ruff format --check .
```

Live verification calls configured services and checks hosted trace ingestion:

```sh
python -m scripts.verify_live --verify-trace
```

The [verification guide](docs/VERIFICATION.md) lists all six smoke scenarios and
recorded results. A separate evaluation command runs 15 cases twice:

```sh
python -m evals.runner --label my-experiment --repetitions 2
```

The recorded comparison improved case success from **28/30 to 30/30**, addressing
an explicit artist-variety request. These are 15 cases repeated twice, not a
production reliability estimate. See [evaluation methodology and evidence](docs/EVALUATION.md).

As of 2026-09-24, **139 offline tests**, lint, formatting, six live/hosted-trace
checks and five Agent Server API scenarios passed. A fresh GitHub clone installed,
built its database and passed the offline suite on macOS/Python 3.12. The dependency
snapshot is not a cross-platform, hash-verified lock. The supported setup is an
editable checkout, not a standalone application wheel.

## Documentation

| Document | Purpose |
| --- | --- |
| [Project scope](docs/PROJECT_SCOPE.md) | Requirements and intentional boundaries |
| [Architecture](docs/ARCHITECTURE.md) | Component ownership, request flow and security model |
| [Walkthrough](docs/WALKTHROUGH.md) | Runnable examples and expected outcomes |
| [Verification](docs/VERIFICATION.md) | Offline, live and historical evidence; known limits |
| [Evaluation](docs/EVALUATION.md) | Baseline, measured improvement, graders and reproducibility |
| [Friction log](FRICTION_LOG.md) | Observed engineering problems and resolutions |
| [Contributor instructions](AGENTS.md) | Implementation and documentation conventions |
