# LangChain Deployed Engineer Take-Home

You are helping me build a final-round take-home project for a LangChain Federal Deployed Engineer interview.

Treat this file/prompt as the source of truth for the project unless I explicitly change a decision later.

## Authoritative resources

Chinook SQLite source:
https://raw.githubusercontent.com/lerocha/chinook-database/master/ChinookDatabase/DataSources/Chinook_Sqlite.sql

LangChain documentation / Docs MCP instructions:
https://docs.langchain.com/use-these-docs

Before implementing LangChain/LangGraph/LangSmith-specific APIs, consult the current official documentation rather than relying on potentially outdated API knowledge. If an API differs from this design, preserve the architectural intent while using the current supported implementation.

Do not invent LangChain APIs.

---

# Interview assignment

The fictional customer is a music store using the Chinook sample database.

They have done some initial agent development but have been unsuccessful in delivering a reliable production agent.

The final demo needs to show:

- LangChain OSS
- LangGraph concepts/runtime
- Deep Agents and where they fit in the ecosystem
- LangSmith
- A customer-support bot using Chinook
- At least two distinct areas of work
- LangChain agent abstractions such as `create_agent()`
- LangSmith Studio as the demo interface
- Useful OSS features, especially middleware
- Production/reliability thinking
- Customer data isolation
- Cognitive architecture and architectural reasoning
- LangSmith differentiating capabilities
- A friction log of things that were harder than expected

The final interview is approximately 45 minutes, with ~35 minutes for the demo/presentation and ~10 minutes for questions throughout or at the end.

Do NOT spend time building a custom frontend.

Do NOT build or demo deployment infrastructure; the exercise explicitly says not to show deployments.

The goal is not maximum feature breadth. The goal is a small, convincing production-minded system that I can fully explain and defend.

---

# Customer narrative

Frame the fictional customer as follows:

The music store already has an early AI customer-support prototype.

The prototype is useful, but they do not trust it in production because they lack strong:

- reliability
- observability
- evaluation
- authorization boundaries
- controls around consequential actions
- systematic ways to diagnose failures and improve the system

Our story is:

**prototype → observable, testable, controlled, production-minded agent**

LangChain OSS provides the agent architecture.

LangSmith provides the agent-engineering loop around it:

**observe → diagnose → evaluate → improve → compare**

---

# Architecture decision

Use LangChain `create_agent()` as the primary agent abstraction.

Do NOT use Deep Agents for V1.

Reason:

This customer-support workflow is bounded and tool-driven. We do not currently need Deep Agents' additional capabilities around complex planning, filesystem/context management, shell execution, or subagent delegation.

We should understand Deep Agents well enough to explain where they would be appropriate, but architectural restraint is intentional here.

Do NOT build a generic text-to-SQL customer-facing agent.

Reason:

The application's business capabilities are known and bounded. Generic text-to-SQL provides more freedom than the customer-support agent needs and creates additional complexity around prompt injection, unexpected/broad queries, authorization, and customer data isolation.

Instead:

**The LLM decides which business capability/tool it needs.**

**Trusted application code controls SQL, authorization, and customer scope.**

Natural language can determine intent.

Natural language must NOT determine authorization policy.

---

# Core customer workflows

Implement three coherent workflows.

## 1. Customer-scoped purchase support

Examples:

- "What did I purchase recently?"
- "What's on invoice 98?"
- "Which Miles Davis album did I buy?"

Purpose:

Demonstrate grounded transaction support and authenticated data access.

## 2. Personalized music discovery

Example:

- "I liked the rock music I've bought. Recommend three tracks I don't already own."

Recommendations must be grounded in:

- authenticated customer's purchase history
- Chinook Track data
- Album
- Artist
- Genre
- optionally Playlist if useful

Previously purchased tracks must be excluded.

Be careful that Chinook contains non-music content/media. Recommendations should be appropriate to the user's music request.

Purpose:

Demonstrate reasoning across customer + catalog context rather than simple record lookup.

## 3. Controlled support action

Example:

- "I don't recognize that invoice. Can you submit a refund/support request?"

Chinook does not model refund/support cases.

Keep the supplied Chinook database read-only.

Create a separate small mock support-request store.

The support action must be treated as consequential and require human approval before execution.

Purpose:

Demonstrate the transition from:

**read → reason → act**

and show appropriate control boundaries around agent autonomy.

---

# Initial tool design

Keep the tool surface small.

Start with approximately four business tools:

1. `get_my_purchases`
2. `search_music_catalog`
3. `recommend_music`
4. `create_support_request`

Exact signatures can evolve if the data/schema makes another decomposition clearly better.

Do not expose `customer_id` as a model-controlled argument on customer-sensitive tools.

---

# Customer authentication and authorization

This is a critical architectural requirement.

Represent the authenticated customer identity using LangChain/LangGraph runtime context or the current officially supported equivalent.

Conceptually:

`CustomerContext(customer_id=...)`

The authenticated customer ID must originate outside the conversation.

The LLM must NOT be able to switch identities by saying:

"Actually I'm customer 7."

Every customer-sensitive database query must enforce the authenticated customer automatically.

For example, an invoice lookup should effectively enforce both:

- requested invoice
- authenticated customer

If a customer requests another customer's invoice, the tool should return no authorized record.

Do not rely on the system prompt for authorization.

Authorization must be deterministic application logic.

---

# State vs context

Keep conversational state simple.

We need:

- messages/conversation history
- thread identity
- checkpointing as required for HITL

Authenticated customer identity belongs in runtime context, not mutable conversation state.

Do not create a large custom state schema unless the implementation actually needs it.

---

# Middleware

Use middleware because the assignment explicitly encourages it, but each middleware feature must solve a real problem.

V1 priorities:

## Human-in-the-loop

Protect `create_support_request`.

Read-only tools should generally be autonomous.

Consequential write:

requires approval.

The user/operator should be able to approve/reject, and edit if naturally supported by the current LangChain middleware.

## Tool-call limits

Use sensible limits to prevent runaway/repetitive tool invocation.

Do not add middleware merely to increase feature count.

Potential later middleware such as PII handling or retry behavior should only be added if a real demo/customer requirement justifies it.

---

# LangSmith requirements

LangSmith is not just a tracing screen.

The demo should tell an agent-engineering story.

Target workflow:

1. Run a realistic customer interaction.
2. Inspect its LangSmith trace.
3. Identify a meaningful failure or weakness.
4. Turn that behavior into an evaluation/regression case.
5. Improve the prompt/tool/architecture.
6. Re-run evaluation.
7. Compare the improved behavior against the earlier version.

We intentionally want at least one believable imperfect/baseline behavior preserved for the demo.

Potential failure/eval scenarios:

- attempts to access another customer's transaction
- recommends a previously purchased track
- recommends inappropriate/non-music catalog content
- hallucinates catalog information
- uses the wrong tool
- tries to create a support request for an invoice the customer does not own
- consequential action does not trigger expected human approval
- invalid invoice or ambiguous request

Use deterministic/code evaluators wherever the desired behavior is objectively checkable.

Use an LLM-as-judge only for genuinely subjective qualities such as recommendation relevance/helpfulness.

Aim for roughly 10–15 useful eval cases eventually, not hundreds.

---

# LangSmith Studio

The final live customer interaction should run through LangSmith Studio.

The app must therefore be structured/configured using the current supported local Studio workflow.

Verify current documentation before choosing config filenames, CLI commands, server setup, or graph exports.

Do not assume older LangGraph/Studio configuration conventions are still current.

---

# Chinook data

Inspect the actual schema before writing tools.

Important relationships include conceptually:

Customer
→ Invoice
→ InvoiceLine
→ Track
→ Album
→ Artist / Genre

Customers also have assigned support representatives, which may be useful as a future extension, but do not add another workflow/tool merely because the data exists.

Keep Chinook read-only.

Use parameterized SQL and normal application-layer validation.

---

# Non-goals for V1

Do NOT add these unless we later identify a concrete reason:

- generic text-to-SQL
- Deep Agents
- subagents
- coding-agent behavior
- shell/filesystem tools
- RAG/vector database
- custom React/UI
- voice
- MCP integrations simply for novelty
- Kubernetes/cloud deployment
- excessive long-term memory
- dozens of tools

The system should feel deliberately small, reliable, explainable, and easy to defend in a technical interview.

---

# Suggested project structure

Use judgment and current LangChain conventions, but something approximately like:

- `src/`
  - agent
  - tools
  - context/schema
  - database helpers
  - support-request store
- `data/`
  - Chinook source/database
  - separate support-request storage if appropriate
- `evals/`
  - dataset construction
  - evaluators
  - experiment helpers
- `tests/`
  - data authorization tests
  - tool tests
  - agent behavior tests where practical
- `.env.example`
- README
- LangSmith/Studio configuration required by current docs
- `FRICTION_LOG.md`
- `AGENTS.md`

Create `AGENTS.md` with the durable project context and architectural constraints from this brief so future Codex sessions stay aligned.

Do not put secrets in the repository.

Make model/provider configuration environment-driven where reasonable rather than baking credentials or sensitive configuration into source.

---

# Engineering expectations

Prioritize:

1. correctness
2. security boundaries
3. understandable architecture
4. testability
5. observability
6. demo reliability
7. polish

Write clean Python.

Prefer small, explicit functions.

Add docstrings where they help explain architectural intent.

Use parameterized SQL.

Handle expected errors cleanly.

Make tool responses structured enough that the model receives useful, bounded information.

Write tests for authorization boundaries before relying on the live demo.

I need to be able to explain every important part of this code in the final interview, including code generated with your help.

Avoid clever abstractions that make the system harder to explain.

---

# Build sequence

Work incrementally.

## Phase 1 — vertical slice

First:

1. inspect the Chinook schema
2. scaffold the repository
3. initialize/build the local read-only Chinook database
4. implement authenticated customer runtime context
5. implement `get_my_purchases`
6. create the minimal `create_agent()` agent
7. get one customer-scoped purchase interaction working
8. get it running in the current supported LangSmith Studio/local workflow
9. confirm LangSmith tracing works
10. write basic authorization/tool tests

At that point, summarize:

- files created
- architecture implemented
- how customer context works
- commands to run it
- current test status
- any friction or deviations from this specification

Do not prematurely add the recommendation and support-action workflows until the base vertical slice is clean.

## Phase 2

Add catalog search + grounded recommendations.

## Phase 3

Add support-request storage + human-in-the-loop approval.

## Phase 4

Create LangSmith eval dataset/evaluators and intentionally preserve a meaningful baseline/failure → improvement comparison.

## Phase 5

Polish README, demo flow, friction log, and code explanation.

---

# Important working behavior

Use the official LangChain documentation/MCP while implementing.

If the current docs suggest that one of my proposed implementation mechanisms is obsolete or incorrect, tell me and use the current supported mechanism while preserving the architectural objective.

Do not silently expand scope.

Do not add major frameworks, tools, agents, or product features without explaining what concrete problem they solve.

For now, begin by inspecting the repository and the current LangChain documentation, then show me the implementation plan for Phase 1 and proceed with the Phase 1 vertical slice.