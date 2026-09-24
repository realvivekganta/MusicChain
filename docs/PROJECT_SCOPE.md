# Project scope

MusicChain is a local customer-support reference application for a fictional
digital media store using Chinook. It demonstrates a bounded agent combining
grounded answers, customer data isolation, human-reviewed actions and an observable
evaluation workflow.

## Functional requirements

| Workflow | Required behavior |
| --- | --- |
| Purchase support | Look up recent purchases, invoices or literal track/album/artist matches; return only the runtime customer's records with bounded pagination |
| Catalog search | Search real music by literal text and optional exact genre; distinguish catalog availability from ownership |
| Recommendations | Use full purchase history, exclude owned and non-music tracks, respect requested genre/count and optional artist variety, expose ranking evidence |
| Support requests | Propose an invoice and reason; pause for approve/edit/reject; validate the reviewed action and ownership before creating a mock case |

Missing and foreign invoices have the same `no_authorized_records` result.
Expected database failures produce `temporarily_unavailable`, not an empty-history
claim. The agent grounds factual answers in tool results and asks for missing
support details. An approved case is a local record, not a refund or external ticket.

## Architectural requirements

- Use LangChain `create_agent()` as the primary abstraction, with LangGraph runtime
  and local Agent Server checkpointing. Use LangSmith Studio as the interface.
- Keep customer identity outside model-selected arguments. Trusted invocation
  context carries identity; application code and parameterized SQL enforce scope.
- Keep Chinook read-only. Store mock support cases separately, with fresh ownership
  checks and transactional duplicate handling after human review.
- Use built-in middleware for review and bounded tool use: four proposals per
  invocation and twenty per thread, including resumed conversations.
- Pin source data and dependencies, provide offline boundary tests, verify hosted
  traces and retain a baseline-to-improvement evaluation comparison.
- Preserve an engineering friction log covering observed problems and resolutions.

## Evaluation requirements

The workflow follows **observe → diagnose → evaluate → improve → compare**. Cases
cover purchase authorization, catalog grounding, unowned music, requested artist
variety and approval outcomes. Deterministic graders check objective contracts
against raw data and observed execution. Reference answers are never provided to
the model. Trials use isolated threads and temporary support stores.

The preserved comparison contains 15 scenarios repeated twice per version. See
[evaluation](EVALUATION.md) for the calibrated baseline, improved version, original
source snapshots and limitations. See [verification](VERIFICATION.md) for runtime
checks and observed results.

## Intentional boundaries

This application runs from an editable local checkout. It does not implement a
customer login, reviewer authentication, thread/checkpoint ACLs, deployment
infrastructure, a custom frontend, external support integrations or refund execution.
Studio is a trusted operator interface with simulated identity. Separate customer
threads are required; SQL scoping cannot protect messages already in a reused thread.

The bounded workflow uses one agent and explicit tools. Generic text-to-SQL, RAG,
shell/filesystem access, subagent delegation and open-ended planning are outside
scope. Deep Agents would suit broader planning and context-management needs; those
capabilities are not needed by the current workflows.

Recommendations use transparent purchase-count heuristics, not inferred listening
preferences. Exact genre matching and music allowlists target the pinned dataset.
Broader model evaluations, real authentication, action policy, external integration
and trace retention/redaction controls would be needed for production use.

## References

- [Chinook provenance and checksum](../src/data/source.json) and [license](../src/data/CHINOOK_LICENSE.md)
- [LangChain official documentation](https://docs.langchain.com/use-these-docs)
- [Architecture and framework responsibilities](ARCHITECTURE.md)
