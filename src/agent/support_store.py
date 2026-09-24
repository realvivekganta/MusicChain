"""Transactional mock support cases, separate from read-only Chinook.

The agent's approval middleware gates this capability. This module independently
validates inputs and invoice ownership on every execution, including retries.
There is no refund execution, external ticket submission or case-closing workflow.
"""

# --- Imports -----------------------------------------------------------------

import os
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from agent.context import CustomerContext, SupportRequestInput, require_customer
from agent.database import PROJECT_ROOT, database_path, owns_invoice

# --- Writable store location: never open Chinook for writes --------------------


def support_path() -> Path:
    """Resolve the writable store location and reject any alias of Chinook.

    Relative paths use the project root. Resolution catches symbolic links;
    samefile also catches existing hard links. Reject both the configured source
    and the default source path with OperationalError before opening for writes.
    """
    path = Path(os.environ.get("SUPPORT_DB_PATH", "src/data/support.sqlite"))
    target = (path if path.is_absolute() else PROJECT_ROOT / path).resolve()
    for source in (database_path().resolve(), PROJECT_ROOT / "src/data/chinook.sqlite"):
        if target == source or (target.exists() and source.exists() and target.samefile(source)):
            raise sqlite3.OperationalError("Support store must be separate from Chinook")
    return target


# --- Authorized, repeatable case creation -------------------------------------


def save_support_request(context: CustomerContext, query: SupportRequestInput) -> dict:
    """Create one open case per customer/invoice, or return the unchanged case.

    Internal persistence function: callers must arrange human approval. Inputs
    and invoice ownership are checked again at execution. Unauthorized or missing
    invoices return no_authorized_records without creating a file or table.

    An immediate transaction plus a unique constraint serializes competing writes.
    Duplicates retain the original ID/reason. Success is returned only after commit;
    SQLite and filesystem errors propagate for the tool to report safely. The
    returned case omits customer identity and never represents an actual refund.
    """
    customer = require_customer(context)
    query = SupportRequestInput.model_validate(query)
    if not owns_invoice(customer, query.invoice_id):
        return {"status": "no_authorized_records"}

    with closing(sqlite3.connect(support_path(), timeout=5)) as connection:
        connection.row_factory = sqlite3.Row
        with connection:
            # Acquire the write lock before reading/inserting so competing approvals
            # return the same committed case instead of creating divergent records.
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """CREATE TABLE IF NOT EXISTS support_requests (
                    request_id TEXT PRIMARY KEY,
                    customer_id INTEGER NOT NULL CHECK(customer_id > 0),
                    invoice_id INTEGER NOT NULL CHECK(invoice_id > 0),
                    reason TEXT NOT NULL CHECK(length(trim(reason)) BETWEEN 1 AND 1000),
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status = 'open'),
                    UNIQUE(customer_id, invoice_id)
                )"""
            )
            inserted = (
                connection.execute(
                    """INSERT INTO support_requests
                   (request_id, customer_id, invoice_id, reason, created_at, status)
                   VALUES (?, ?, ?, ?, ?, 'open')
                   ON CONFLICT(customer_id, invoice_id) DO NOTHING""",
                    (
                        str(uuid4()),
                        customer.customer_id,
                        query.invoice_id,
                        query.reason,
                        datetime.now(UTC).isoformat(),
                    ),
                ).rowcount
                == 1
            )
            row = connection.execute(
                """SELECT request_id, invoice_id, reason, created_at, status
                   FROM support_requests WHERE customer_id = ? AND invoice_id = ?""",
                (customer.customer_id, query.invoice_id),
            ).fetchone()
        # The transaction has committed before we tell the model it succeeded.
    return {
        "status": "created" if inserted else "already_exists",
        "request": dict(row),
        "mock": True,
        "refund_issued": False,
    }
