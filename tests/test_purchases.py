"""Verify purchase access directly against a fresh Chinook database.

These tests exercise deterministic SQL ownership checks, bounded results, input
validation and read-only access independently of the model and agent runtime.
"""

# --- Imports -----------------------------------------------------------------

import sqlite3

import pytest
from pydantic import ValidationError

from agent.context import CustomerContext, PurchaseQuery
from agent.database import get_purchases, read_connection

# --- Grounded records and invoice ownership ----------------------------------


def test_known_invoice_is_grounded():
    """Verify invoice 98's two line items and decimal total without inventing a currency."""
    result = get_purchases(CustomerContext(1), PurchaseQuery(invoice_id=98))
    assert result["status"] == "ok"
    assert result["returned"] == 2
    assert {item["invoice_id"] for item in result["items"]} == {98}
    assert {item["invoice_total"] for item in result["items"]} == {"3.98"}
    assert all(item["track"] and item["artist"] for item in result["items"])
    assert result["currency"] is None


def test_other_customers_invoice_is_indistinguishable_from_missing():
    """Prevent invoice-existence disclosure by requiring identical foreign and missing responses."""
    assert get_purchases(CustomerContext(2), PurchaseQuery(invoice_id=98)) == get_purchases(
        CustomerContext(2), PurchaseQuery(invoice_id=999999)
    )


def test_all_invoice_ownership_boundaries(chinook_path):
    """Check every source invoice succeeds for its owner and returns no items for another
    customer.
    """
    with read_connection(chinook_path) as connection:
        ownership = connection.execute("SELECT InvoiceId, CustomerId FROM Invoice").fetchall()
    for invoice in ownership:
        own = CustomerContext(invoice["CustomerId"])
        other = CustomerContext(invoice["CustomerId"] % 59 + 1)
        query = PurchaseQuery(invoice_id=invoice["InvoiceId"], limit=50)
        assert get_purchases(own, query)["status"] == "ok"
        assert get_purchases(other, query)["items"] == []


# --- Pagination and literal search -------------------------------------------


def test_recent_results_paginate_without_duplicates(chinook_path):
    """Reassemble full scoped history in order and verify pages omit unnecessary customer
    details.
    """
    context = CustomerContext(1)
    collected = []
    offset = 0
    while True:
        page = get_purchases(context, PurchaseQuery(limit=3, offset=offset))
        assert page["returned"] <= 3
        collected.extend(page["items"])
        if not page["has_more"]:
            assert page["next_offset"] is None
            break
        offset = page["next_offset"]
    with read_connection(chinook_path) as connection:
        expected = connection.execute(
            "SELECT InvoiceLineId FROM InvoiceLine JOIN Invoice USING(InvoiceId) "
            "WHERE CustomerId=1 ORDER BY InvoiceDate DESC, InvoiceId DESC, InvoiceLineId"
        ).fetchall()
    assert [item["invoice_line_id"] for item in collected] == [row[0] for row in expected]
    assert collected[0]["invoice_id"] == 382
    assert not {"customer_id", "email", "address", "billing_address"} & collected[0].keys()


@pytest.mark.parametrize("search", ["' OR 1=1 --", "%", "_", "'; DROP TABLE Invoice; --"])
def test_search_is_literal_and_cannot_broaden_scope(search):
    """Treat SQL syntax and wildcard characters as search text rather than executable filters."""
    assert get_purchases(CustomerContext(1), PurchaseQuery(search=search))["items"] == []


def test_artist_search_is_scoped(chinook_path):
    """Find a genuine Miles Davis buyer and verify another customer cannot see those purchases."""
    with read_connection(chinook_path) as connection:
        customer_id = connection.execute(
            "SELECT i.CustomerId FROM Invoice i JOIN InvoiceLine il USING(InvoiceId) "
            "JOIN Track t USING(TrackId) JOIN Album al USING(AlbumId) "
            "JOIN Artist ar USING(ArtistId) WHERE ar.Name = ? LIMIT 1",
            ("Miles Davis",),
        ).fetchone()[0]
    matches = get_purchases(CustomerContext(customer_id), PurchaseQuery(search="miles davis"))
    assert matches["items"]
    assert all(item["artist"] == "Miles Davis" for item in matches["items"])
    assert get_purchases(CustomerContext(1), PurchaseQuery(search="Miles Davis"))["items"] == []


# --- Identity and filter validation -------------------------------------------


@pytest.mark.parametrize("bad", [0, -1, True, "1", 1.0, None, 2**63])
def test_invalid_customer_context_is_rejected(bad):
    """Require a positive integer identity without accepting strings, floats or bool coercion."""
    with pytest.raises(ValueError):
        CustomerContext(bad)


@pytest.mark.parametrize(
    "args",
    [
        {"invoice_id": 0},
        {"invoice_id": True},
        {"invoice_id": "98"},
        {"invoice_id": 2**63},
        {"limit": 0},
        {"limit": 51},
        {"offset": -1},
        {"offset": 10_001},
        {"search": " "},
        {"search": "a" * 101},
        {"customer_id": 2},
    ],
)
def test_invalid_tool_filters_are_rejected(args):
    """Enforce integer bounds, bounded search text and the absence of model-selected customer
    IDs.
    """
    with pytest.raises(ValidationError):
        PurchaseQuery(**args)


def test_no_customer_context_fails_closed():
    """Make the direct purchase function reject an absent trusted caller before reading records."""
    with pytest.raises(ValueError, match="Trusted CustomerContext"):
        get_purchases(None, PurchaseQuery())


def test_largest_supported_customer_id_returns_no_records_without_overflow():
    """Allow SQLite's maximum integer while returning an empty result for an unknown caller."""
    assert get_purchases(CustomerContext(2**63 - 1), PurchaseQuery())["items"] == []


# --- Read-only storage guarantees --------------------------------------------


def test_database_is_read_only_even_if_file_permissions_change(chinook_path):
    """Prove URI read-only mode still blocks writes after weakening permissions and PRAGMA
    safeguards.
    """
    chinook_path.chmod(0o644)
    try:
        with read_connection(chinook_path) as connection:
            connection.execute("PRAGMA query_only = OFF")
            with pytest.raises(sqlite3.OperationalError, match="readonly"):
                connection.execute("DELETE FROM Invoice")
    finally:
        chinook_path.chmod(0o444)


def test_missing_database_is_not_created(tmp_path):
    """Ensure a failed read cannot silently create an empty database at a mistyped path."""
    missing = tmp_path / "missing.sqlite"
    with pytest.raises(sqlite3.OperationalError), read_connection(missing):
        pass
    assert not missing.exists()
