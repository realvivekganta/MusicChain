# Architecture

MusicChain combines purchase support, music discovery and reviewed mock support
requests in one LangChain agent. See [scope](PROJECT_SCOPE.md) for requirements,
[walkthrough](WALKTHROUGH.md) for examples and [verification](VERIFICATION.md) for evidence.

## What this project does today

This is a Python support agent for MusicChain, a fictional digital media store
using the Chinook sample dataset. A
customer can ask about recent purchases, a particular invoice, or purchased
tracks matching an artist, album or track name. They can also search the music
catalog and request unowned recommendations grounded in their purchase history.

| Tool | Purpose | Ownership behavior |
| --- | --- | --- |
| `get_my_purchases` | Purchase lines, invoice lookup and purchase search | Always scoped to trusted customer |
| `search_music_catalog` | Find music by literal track/album/artist search and optional genre | Public catalog; makes no ownership claim |
| `recommend_music` | Rank eligible unowned music using genre/artist purchase counts | Full customer history determines counts and mandatory exclusions |
| `create_support_request` | Create a local mock case after approve/edit review | Fresh invoice/customer ownership check after review; one case per customer/invoice |

OpenAI interprets the question, chooses tool arguments and writes the answer.
Python validates the inputs and restricts the query to the caller's customer ID.
The system prompt tells the model to base factual claims on tool results;
authorization and recommendation eligibility are enforced independently in code.
Support cases are mock local records; no actual refunds or external ticket
submission is implemented. A separate [evaluation workflow](EVALUATION.md) measures
objective behavior and preserves the baseline-to-improvement comparison.

## What the frameworks handle

| Component | Responsibility in this project | Code we still own |
| --- | --- | --- |
| LangChain | `create_agent()` supplies the model/tool loop; `@tool` describes tools; middleware validates context, limits calls and pauses writes for review | Prompt, business tools, input/identity validation and approval policy |
| LangGraph | Executes the graph returned by `create_agent()`; the local Agent Server supplies thread checkpointing | Passing trusted context and keeping customer threads separate |
| LangSmith | Studio provides the operator interface; hosted traces expose model and tool execution when enabled | Trace configuration, verification, evaluation cases and deterministic graders |
| OpenAI | Provides the configured language model | Model choice and instructions |
| Pydantic and SQLite | Validate business filters and execute parameterized queries | Input constraints, SQL, ownership checks, ranking and result formatting |

This keeps us from writing our own model/tool dispatch loop, graph runner or
debugging UI. We configure those pieces and concentrate on the store's behavior.
The factory in `agent.py` assembles the agent; it does not implement a custom loop.

The default model is `openai:gpt-6-luna`, configurable through `SUPPORT_MODEL`.
For Luna, the factory sets `reasoning_effort="none"` because its function calling
on Chat Completions requires that setting. This preserves the existing endpoint
and non-reasoning execution; using reasoning with tools would require Responses.
See the [official model documentation](https://developers.openai.com/api/docs/models/gpt-6-luna).

## How the files fit together

`src/` groups application code (`agent/`), developer commands (`scripts/`) and the
evaluation commands (`evals/`) and local dataset (`data/`). Tests and documentation live at the repository root.
The application is one Python package, `src/agent/`. `agent.py` builds the agent;
LangChain's `create_agent()` supplies its loop. The `support` graph name in
`langgraph.json` points to root-level `app.py`, which constructs the provider-backed graph
for the local server. The Python distribution is still named `chinook-support`;
its import package is `agent`.

| File | Owns | Change it when… |
| --- | --- | --- |
| `app.py` (root) | Constructs and exports the configured agent for the server | The application entry point changes |
| `src/agent/agent.py` | `build_agent()`, provider setup, tool registration and middleware | Adding a tool or changing execution controls |
| `src/agent/system_prompt.py` | Model instructions for grounding, scope and wording | Changing how the agent should respond |
| `src/agent/tools.py` | Four model-facing capabilities and runtime-context injection | Changing what the model can request or how tool errors are returned |
| `src/agent/context.py` | Immutable `CustomerContext`, identity validation and query/action input models | Changing trusted runtime context or allowed business inputs |
| `src/agent/database.py` | Read-only connections, purchase/catalog SQL, recommendation eligibility and ranking | Changing data access, candidate policy or returned evidence |
| `src/agent/support_store.py` | Separate writable case store, fresh ownership checks, transactions and deduplication | Changing support persistence or case policy |
| `src/agent/__init__.py` | Python package marker and orientation docstring | Package-level documentation changes |

`context.py` keeps the constraints in one place while the tool retains an inferred
signature schema. This preserves runtime injection and also lets ordinary Python
callers construct a validated `PurchaseQuery` without involving LangChain.
Trusted identity and model-selected filters share this module because both define
inputs used across the application. Clearly labeled sections preserve the
distinction between their sources without requiring another small file.
The module is named `context.py` by project convention and contains both runtime
context and tool-input validation; it does not assemble a prompt or fetch data.
For example, the caller supplies `CustomerContext(customer_id=1)` while the model
may supply `invoice_id=98`. `PurchaseQuery` has no customer-ID field. Calling this
file `guardrails.py` would obscure its specific purpose: safeguards also live in
the context validator, agent middleware and database query.
Runtime customer IDs must be actual integers in SQLite's positive signed-64-bit
range; oversized values are rejected before the model or database runs. This
validates the identity's shape, not the caller's authentication.

`src/scripts/` contains developer commands, not model-callable tools.
`build_database.py` prepares the dataset and is reused by test fixtures;
`verify_live.py` exercises the real provider and optionally verifies a hosted
trace. `src/data/` contains the vendored SQL, provenance/checksum, license and
generated SQLite database. It is data, not Python source; grouping it under
`src/` is this repository's organizational choice. The current setup targets
running from an editable checkout, not distributing a standalone application wheel.

The flat package is intentional: there is one agent and four business tools today.
Separate folders for tools or persistence can be introduced when they contain
enough distinct implementations to make navigation easier. For now, no service,
repository, manager, or context-builder layers are needed.

### Documentation conventions

Every maintained Python module starts with a purpose docstring. Every function,
method and class has a docstring explaining its contract: short for a small helper
or test, fuller where inputs, returned evidence, side effects, failures or trust
boundaries need explanation. Test docstrings identify the guarantee being checked.
Labeled `# --- Section name ---` dividers group related responsibilities; long
approval/evaluation flows also mark their meaningful internal stages. Inline
comments explain decisions such as pagination look-ahead or transaction ordering.

Tool docstrings are also model-visible descriptions generated by LangChain, and
`SYSTEM_PROMPT` is sent to the model. Editing either can change behavior. Keep
maintainer commentary outside those texts unless deliberately changing the agent.

Markdown uses native headings. TOML, ignore rules and `.env.example` use comments
where the format supports them. JSON remains strict JSON; its role is documented
here instead of adding invalid comment syntax:

| File | Meaning |
| --- | --- |
| `langgraph.json` | `dependencies` installs the local project, `graphs` maps `support` to `app.py:agent`, and `env` identifies the server's local configuration file |
| `src/data/source.json` | Upstream SQL URL/version, retrieval date, checksum verified by the builder, and license URL |
| `src/data/eval_cases.json` | `inputs` supplies fixture identity, prompt and optional reviewer decision; `outputs` supplies grader-only expected contracts |
| `artifacts/phase4/*/manifest.json` | Historical model/configuration, source/data/grader hashes, experiment link and score totals |
| `artifacts/phase4/*/results.json` | Historical per-trial case/run IDs, outputs, errors and metric scores |

Vendor SQL/license text, dependency pins, generated databases/checkpoints and
archived experiment snapshots retain their original content. Documentation changes
to maintained source can change its byte hashes; archived hashes continue to
identify the exact versions actually evaluated, not a later annotated checkout.

## Purchase request flow

For a trusted local operator using customer 1 and asking “What's on invoice 98?”:

1. At server startup, `langgraph.json` loads `app.py:agent`. That calls
   `build_agent()` to assemble the model, prompt, tools and middleware.
2. The operator sends the message with `CustomerContext(customer_id=1)` supplied
   separately. Middleware rejects missing or invalid context before any model call.
3. The model receives the prompt, messages and public tool schema. A typical call
   is `get_my_purchases(invoice_id=98)`; customer identity is not a tool argument
   the model controls.
4. LangChain dispatches the call, subject to the four-call limit, and injects
   runtime context. `tools.py` validates identity and constructs `PurchaseQuery`.
5. `database.py` binds both customer 1 and invoice 98 into the query. It returns a
   structured result with invoice lines, status and pagination metadata.
6. The tool result becomes a message in the conversation. The model can request
   another lookup or produce the final answer. With tracing configured, the run
   also emits model and tool execution details to LangSmith.

Invoice 98 belongs to customer 1 and contains two video line items. With customer
2's context, the same lookup returns `no_authorized_records`. Writing “I'm customer
2” in chat does not change the trusted context.

```mermaid
flowchart LR
    Context[Trusted CustomerContext] --> Gate[Validate context]
    Chat[Customer message] --> Gate
    Gate --> Model[Model: choose tool or answer]
    Model --> Limit[Tool-call limit]
    Limit --> Tool[get_my_purchases]
    Context --> Tool
    Tool --> SQL[Parameterized SQL with CustomerId predicate]
    SQL --> DB[(Read-only Chinook)]
    DB --> Tool
    Tool --> Model
    Model --> Answer[Final answer]
    Model -. traces .-> LS[LangSmith]
    Tool -. traces .-> LS
```

- **Cognitive architecture:** a bounded model/tool loop, not an open-ended planner.
  The model chooses business tools and filters; deterministic code decides accessible
  records and eligible recommendations. Deep Agents would fit more complex planning, context/filesystem
  management and delegation; those capabilities add no necessary value here.
- **State vs context:** standard agent messages plus framework tool-limit/review state
  are state. `CustomerContext(customer_id=...)` is a frozen invocation context,
  injected into `ToolRuntime`, excluded from the model-facing schema. Missing or
  invalid context fails before the model. Pass context on every invocation.
- **Authorization:** the sole purchase query always applies `i.CustomerId =
  :customer_id`; invoice filtering is an additional predicate. Missing and foreign
  invoices have the same empty result. User text cannot override the context.
- **Read-only data:** file mode 0444, SQLite URI `mode=ro`, and `query_only=ON`.
  Tests prove URI protection still works with writable file permissions and with
  `query_only` disabled. Every connection is closed after use.
- **Bounded output:** 20 line items by default, at most 50; one extra row detects
  pagination. Search is a literal track/album/artist substring. Sort order includes
  invoice and line IDs for stable paging. Prices are decimal strings; Chinook has
  no currency code, so the tool does not invent one. Invoice totals repeat on each
  line and must not be summed. A page does not prove complete album ownership.
- **Reliability:** four tool proposals per invocation and twenty per thread, with
  explicit termination when exceeded. The run counter resets on interrupt resume;
  the persisted thread cap bounds repeated review cycles. Counts include rejected
  proposals. Limits are shared across all four tools. Full-graph tests verify mixed-tool
  batches; installed LangChain cancels the entire pending batch when it exceeds
  the limit, preserving valid tool-response messages. No custom retry middleware:
  the model has a 30-second
  timeout and one SDK retry. Database outages return a distinct structured status.
- **Data minimization:** tool results omit customer names, email and billing details.
  With tracing enabled, messages and purchase tool outputs are sent to LangSmith.
  This repository uses public fictional sample data.

## Controlled support action

The model proposes `create_support_request(invoice_id, reason)`. HITL middleware
pauses before tool execution and exposes the arguments for operator review. No
support record exists yet. `approve` runs the proposed action; `edit` runs the
reviewed arguments; `reject` skips it and returns rejection feedback to the model.
Only these three decision types are enabled. Normal chat cannot provide approval.

At execution, the tool validates the final invoice/reason and requires trusted
runtime context again. `support_store.py` uses `database.owns_invoice` to recheck
the invoice against that customer, independently of earlier lookups or human
approval. Missing and foreign invoices return `no_authorized_records` identically.

The separate `src/data/support.sqlite` file is created on the first authorized
execution. `SUPPORT_DB_PATH` can override its location. Direct paths, symlinks and
hardlinks to Chinook are rejected. A transaction creates the schema if needed,
inserts an open case, and reads it back. A unique customer/invoice constraint makes
retries and concurrent submissions return the same case without replacing its
original approved reason. Results distinguish `created` and `already_exists`, and
include case ID, invoice, reason, timestamp, open status and explicit mock/no-refund
flags. No creation success is returned before commit. Database failures return
`temporarily_unavailable` without assuming that an uncertain commit failed.

Middleware ordering matters: `after_model` hooks run in reverse registration
order, so the tool limit runs before human review. An over-limit batch is cancelled
without asking for approval or writing cases. A mixed read/write batch pauses as a
unit before its tools; a read-only batch runs autonomously.

The Agent Server supplies checkpoints for Studio. Standalone support tests/helpers
inject `InMemorySaver`. Every resume must supply the same trusted customer context
and thread ID. Missing context at execution fails closed; the before-agent hook
is not rerun as an authorization mechanism on resume. The caller must enforce
customer/thread binding and reviewer access. This local operator demo has no
production authentication or thread ACL. Calling the internal persistence function
directly also bypasses the agent's approval gate; it is not a public application API.

There is no case-closing/reopening flow, external ticket system, refund execution
or reviewer identity ledger. LangSmith/checkpoints provide demo review evidence,
not a tamper-proof compliance audit log.

## Music discovery flow and policy

For “I liked the rock music I've bought. Recommend three tracks I don't already
own,” the model calls `recommend_music(genre="Rock", limit=3)`. LangChain injects
the trusted customer context. The tool validates filters and asks `database.py`
for candidates; no preliminary purchase lookup or model-written SQL is needed.

1. Within a single read snapshot, SQL finds the customer's complete purchase
   history, including old invoices. Distinct track IDs prevent repeat purchases
   from inflating the evidence counts.
2. A shared music query requires both a known audio media type (IDs 1, 2, 4, 5)
   and a music genre (IDs 1–17, 23–25). These allowlists belong to the pinned
   Chinook 1.4.5 snapshot. Video, TV, unknown and missing classifications are excluded.
3. `NOT EXISTS` removes every previously purchased track. The model cannot disable
   this rule. An explicit genre is an exact, case-insensitive hard filter; without
   one, candidates must belong to a previously purchased music genre.
4. Candidates sort by distinct owned tracks in their genre, then distinct owned
   tracks by their artist, both descending. Track ID breaks ties deterministically.
   The default is three results, with a maximum of ten.
5. Each result includes canonical catalog metadata, genre/artist evidence counts
   and its basis (`purchase_history` or `requested_genre`). The model explains
   these facts without inventing musical attributes or treating purchases as proof
   of liking. It only recommends returned candidates.

With no music history and no stated genre, `needs_genre_preference` asks the model
to request a genre. An explicit genre allows honest genre-based suggestions even
without relevant history. Empty results use `no_matching_unowned_music`; a short
list is returned as-is, without filling it with owned or out-of-genre tracks.
For example, customer 1 has only one eligible Opera track in this catalog.

`search_music_catalog` uses the same music eligibility query, literal substring
search over track/album/artist and optional exact genre matching. It pages by track
ID (20 results by default, maximum 50). Its `ownership_checked: false` flag makes
clear that catalog matches may already be owned; they cannot substitute for the
recommendation tool when the user requests unowned music.

The default transparent ranking still gives customer 1 three Guns N' Roses tracks
from one album. When the user requests varied/different artists, the model passes
`different_artists=True`. SQL ranks candidates within each artist, keeps each
artist's best eligible track, then applies the same global ranking and limit.
Customer 1's varied Rock list is tracks 1146 (Guns N' Roses), 436 (Kiss) and 2093
(Ozzy Osbourne). Too few eligible artists produces a shorter list; it never relaxes
ownership, music eligibility or the requested genre. This is an explicit artist
constraint, not a subjective recommendation-quality or album-diversity optimizer.
There are no embeddings, external music APIs, extra agent layers or new dependencies.

## Running and evaluating the application

The [walkthrough](WALKTHROUGH.md) covers Studio setup, customer-scoped examples,
approval payloads and trace inspection. The [verification guide](VERIFICATION.md)
lists offline and live checks. The [evaluation guide](EVALUATION.md) explains
isolated trials, deterministic graders, source snapshots and measured results.

## Dataset notes

The authoritative SQL snapshot is Chinook **1.4.5**, SHA-256 recorded in
`src/data/source.json`. It contains 59 customers, 412 invoices, 2,240 invoice lines,
3,503 tracks, 347 albums, 275 artists and 25 genres. Relevant relationships:

`Customer → Invoice → InvoiceLine → Track → Album → Artist`, with Track also
referencing Genre and MediaType. Track album/genre associations are nullable, so
the query uses left joins to avoid losing legitimate purchases. Invoice 98 is
non-music video content; purchase support returns it accurately. Discovery now
filters music separately: 3,289 eligible music tracks out of 3,503 total. A video
with genre Alternative demonstrates why both media and genre filtering matter.
Customer 1 has
no Miles Davis purchases, so that prompt is a useful honest empty-result case.

The builder validates the vendored source checksum, SQLite integrity and foreign
keys, then creates the target without overwriting an existing database. Re-running
the command leaves an existing target unchanged; it does not revalidate that file.
Tests build a fresh independent database from the same source. Updating the source
requires an intentional new checksum, refreshed fixture facts and test run.

## Official documentation consulted

- [Using the docs programmatically](https://docs.langchain.com/use-these-docs)
- [Agents and create_agent](https://docs.langchain.com/oss/python/langchain/agents)
- [Runtime context](https://docs.langchain.com/oss/python/langchain/runtime)
- [Tools and ToolRuntime](https://docs.langchain.com/oss/python/langchain/tools)
- [Tool-call-limit middleware](https://docs.langchain.com/oss/python/langchain/middleware/built-in#tool-call-limit)
- [Human-in-the-loop middleware](https://docs.langchain.com/oss/python/langchain/human-in-the-loop)
- [Interrupt and resume semantics](https://docs.langchain.com/oss/python/langgraph/interrupts)
- [Studio local setup](https://docs.langchain.com/oss/python/langchain/studio)
- [Local development server](https://docs.langchain.com/langsmith/local-dev-testing)
- [Tracing LangChain applications](https://docs.langchain.com/langsmith/trace-with-langchain)

- [Evaluate an application](https://docs.langchain.com/langsmith/evaluate-llm-application)
- [Compare experiments](https://docs.langchain.com/langsmith/compare-experiment-results)
