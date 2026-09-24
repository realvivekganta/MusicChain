"""Run isolated real-agent cases and publish reproducible LangSmith experiments.

Usage: python -m evals.runner --label baseline --repetitions 2
Support decisions simulate a trusted reviewer, not a message sent to the model.
Runs are sequential because each target temporarily overrides SUPPORT_DB_PATH.
"""

# --- Imports -----------------------------------------------------------------

import argparse
import hashlib
import json
import os
import platform
import re
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import NAMESPACE_URL, uuid4, uuid5
from zipfile import ZIP_DEFLATED, ZipFile

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from langsmith import Client
from langsmith.utils import LangSmithNotFoundError

from agent.agent import build_agent
from agent.context import CustomerContext
from agent.database import PROJECT_ROOT, database_path
from evals.evaluators import grade_case

# --- Capture real tool output and isolated support-store state -----------------


def read_support_rows(path: Path) -> list[dict]:
    """Read persisted evidence without creating or modifying the temporary store.

    A missing file means no write occurred and returns an empty list. Existing
    files must contain the support schema; unexpected SQLite errors propagate.
    """
    if not path.exists():
        return []
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as db:
        db.row_factory = sqlite3.Row
        return [dict(row) for row in db.execute("SELECT * FROM support_requests")]


def capture(state: dict) -> dict:
    """Extract tool evidence, final assistant content and pause state for grading.

    Edited tool results can include a middleware notice before their JSON payload.
    Keep non-JSON rejection/error messages as text rather than discarding them.
    Pending proposals have no final answer; the runner records proposals separately.
    """
    events = []
    for message in state.get("messages", []):
        if isinstance(message, ToolMessage):
            content = str(message.content)
            try:
                payload = json.loads(content.rsplit("Tool response:\n", 1)[-1])
            except (ValueError, TypeError):
                payload = {"status": "tool_message", "text": content}
            events.append({"name": message.name, "payload": payload})
    last = state.get("messages", [None])[-1]
    paused = bool(state.get("__interrupt__"))
    return {
        "tools": events,
        "answer": last.content if isinstance(last, AIMessage) and not paused else "",
        "paused": paused,
    }


def run_case(inputs: dict) -> dict:
    """Execute one real-agent fixture with isolated identity, history and storage.

    Only inputs reach this target; reference outputs are grader-only. Pass the
    fixture's customer ID as trusted runtime context and its prompt as chat.
    If requested, supply one fixed reviewer decision outside the conversation;
    never automatically approve additional proposals or follow-up interrupts.

    Return tool/answer evidence plus proposals and rows before/after review.
    Restore SUPPORT_DB_PATH even on failure. Each temporary store is deleted on
    exit; callers must run cases sequentially because the environment is shared.
    Exceptions propagate to LangSmith as failed trials rather than being hidden.
    """
    # --- Trial isolation: no shared history or writes to the Studio store ---
    previous = os.environ.get("SUPPORT_DB_PATH")
    try:
        with TemporaryDirectory(prefix="chinook-eval-") as directory:
            path = Path(directory) / "support.sqlite"
            os.environ["SUPPORT_DB_PATH"] = str(path)
            graph = build_agent(checkpointer=InMemorySaver())
            config = {"configurable": {"thread_id": str(uuid4())}, "recursion_limit": 50}
            context = CustomerContext(inputs["customer_id"])
            state = graph.invoke(
                {"messages": [{"role": "user", "content": inputs["prompt"]}]},
                config=config,
                context=context,
            )
            # --- Review boundary: preserve evidence before any scripted decision ---
            before = read_support_rows(path)
            interrupts = state.get("__interrupt__", [])
            proposals = [
                action for pause in interrupts for action in pause.value["action_requests"]
            ]
            review = inputs.get("review", "pending")
            if proposals and review != "pending":
                # Never silently approve extra or unrelated proposals in the harness.
                if len(proposals) != 1 or proposals[0]["name"] != "create_support_request":
                    raise ValueError("Unexpected review proposal")
                # The unauthorized fixture still approves a proposed action so
                # execution-time ownership can deny it independently of the reviewer.
                decision = {"type": "approve"}
                if review == "reject":
                    decision = {"type": "reject", "message": "Do not create this case."}
                elif review == "edit":
                    decision = {
                        "type": "edit",
                        "edited_action": {
                            "name": "create_support_request",
                            "args": {
                                "invoice_id": 382,
                                "reason": "Reviewed demo: please investigate invoice 382.",
                            },
                        },
                    }
                state = graph.invoke(
                    Command(resume={"decisions": [decision]}), config=config, context=context
                )
            # --- Grader output: factual execution evidence, not a reference answer ---
            return {
                **capture(state),
                "completed": True,
                "proposals": proposals,
                "rows_before_review": before,
                "rows": read_support_rows(path),
                "unexpected_interrupt": bool(state.get("__interrupt__")) and review != "pending",
            }
    finally:
        if previous is None:
            os.environ.pop("SUPPORT_DB_PATH", None)
        else:
            os.environ["SUPPORT_DB_PATH"] = previous


# --- Immutable-by-content dataset and source evidence --------------------------


def digest(path: Path) -> str:
    """Return the file-byte SHA-256 used to identify source, cases and database versions."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sync_dataset(client: Client, cases: list[dict], case_hash: str):
    """Return a hosted dataset and examples matching the local case snapshot.

    Derive the dataset name and stable example IDs from the case content hash.
    Create missing examples to allow an interrupted upload to resume, but reject
    changed/duplicate/unknown hosted cases instead of overwriting past references.
    The returned examples are the verified snapshot passed to the experiment.
    """
    name = f"chinook-phase4-{case_hash[:12]}"
    try:
        dataset = client.read_dataset(dataset_name=name)
    except LangSmithNotFoundError:
        dataset = client.create_dataset(
            dataset_name=name,
            description="15 Chinook contracts with simulated customer/reviewer context.",
        )
    existing = list(client.list_examples(dataset_id=dataset.id))
    wanted = {case["inputs"]["case_id"]: case for case in cases}
    seen = set()
    for example in existing:
        key = example.inputs["case_id"]
        if (
            key in seen
            or key not in wanted
            or (
                example.inputs != wanted[key]["inputs"] or example.outputs != wanted[key]["outputs"]
            )
        ):
            raise ValueError(
                "Hosted dataset differs from pinned local cases; refusing to overwrite"
            )
        seen.add(key)
    # Stable IDs make retrying a partial dataset upload refer to the same examples.
    missing = [
        {
            **case,
            "id": str(uuid5(NAMESPACE_URL, name + "/" + key)),
            "metadata": {"case_id": key, "cases_sha256": case_hash},
        }
        for key, case in wanted.items()
        if key not in seen
    ]
    if missing:
        client.create_examples(dataset_id=dataset.id, examples=missing)
    examples = list(client.list_examples(dataset_id=dataset.id))
    if len(examples) != len(cases):
        raise ValueError("Incomplete dataset upload")
    return dataset, examples


def snapshot(destination: Path) -> dict:
    """Write source.zip and return a relative-path-to-SHA-256 manifest.

    Archive only explicitly allowed source, tests, pinned SQL and configuration
    files inside an already-created experiment directory. Exclude .env, SQLite
    stores and checkpoints so the evidence contains no runtime credentials/state.
    The caller owns creating a fresh directory and preventing artifact overwrites.
    """
    paths = [PROJECT_ROOT / name for name in ("app.py", "pyproject.toml", "requirements.lock")]
    for directory in ("src/agent", "src/evals", "src/scripts", "tests"):
        paths.extend(sorted((PROJECT_ROOT / directory).glob("*.py")))
    for pattern in ("*.sql", "source.json", "CHINOOK_LICENSE.md", "eval_cases.json"):
        paths.extend(sorted((PROJECT_ROOT / "src/data").glob(pattern)))
    hashes = {str(path.relative_to(PROJECT_ROOT)): digest(path) for path in paths}
    with ZipFile(destination / "source.zip", "w", ZIP_DEFLATED) as archive:
        for path in paths:
            archive.write(path, path.relative_to(PROJECT_ROOT))
    return hashes


# --- Experiment execution and inspectable local results ------------------------


def main() -> None:
    """Publish repeated real-agent trials and save their source/configuration/results.

    Validate CLI options and local credentials, preserve source before execution,
    then sync the exact dataset and evaluate sequentially with deterministic scores.
    Record per-trial errors and applicable-metric denominators, flush trace uploads,
    and print the experiment link. The initial manifest remains if execution fails;
    completed artifacts are written only after the experiment returns. Labels name
    runs and never select a historical implementation. Model calls incur normal use.
    """
    # --- Configuration and credentials: validate before creating remote work ---
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", required=True, help="baseline or a descriptive candidate label")
    parser.add_argument("--repetitions", type=int, default=2)
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9-]+", args.label) or args.repetitions < 1:
        parser.error("Use a lowercase label and a positive repetition count")
    load_dotenv(PROJECT_ROOT / ".env", override=True)
    if not all(os.environ.get(key) for key in ("OPENAI_API_KEY", "LANGSMITH_API_KEY")):
        parser.error("Set OPENAI_API_KEY and LANGSMITH_API_KEY in local .env")
    os.environ["LANGSMITH_TRACING"] = "true"
    # --- Preserve the evaluated source before running any trials ---
    cases_path = PROJECT_ROOT / "src/data/eval_cases.json"
    cases = json.loads(cases_path.read_text())
    case_hash = digest(cases_path)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    destination = PROJECT_ROOT / "artifacts/phase4" / f"{stamp}-{args.label}"
    destination.mkdir(parents=True, exist_ok=False)
    hashes = snapshot(destination)
    manifest = {
        "label": args.label,
        "started_at": stamp,
        "status": "started",
        "model": os.environ.get("SUPPORT_MODEL", "openai:gpt-6-luna"),
        "model_configuration": "See source snapshot agent.py; other defaults are provider-owned",
        "python": platform.python_version(),
        "repetitions": args.repetitions,
        "case_count": len(cases),
        "cases_sha256": case_hash,
        "evaluators_sha256": hashes["src/evals/evaluators.py"],
        "database_sha256": digest(database_path()),
        "source_hashes": hashes,
        "versions": {name: version(name) for name in ("langchain", "langgraph", "langsmith")},
    }
    manifest_path = destination / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    # --- Hosted dataset and experiment: use one fixed example snapshot ---
    client = Client()
    dataset, examples = sync_dataset(client, cases, case_hash)
    manifest.update(
        dataset_id=str(dataset.id),
        dataset_name=dataset.name,
        dataset_version=max(str(e.modified_at) for e in examples),
    )
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    # Feed the verified example snapshot, not a mutable name resolved later.
    results = client.evaluate(
        run_case,
        data=examples,
        evaluators=[grade_case],
        max_concurrency=0,
        num_repetitions=args.repetitions,
        experiment_prefix=f"phase4-{args.label}",
        metadata={
            key: manifest[key]
            for key in ("cases_sha256", "evaluators_sha256", "database_sha256", "model", "label")
        },
        description="Real-agent trials; deterministic contracts; wording needs manual review.",
    )
    # --- Local results: keep failures and count only applicable metric scores ---
    rows = []
    for row in results:
        run = row["run"]
        rows.append(
            {
                "case_id": row["example"].inputs["case_id"],
                "run_id": str(run.id),
                "error": run.error,
                "outputs": run.outputs,
                "scores": {
                    result.key: result.score for result in row["evaluation_results"]["results"]
                },
            }
        )
    keys = sorted({key for row in rows for key in row["scores"]})
    summary = {
        key: {
            "passed": sum(row["scores"].get(key, 0) == 1 for row in rows),
            "evaluated": sum(key in row["scores"] for row in rows),
        }
        for key in keys
    }
    manifest.update(
        status="completed",
        experiment_id=str(results.experiment_id),
        experiment_name=results.experiment_name,
        url=results.url,
        completed_at=datetime.now(UTC).isoformat(),
        summary=summary,
        run_errors=sum(bool(row["error"]) for row in rows),
    )
    (destination / "results.json").write_text(json.dumps(rows, indent=2, default=str) + "\n")
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    # evaluate() uploads feedback; flush trace batching before process exit.
    client.flush()
    print(
        json.dumps(
            {
                "artifacts": str(destination),
                "url": results.url,
                "run_errors": manifest["run_errors"],
                "summary": summary,
            },
            indent=2,
        )
    )


# --- Command-line entry point ------------------------------------------------

if __name__ == "__main__":
    main()
