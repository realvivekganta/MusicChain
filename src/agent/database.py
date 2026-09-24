"""Read-only purchases, music catalog search and grounded recommendations.

This module owns SQL and authorization. It returns bounded business records
without depending on LangChain, so the same boundary can be tested directly.
"""

# --- Imports -----------------------------------------------------------------

import os
import sqlite3
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path

from agent.context import (
    CatalogQuery,
    CustomerContext,
    PurchaseQuery,
    RecommendationQuery,
    require_customer,
)

# --- Database location -------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def database_path() -> Path:
    """Resolve CHINOOK_DB_PATH, defaulting to the project's local read-only dataset.

    Relative configuration paths are anchored to the project root, independent
    of the caller's working directory. This helper does not open or create a file.
    """
    path = Path(os.environ.get("CHINOOK_DB_PATH", "src/data/chinook.sqlite"))
    return path if path.is_absolute() else PROJECT_ROOT / path


# --- Read-only connection lifecycle ------------------------------------------


@contextmanager
def read_connection(path: Path | None = None):
    """Yield a row-mapped, query-only SQLite connection and always close it.

    The URI's mode=ro independently rejects writes and refuses to create a missing
    file. An explicit path supports isolated test databases. SQLite errors propagate
    to callers; model-facing tools convert expected failures into safe statuses.
    """
    target = (path if path is not None else database_path()).resolve()
    connection = sqlite3.connect(target.as_uri() + "?mode=ro", uri=True)
    try:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only = ON")
        yield connection
    finally:
        connection.close()


# --- Result formatting -------------------------------------------------------


def _money(value: int | float | str) -> str:
    """Format a stored amount to two decimal places without inventing a currency."""
    return str(Decimal(str(value)).quantize(Decimal("0.01")))


# --- Purchase lookup: enforce ownership in the SQL predicate ------------------


def get_purchases(
    context: CustomerContext, query: PurchaseQuery, *, path: Path | None = None
) -> dict:
    """Return a bounded page of the caller's invoice lines, newest invoice first.

    Trusted context scopes every query, including when no filters are supplied.
    Unauthorized and nonexistent invoices produce the same empty response. Search
    is a literal substring, never SQL syntax. One extra row determines pagination;
    amounts are decimal strings and repeated invoice totals must not be summed.
    An explicit path supports tests; database errors propagate to the tool layer.
    """
    customer = require_customer(context)
    query = PurchaseQuery.model_validate(query)
    with read_connection(path) as connection:
        rows = connection.execute(
            """
            SELECT i.InvoiceId AS invoice_id, i.InvoiceDate AS purchased_at,
                   i.Total AS invoice_total, il.InvoiceLineId AS invoice_line_id,
                   t.TrackId AS track_id, t.Name AS track,
                   al.Title AS album, ar.Name AS artist, g.Name AS genre,
                   mt.Name AS media_type, il.UnitPrice AS unit_price,
                   il.Quantity AS quantity
            FROM Invoice AS i
            JOIN InvoiceLine AS il ON il.InvoiceId = i.InvoiceId
            JOIN Track AS t ON t.TrackId = il.TrackId
            LEFT JOIN Album AS al ON al.AlbumId = t.AlbumId
            LEFT JOIN Artist AS ar ON ar.ArtistId = al.ArtistId
            LEFT JOIN Genre AS g ON g.GenreId = t.GenreId
            JOIN MediaType AS mt ON mt.MediaTypeId = t.MediaTypeId
            WHERE i.CustomerId = :customer_id
              AND (:invoice_id IS NULL OR i.InvoiceId = :invoice_id)
              AND (:search IS NULL
                   OR instr(lower(t.Name), lower(:search)) > 0
                   OR instr(lower(al.Title), lower(:search)) > 0
                   OR instr(lower(ar.Name), lower(:search)) > 0)
            ORDER BY i.InvoiceDate DESC, i.InvoiceId DESC, il.InvoiceLineId ASC
            LIMIT :page_size OFFSET :offset
            """,
            {
                "customer_id": customer.customer_id,
                "invoice_id": query.invoice_id,
                "search": query.search,
                "page_size": query.limit + 1,
                "offset": query.offset,
            },
        ).fetchall()

    # The extra row is a pagination signal, never part of the customer-facing page.
    items = [dict(row) for row in rows[: query.limit]]
    for item in items:
        item["unit_price"] = _money(item["unit_price"])
        item["invoice_total"] = _money(item["invoice_total"])
    has_more = len(rows) > query.limit
    return {
        "status": "ok" if items else "no_authorized_records",
        "items": items,
        "returned": len(items),
        "has_more": has_more,
        "next_offset": query.offset + len(items) if has_more else None,
        "scope": "authenticated_customer",
        "unit": "invoice_line",
        "currency": None,  # Chinook has prices but no currency code.
    }


# --- Support authorization: fresh scoped invoice check ------------------------


def owns_invoice(context: CustomerContext, invoice_id: int) -> bool:
    """Return whether this invoice belongs to the caller at execution time.

    Missing and foreign invoices both return False. The support store calls this
    after review, so an earlier proposal or lookup cannot stand in for authorization.
    Input validation and database failures propagate rather than granting access.
    """
    customer = require_customer(context)
    invoice_id = PurchaseQuery(invoice_id=invoice_id).invoice_id
    with read_connection() as connection:
        return (
            connection.execute(
                "SELECT 1 FROM Invoice WHERE InvoiceId = ? AND CustomerId = ?",
                (invoice_id, customer.customer_id),
            ).fetchone()
            is not None
        )


# --- Music catalog: fixed allowlists for the pinned Chinook 1.4.5 dataset -------

# Audio alone is not proof of music, and a music genre can still contain video.
# Unknown media/genres and tracks with missing classifications are excluded.
# These are source-controlled SQL literals, never interpolated model input.
_MUSIC_CATALOG = """
    WITH music AS (
        SELECT t.TrackId AS track_id, t.Name AS track,
               al.Title AS album, ar.Name AS artist, ar.ArtistId AS artist_id,
               g.Name AS genre, g.GenreId AS genre_id, mt.Name AS media_type,
               t.UnitPrice AS unit_price
        FROM Track t
        LEFT JOIN Album al ON al.AlbumId = t.AlbumId
        LEFT JOIN Artist ar ON ar.ArtistId = al.ArtistId
        JOIN Genre g ON g.GenreId = t.GenreId
        JOIN MediaType mt ON mt.MediaTypeId = t.MediaTypeId
        WHERE t.MediaTypeId IN (1, 2, 4, 5)
          AND t.GenreId IN (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 23, 24, 25)
    )
"""


def search_catalog(query: CatalogQuery, *, path: Path | None = None) -> dict:
    """Return a stable, bounded page of music-only public catalog records.

    Literal search and exact case-insensitive genre must both match if supplied.
    A look-ahead row determines has_more/next_offset. Ownership is not checked;
    call get_recommendations for customer-specific unowned suggestions.
    """
    query = CatalogQuery.model_validate(query)
    with read_connection(path) as connection:
        rows = connection.execute(
            _MUSIC_CATALOG
            + """
            SELECT track_id, track, album, artist, genre, media_type, unit_price
            FROM music
            WHERE (:genre IS NULL OR lower(genre) = lower(:genre))
              AND (:search IS NULL
                   OR instr(lower(track), lower(:search)) > 0
                   OR instr(lower(album), lower(:search)) > 0
                   OR instr(lower(artist), lower(:search)) > 0)
            ORDER BY track_id
            LIMIT :page_size OFFSET :offset
            """,
            {**query.model_dump(exclude={"limit"}), "page_size": query.limit + 1},
        ).fetchall()
    # The extra row is a pagination signal, never part of the customer-facing page.
    items = [dict(row) for row in rows[: query.limit]]
    for item in items:
        item["unit_price"] = _money(item["unit_price"])
    has_more = len(rows) > query.limit
    return {
        "status": "ok" if items else "no_matching_music",
        "items": items,
        "returned": len(items),
        "has_more": has_more,
        "next_offset": query.offset + len(items) if has_more else None,
        "ownership_checked": False,
        "currency": None,
    }


# --- Recommendations: customer history, hard exclusions, explainable ranking ---


def get_recommendations(
    context: CustomerContext, query: RecommendationQuery, *, path: Path | None = None
) -> dict:
    """Rank unowned music by distinct owned genre/artist tracks, then track ID.

    An explicit genre is a hard filter. Without one, only previously purchased
    music genres qualify. A customer with no music history needs to name a genre;
    those suggestions are labeled as genre-based, not personalized from history.
    Optional artist variety keeps each artist's best eligible candidate before
    applying the global ranking and limit; all hard exclusions still apply.

    Return at most the requested count, with evidence counts and a status that
    distinguishes no eligible candidates from needing a genre preference. History
    and candidates share one read transaction. Database errors reach the tool layer.
    """
    customer = require_customer(context)
    query = RecommendationQuery.model_validate(query)
    with read_connection(path) as connection:
        # Read history and candidates from one SQLite snapshot.
        connection.execute("BEGIN")
        history_count = connection.execute(
            _MUSIC_CATALOG
            + """
            SELECT count(DISTINCT m.track_id)
            FROM music m JOIN InvoiceLine il ON il.TrackId = m.track_id
            JOIN Invoice i ON i.InvoiceId = il.InvoiceId
            WHERE i.CustomerId = :customer_id
            """,
            {"customer_id": customer.customer_id},
        ).fetchone()[0]
        # Count each owned track once, then rank only eligible unowned candidates.
        # Per-artist row numbers enforce requested variety before the global limit.
        rows = connection.execute(
            _MUSIC_CATALOG
            + """
            , owned AS (
                SELECT DISTINCT il.TrackId AS track_id
                FROM Invoice i JOIN InvoiceLine il ON il.InvoiceId = i.InvoiceId
                WHERE i.CustomerId = :customer_id
            ), owned_music AS (
                SELECT m.* FROM music m JOIN owned o ON o.track_id = m.track_id
            ), genre_counts AS (
                SELECT genre_id, count(*) AS owned_genre_tracks
                FROM owned_music GROUP BY genre_id
            ), artist_counts AS (
                SELECT artist_id, count(*) AS owned_artist_tracks
                FROM owned_music GROUP BY artist_id
            ), candidates AS (
            SELECT m.track_id, m.track, m.album, m.artist, m.genre, m.media_type,
                   m.unit_price,
                   coalesce(gc.owned_genre_tracks, 0) AS owned_genre_tracks,
                   coalesce(ac.owned_artist_tracks, 0) AS owned_artist_tracks,
                   row_number() OVER (
                       PARTITION BY m.artist_id
                       ORDER BY coalesce(gc.owned_genre_tracks, 0) DESC,
                                coalesce(ac.owned_artist_tracks, 0) DESC, m.track_id
                   ) AS artist_choice
            FROM music m
            LEFT JOIN genre_counts gc ON gc.genre_id = m.genre_id
            LEFT JOIN artist_counts ac ON ac.artist_id = m.artist_id
            WHERE NOT EXISTS (SELECT 1 FROM owned o WHERE o.track_id = m.track_id)
              AND (:genre IS NULL OR lower(m.genre) = lower(:genre))
              AND (:genre IS NOT NULL OR coalesce(gc.owned_genre_tracks, 0) > 0)
            )
            SELECT track_id, track, album, artist, genre, media_type, unit_price,
                   owned_genre_tracks, owned_artist_tracks
            FROM candidates
            WHERE (:different_artists = 0 OR artist_choice = 1)
            ORDER BY owned_genre_tracks DESC, owned_artist_tracks DESC, track_id
            LIMIT :limit
            """,
            {"customer_id": customer.customer_id, **query.model_dump()},
        ).fetchall()
    items = [dict(row) for row in rows]
    for item in items:
        item["unit_price"] = _money(item["unit_price"])
        item["basis"] = (
            "purchase_history"
            if item["owned_genre_tracks"] or item["owned_artist_tracks"]
            else "requested_genre"
        )
    status = "ok" if items else "no_matching_unowned_music"
    if not history_count and query.genre is None:
        status = "needs_genre_preference"
    return {
        "status": status,
        "items": items,
        "returned": len(items),
        "requested": query.limit,
        "requested_genre": query.genre,
        "owned_music_tracks": history_count,
        "ranking": ("one_per_artist, " if query.different_artists else "")
        + "owned_genre_tracks_desc, owned_artist_tracks_desc, track_id_asc",
        "different_artists": query.different_artists,
        "scope": "authenticated_customer",
        "owned_tracks_excluded": True,
        "currency": None,
    }
