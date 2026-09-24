"""Verify real purchase, discovery or reviewed support interactions and tracing.

Run with: python -m scripts.verify_live --verify-trace
For discovery add: --scenario catalog or --scenario recommendations
Support scenarios use a temporary case store and scripted reviewer decisions.
Uses local .env credentials and makes real provider calls; offline tests do not.
"""

# --- Imports -----------------------------------------------------------------

import argparse
import asyncio
import json
import os
import sqlite3
import time
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from dotenv import load_dotenv
from langchain_core.messages import ToolMessage
from langchain_core.tracers.langchain import wait_for_all_tracers
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from langsmith import Client, NotFoundError
from langsmith.utils import LangSmithNotFoundError

from agent.agent import build_agent
from agent.context import (
    CatalogQuery,
    CustomerContext,
    PurchaseQuery,
    RecommendationQuery,
    SupportRequestInput,
)
from agent.database import PROJECT_ROOT, get_purchases, get_recommendations, search_catalog

# --- Hosted trace verification -----------------------------------------------


async def verify_trace(
    run_id, *, tool_name: str | None = "get_my_purchases", timeout: float = 20
) -> str:
    """Return the hosted URL after observing a completed root and model/tool spans.

    Poll the configured LangSmith project for indexing delays up to timeout
    seconds. Set tool_name=None for rejection runs, where no write tool executes.
    A missing or unsuccessful trace raises RuntimeError; other service failures
    propagate. The caller must flush its tracing callbacks before this check.
    """
    client = Client()
    trace_id = str(run_id)  # This helper invokes a root run, which is its own trace.
    project = await client.aread_project(
        project_name=os.environ.get("LANGSMITH_PROJECT", "default")
    )
    project_id = str(project.id)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            trace = await client.traces.list_runs(
                trace_id,
                project_id=project_id,
                selects=["ID", "NAME", "RUN_TYPE", "STATUS", "END_TIME", "ERROR"],
            )
            spans = trace.items or []
            root = next((span for span in spans if str(span.id) == trace_id), None)
            # Hosted responses currently use lowercase despite uppercase SDK types.
            has_model = any(str(span.run_type).lower() == "llm" for span in spans)
            has_tool = tool_name is None or any(
                str(span.run_type).lower() == "tool" and span.name == tool_name for span in spans
            )
            completed = all(
                span.end_time and str(span.status).lower() == "success" and not span.error
                for span in spans
            )
            if root and completed and has_model and has_tool:
                response = await client.runs.get_url(
                    trace_id, project_id=project_id, trace_id=trace_id
                )
                return response.url
        except (LangSmithNotFoundError, NotFoundError):
            pass  # Trace indexing can lag briefly behind submission.
        await asyncio.sleep(1)
    raise RuntimeError(f"Trace {run_id} not verified with completed model/tool spans in time")


# --- Live interaction and grounded-result checks -----------------------------


def verify_support(decision_type: str, *, hosted_trace: bool) -> None:
    """Run one real-model support scenario with a fixed trusted reviewer decision.

    Require one invoice-98 proposal and no pre-approval write, then approve,
    reject or edit it to invoice 382. Inspect persisted rows and the final model
    response; optionally verify the resumed hosted trace. Unexpected proposals
    or outcomes raise RuntimeError. Always restore the configured store path and
    remove the temporary store. This verifies the API flow, not Studio's UI.
    """
    context = CustomerContext(1)
    proposal_id, resume_id = uuid4(), uuid4()
    config = {"configurable": {"thread_id": str(uuid4())}, "tags": ["phase3", "live-smoke"]}
    with TemporaryDirectory(prefix="chinook-support-smoke-") as directory:
        path = Path(directory) / "support.sqlite"
        previous = os.environ.get("SUPPORT_DB_PATH")
        os.environ["SUPPORT_DB_PATH"] = str(path)
        try:
            graph = build_agent(checkpointer=InMemorySaver())
            paused = graph.invoke(
                {
                    "messages": [
                        (
                            "user",
                            "Please create a support request for invoice 98. "
                            "Reason: I do not recognize this invoice.",
                        )
                    ]
                },
                {**config, "run_id": proposal_id, "run_name": f"phase3-{decision_type}-proposal"},
                context=context,
            )
            # --- Proposal checks: authorize only this helper's fixed demo action ---
            interrupts = paused.get("__interrupt__", [])
            if len(interrupts) != 1 or path.exists():
                raise RuntimeError("Expected one review interrupt and no pre-approval store")
            actions = interrupts[0].value["action_requests"]
            if len(actions) != 1 or actions[0]["name"] != "create_support_request":
                raise RuntimeError("Unexpected proposed action; refusing scripted review")
            proposed = SupportRequestInput(**actions[0]["args"])
            if proposed.invoice_id != 98:
                raise RuntimeError("Unexpected invoice; refusing scripted review")
            decision = {"type": decision_type}
            expected = proposed
            if decision_type == "edit":
                expected = SupportRequestInput(
                    invoice_id=382, reason="Reviewed demo: please investigate invoice 382."
                )
                decision["edited_action"] = {
                    "name": "create_support_request",
                    "args": expected.model_dump(),
                }
            elif decision_type == "reject":
                decision["message"] = "Do not create a case. Do not retry this action."
            # --- Resume the same thread with the same trusted customer ---
            result = graph.invoke(
                Command(resume={"decisions": [decision]}),
                {**config, "run_id": resume_id, "run_name": f"phase3-{decision_type}-resume"},
                context=context,
            )
            # --- Persisted outcome: approval alone is not proof a write succeeded ---
            if result.get("__interrupt__"):
                raise RuntimeError("Unexpected second proposal; refusing automatic approval")
            if decision_type == "reject":
                if path.exists():
                    raise RuntimeError("A rejected request wrote to the support store")
                messages = [
                    m
                    for m in result["messages"]
                    if isinstance(m, ToolMessage) and m.name == "create_support_request"
                ]
                if not messages or messages[-1].status != "error":
                    raise RuntimeError("Missing explicit rejection result")
            else:
                with closing(sqlite3.connect(path)) as connection:
                    records = connection.execute(
                        "SELECT customer_id, invoice_id, reason, status FROM support_requests"
                    ).fetchall()
                if records != [(1, expected.invoice_id, expected.reason, "open")]:
                    raise RuntimeError("Stored case differs from the approved action")
            final = result["messages"][-1]
            if final.type != "ai" or not final.content:
                raise RuntimeError("No final model response")
            print(final.content)
            print(f"Verified {decision_type}: pause before write and expected persisted outcome.")
            print(f"Proposal run: {proposal_id}; resumed run: {resume_id}")
        finally:
            wait_for_all_tracers()
            if previous is None:
                os.environ.pop("SUPPORT_DB_PATH", None)
            else:
                os.environ["SUPPORT_DB_PATH"] = previous
    if hosted_trace:
        url = asyncio.run(
            verify_trace(
                resume_id, tool_name=None if decision_type == "reject" else "create_support_request"
            )
        )
        print(f"Verified hosted resumed trace: {url}")
    print("Review final wording manually; scripted reviewer decisions do not verify Studio UI.")


# --- Scenario selection, credentials and read-only smoke checks ----------------


def main() -> None:
    """Run the selected live smoke scenario using the project's local credentials.

    Load .env with server-compatible precedence and validate required settings.
    Read-only scenarios compare tool records with the known fixture; support
    scenarios delegate to the isolated review helper. Print a response/run ID and,
    when requested, a verified hosted trace URL. This command spends model tokens.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-trace", action="store_true")
    parser.add_argument(
        "--scenario",
        choices=[
            "purchase",
            "catalog",
            "recommendations",
            "support-approve",
            "support-reject",
            "support-edit",
        ],
        default="purchase",
    )
    args = parser.parse_args()
    # Match local Agent Server precedence: this project's .env is authoritative.
    load_dotenv(PROJECT_ROOT / ".env", override=True)
    required = ["OPENAI_API_KEY"]
    if args.verify_trace:
        required.append("LANGSMITH_API_KEY")
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        parser.exit(2, f"Missing {', '.join(missing)}. Add keys locally to .env; do not commit.\n")
    if args.verify_trace and os.environ.get("LANGSMITH_TRACING", "").lower() != "true":
        parser.exit(2, "Set LANGSMITH_TRACING=true in .env to verify hosted tracing.\n")

    if args.scenario.startswith("support-"):
        verify_support(args.scenario.removeprefix("support-"), hosted_trace=args.verify_trace)
        return

    context = CustomerContext(1)  # Trusted local demo fixture, never extracted from chat.
    if args.scenario == "purchase":
        prompt = "What's on invoice 98?"
        tool_name, item_key, phase = "get_my_purchases", "invoice_line_id", "phase1"
        expected = get_purchases(context, PurchaseQuery(invoice_id=98))
    elif args.scenario == "catalog":
        prompt = "Find three Jazz tracks by Miles Davis in the music catalog. Include track IDs."
        tool_name, item_key, phase = "search_music_catalog", "track_id", "phase2"
        expected = search_catalog(CatalogQuery(search="Miles Davis", genre="Jazz", limit=3))
    else:
        prompt = "I liked the rock music I've bought. Recommend three tracks I don't already own."
        tool_name, item_key, phase = "recommend_music", "track_id", "phase2"
        expected = get_recommendations(context, RecommendationQuery(genre="Rock", limit=3))
    if expected["status"] != "ok":
        raise RuntimeError(f"Expected {args.scenario} fixture missing; inspect Chinook")
    run_id = uuid4()
    try:
        result = build_agent().invoke(
            {"messages": [{"role": "user", "content": prompt}]},
            config={
                "run_id": run_id,
                "run_name": f"{phase}-{args.scenario}-smoke",
                "tags": [phase, "live-smoke"],
                "metadata": {"scenario": args.scenario},
            },
            context=context,
        )
    finally:
        wait_for_all_tracers()

    # These are smoke checks against known application-query results, not the
    # independent multi-case graders in evals/evaluators.py. Wording needs review.
    payloads = [
        json.loads(message.content)
        for message in result["messages"]
        if isinstance(message, ToolMessage)
        and message.name == tool_name
        and message.status != "error"
    ]
    expected_items = {item[item_key]: item for item in expected["items"]}
    returned_items = {
        item[item_key]: item for payload in payloads for item in payload.get("items", [])
    }
    if any(returned_items.get(key) != item for key, item in expected_items.items()):
        raise RuntimeError(
            f"Model did not retrieve expected {args.scenario} records; inspect trace"
        )
    if result["messages"][-1].type != "ai" or not result["messages"][-1].content:
        raise RuntimeError("No final model response")
    print(result["messages"][-1].content)
    print(f"Verified {args.scenario} tool grounding. Run ID: {run_id}")
    print("Review the wording manually; this smoke check does not grade all answer claims.")
    if args.verify_trace:
        url = asyncio.run(verify_trace(run_id, tool_name=tool_name))
        print(f"Verified hosted model/tool trace: {url}")


# --- Command-line entry point ------------------------------------------------

if __name__ == "__main__":
    main()
