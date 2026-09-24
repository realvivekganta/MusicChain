"""Model-facing business tools and their runtime dependencies.

LangChain derives the public tool schema from the function signature and injects
ToolRuntime privately. Data-access code enforces customer ownership; the agent's
HITL middleware gates support writes before tool execution.
"""

# Tool docstrings below become model-visible capability descriptions. Keep
# developer explanations outside them unless intentionally changing agent behavior.

# --- Imports -----------------------------------------------------------------

import sqlite3

from langchain.tools import ToolRuntime, tool

from agent.context import (
    CatalogQuery,
    CustomerContext,
    DifferentArtists,
    PageOffset,
    PageSize,
    PositiveId,
    PurchaseQuery,
    RecommendationCount,
    RecommendationQuery,
    SearchText,
    SupportReason,
    SupportRequestInput,
    require_customer,
)
from agent.database import get_purchases, get_recommendations, search_catalog
from agent.support_store import save_support_request

# --- Purchase support: one bounded, read-only capability ----------------------


@tool
def get_my_purchases(
    runtime: ToolRuntime[CustomerContext],
    invoice_id: PositiveId | None = None,
    search: SearchText | None = None,
    limit: PageSize = 20,
    offset: PageOffset = 0,
) -> dict:
    """Look up the authenticated customer's purchased tracks, newest first.

    Supply invoice_id for one invoice, or search for a literal track, album, or
    artist substring across purchase history. Results are invoice line items,
    not whole albums or invoices. Use next_offset to page when has_more is true.
    Only the authenticated customer's records can be returned. Missing and
    unauthorized invoices both return no_authorized_records. No currency is
    recorded in Chinook. A database error is not evidence of no purchases.
    """
    customer = require_customer(runtime.context)
    query = PurchaseQuery(invoice_id=invoice_id, search=search, limit=limit, offset=offset)
    try:
        return get_purchases(customer, query)
    except sqlite3.Error:
        # Do not expose paths or raw SQL errors to the model/customer.
        return {
            "status": "temporarily_unavailable",
            "message": "Purchase records are unavailable. Try again later.",
        }


# --- Music discovery: public catalog and customer-scoped recommendations -------


@tool
def search_music_catalog(
    search: SearchText | None = None,
    genre: SearchText | None = None,
    limit: PageSize = 20,
    offset: PageOffset = 0,
) -> dict:
    """Search real music tracks by literal track/album/artist substring.

    genre is an exact case-insensitive Chinook genre, e.g. Rock, Jazz, Metal,
    Alternative & Punk, Classical, or R&B/Soul. Both filters must match if supplied.
    Video and non-music genres are excluded. Results can include owned tracks:
    use recommend_music to suggest tracks this customer does not own.
    Use next_offset when has_more is true. Prices have no recorded currency.
    """
    query = CatalogQuery(search=search, genre=genre, limit=limit, offset=offset)
    try:
        return search_catalog(query)
    except sqlite3.Error:
        return {
            "status": "temporarily_unavailable",
            "message": "The music catalog is unavailable. Try again later.",
        }


@tool
def recommend_music(
    runtime: ToolRuntime[CustomerContext],
    genre: SearchText | None = None,
    limit: RecommendationCount = 3,
    different_artists: DifferentArtists = False,
) -> dict:
    """Recommend up to 10 unowned music tracks using this customer's full history.

    Ownership and music-only exclusions are mandatory, enforced in SQL. genre
    optionally narrows to an exact case-insensitive genre (e.g. Rock or Jazz).
    Without a genre, use purchased music genres. Ranking uses distinct owned
    tracks in the genre, then by the artist, with track ID as a stable tie-break.
    Set different_artists=True when the customer requests artist variety: SQL
    returns at most one track per artist, or fewer tracks if too few artists qualify.
    Each result includes those counts as evidence; they do not prove the customer
    liked a purchase. No separate purchase lookup is required for this tool.
    needs_genre_preference means no music history: ask for a genre. An explicit
    genre can yield requested_genre suggestions with no purchase-based evidence.
    Fewer than limit results means insufficient eligible candidates, not an error.
    """
    customer = require_customer(runtime.context)
    query = RecommendationQuery(genre=genre, limit=limit, different_artists=different_artists)
    try:
        return get_recommendations(customer, query)
    except sqlite3.Error:
        return {
            "status": "temporarily_unavailable",
            "message": "Music recommendations are unavailable. Try again later.",
        }


# --- Consequential action: agent middleware requires human review -------------


@tool
def create_support_request(
    invoice_id: PositiveId,
    reason: SupportReason,
    runtime: ToolRuntime[CustomerContext],
) -> dict:
    """Propose a mock support case for an invoice this customer owns.

    Requires human approve/edit/reject through the agent's review workflow before
    execution. Include the customer's actual issue as reason; ask if unclear.
    This only records an open local case, never issues a refund or contacts anyone.
    Ownership is checked again after approval. Missing and unauthorized invoices
    both return no_authorized_records. already_exists returns an unchanged open
    case, preserving its original reason. A failure is not proof a retry is needed:
    a prior commit may have succeeded; repeating this action safely deduplicates.
    """
    customer = require_customer(runtime.context)
    query = SupportRequestInput(invoice_id=invoice_id, reason=reason)
    try:
        return save_support_request(customer, query)
    except (sqlite3.Error, OSError):
        return {
            "status": "temporarily_unavailable",
            "message": "Could not confirm support request creation. Try again later.",
        }
