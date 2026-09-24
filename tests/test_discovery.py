"""Verify catalog grounding and recommendation exclusions against real Chinook.

Expected ownership and evidence are derived independently from invoice records.
Dataset mutations are confined to temporary copies, never the runtime database.
"""

# --- Imports -----------------------------------------------------------------

import shutil
import sqlite3
from collections import Counter

import pytest
from pydantic import ValidationError

from agent.context import CatalogQuery, CustomerContext, RecommendationQuery
from agent.database import get_recommendations, read_connection, search_catalog

# --- Public catalog: music classification, grounding and paging ---------------


def test_catalog_pages_cover_only_music_without_duplicates():
    """Compare all catalog pages with independent source joins, including the Alternative
    video trap.
    """
    items = []
    offset = 0
    while True:
        page = search_catalog(CatalogQuery(limit=50, offset=offset))
        assert page["ownership_checked"] is False
        items.extend(page["items"])
        if not page["has_more"]:
            break
        offset = page["next_offset"]
    with read_connection() as c:
        # Independent negative checks on actual media/genre names, including the
        # video classified as Alternative that a genre-only filter would admit.
        expected = c.execute(
            """SELECT t.TrackId, t.Name, a.Title, ar.Name AS artist
               FROM Track t JOIN MediaType mt USING(MediaTypeId)
               JOIN Genre g USING(GenreId) JOIN Album a USING(AlbumId)
               JOIN Artist ar USING(ArtistId)
               WHERE mt.Name NOT LIKE '%video%'
                 AND g.Name NOT IN ('Science Fiction','TV Shows','Sci Fi & Fantasy',
                                    'Drama','Comedy') ORDER BY t.TrackId"""
        ).fetchall()
    assert len(items) == len({i["track_id"] for i in items}) == 3289
    assert [(i["track_id"], i["track"], i["album"], i["artist"]) for i in items] == [
        tuple(r) for r in expected
    ]


@pytest.mark.parametrize("search", ["Miles Davis", "%' OR 1=1 --", "%", "_"])
def test_catalog_search_is_literal_and_genre_is_exact(search):
    """Combine genre normalization with literal search, rejecting wildcard and SQL-injection
    expansion.
    """
    result = search_catalog(CatalogQuery(search=search, genre=" jAzZ ", limit=50))
    assert all(i["genre"] == "Jazz" for i in result["items"])
    assert all(
        any(search.lower() in (i[field] or "").lower() for field in ("track", "album", "artist"))
        for i in result["items"]
    )
    if search == "Miles Davis":
        assert result["items"]
        assert all(i["artist"] == "Miles Davis" for i in result["items"])
    else:
        assert result["items"] == []
    assert search_catalog(CatalogQuery(genre="Rock%' OR 1=1 --"))["items"] == []


# --- Full-history ownership and evidence: all 59 real customers ---------------


@pytest.mark.parametrize("different_artists", [False, True])
def test_recommendations_exclude_owned_and_ground_evidence_for_every_customer(different_artists):
    """Check all 59 customers against raw history, with artist variety both enabled and disabled."""
    with read_connection() as c:
        tracks = {
            r["TrackId"]: dict(r)
            for r in c.execute(
                """SELECT t.TrackId, t.Name, t.MediaTypeId, t.GenreId, g.Name AS genre,
                          a.ArtistId, ar.Name AS artist
                   FROM Track t JOIN Genre g USING(GenreId)
                   JOIN Album a USING(AlbumId) JOIN Artist ar USING(ArtistId)"""
            )
        }
        for customer_id in range(1, 60):
            owned = {
                r[0]
                for r in c.execute(
                    """SELECT il.TrackId FROM Invoice i JOIN InvoiceLine il USING(InvoiceId)
                       WHERE i.CustomerId=?""",
                    (customer_id,),
                )
            }
            music = [tracks[t] for t in owned if tracks[t]["MediaTypeId"] != 3]
            genres = Counter(t["GenreId"] for t in music)
            artists = Counter(t["ArtistId"] for t in music)
            result = get_recommendations(
                CustomerContext(customer_id),
                RecommendationQuery(limit=10, different_artists=different_artists),
            )
            assert result["owned_music_tracks"] == len(music)
            assert result["returned"] == 10
            if different_artists:
                assert len({item["artist"] for item in result["items"]}) == 10
            assert len({i["track_id"] for i in result["items"]}) == 10
            for item in result["items"]:
                canonical = tracks[item["track_id"]]
                assert item["track_id"] not in owned
                assert canonical["MediaTypeId"] != 3
                assert canonical["GenreId"] not in {18, 19, 20, 21, 22}
                assert item["track"] == canonical["Name"]
                assert item["artist"] == canonical["artist"]
                assert item["genre"] == canonical["genre"]
                assert item["owned_genre_tracks"] == genres[canonical["GenreId"]] > 0
                assert item["owned_artist_tracks"] == artists[canonical["ArtistId"]]


def test_explicit_genre_and_stable_ranking():
    """Verify normalized Rock filtering, deterministic ordering and distinct-history evidence
    counts.
    """
    query = RecommendationQuery(genre=" rock ", limit=3)
    first = get_recommendations(CustomerContext(1), query)
    assert first == get_recommendations(CustomerContext(1), query)
    assert first["returned"] == 3
    assert all(i["genre"] == "Rock" and i["owned_genre_tracks"] == 14 for i in first["items"])
    assert first["items"] == sorted(
        first["items"],
        key=lambda i: (-i["owned_genre_tracks"], -i["owned_artist_tracks"], i["track_id"]),
    )


# --- Empty history, exhausted catalog and unfamiliar classifications ----------


@pytest.fixture
def writable_copy(chinook_path, tmp_path):
    """Copy the session database into a writable per-test fixture for controlled source
    mutations.
    """
    target = tmp_path / "discovery.sqlite"
    shutil.copyfile(chinook_path, target)
    target.chmod(0o600)
    return target


def test_video_only_history_needs_preference_and_never_fakes_personalization(writable_copy):
    """Require a genre for video-only history and label explicit-genre results without false
    history.
    """
    with sqlite3.connect(writable_copy) as c:
        c.execute(
            "DELETE FROM InvoiceLine WHERE InvoiceId IN "
            "(SELECT InvoiceId FROM Invoice WHERE CustomerId=1) AND InvoiceId != 98"
        )
    result = get_recommendations(CustomerContext(1), RecommendationQuery(), path=writable_copy)
    assert result["status"] == "needs_genre_preference"
    assert result["items"] == []
    result = get_recommendations(
        CustomerContext(1), RecommendationQuery(genre="Rock"), path=writable_copy
    )
    assert result["returned"] == 3
    assert result["owned_music_tracks"] == 0
    assert all(
        i["basis"] == "requested_genre" and i["owned_genre_tracks"] == i["owned_artist_tracks"] == 0
        for i in result["items"]
    )


def test_owned_candidate_removed_even_from_old_invoice(writable_copy):
    """Exclude a newly owned candidate across full history without double-counting repeat
    purchases.
    """
    context, query = CustomerContext(1), RecommendationQuery(genre="Rock")
    original = get_recommendations(context, query, path=writable_copy)
    track_id = original["items"][0]["track_id"]
    with sqlite3.connect(writable_copy) as c:
        invoice = c.execute(
            "SELECT InvoiceId FROM Invoice WHERE CustomerId=1 ORDER BY InvoiceDate LIMIT 1"
        ).fetchone()[0]
        # Duplicate purchases must not inflate the distinct-track evidence.
        c.executemany(
            "INSERT INTO InvoiceLine (InvoiceId,TrackId,UnitPrice,Quantity) VALUES (?,?,0.99,1)",
            [(invoice, track_id), (invoice, track_id)],
        )
    result = get_recommendations(context, query, path=writable_copy)
    assert track_id not in {i["track_id"] for i in result["items"]}
    assert result["owned_music_tracks"] == original["owned_music_tracks"] + 1
    assert all(i["owned_genre_tracks"] == 15 for i in result["items"])


def test_exhausted_genre_and_unknown_classifications_fail_closed(writable_copy):
    """Test empty eligible sets and reject missing/unknown classifications or non-music genres."""
    with sqlite3.connect(writable_copy) as c:
        opera = c.execute("SELECT TrackId FROM Track WHERE GenreId=25").fetchone()[0]
        c.execute(
            "INSERT INTO InvoiceLine (InvoiceId,TrackId,UnitPrice,Quantity) VALUES (98,?,0.99,1)",
            (opera,),
        )
        c.execute("UPDATE Track SET GenreId=NULL WHERE TrackId=1")
        c.execute("INSERT INTO MediaType VALUES (99,'Unclassified audio file')")
        c.execute("UPDATE Track SET MediaTypeId=99 WHERE TrackId=2")
        # Even audio content tagged as drama must be excluded.
        c.execute("UPDATE Track SET GenreId=21 WHERE TrackId=3")
    result = get_recommendations(
        CustomerContext(1), RecommendationQuery(genre="Opera"), path=writable_copy
    )
    assert result["status"] == "no_matching_unowned_music"
    assert result["items"] == []
    page = search_catalog(CatalogQuery(), path=writable_copy)
    assert not {1, 2, 3}.intersection(i["track_id"] for i in page["items"])
    for genre in ("Drama", "TV Shows", "Unknown", "Rock' OR 1=1 --"):
        assert (
            get_recommendations(
                CustomerContext(1), RecommendationQuery(genre=genre), path=writable_copy
            )["items"]
            == []
        )


# --- Preference validation and trusted caller requirements ---------------------


@pytest.mark.parametrize(
    "query", [{"limit": 0}, {"limit": 11}, {"limit": True}, {"customer_id": 2}, {"genre": " "}]
)
def test_invalid_recommendation_inputs(query):
    """Reject excessive counts, invalid filters and caller identity in preference arguments."""
    with pytest.raises(ValidationError):
        RecommendationQuery(**query)


def test_recommendation_requires_trusted_context():
    """Prevent a direct recommendation query from bypassing the runtime identity requirement."""
    with pytest.raises(ValueError, match="Trusted CustomerContext"):
        get_recommendations(None, RecommendationQuery())


# --- Requested artist variety: ranking, shortage and strict option validation --


def test_artist_variety_keeps_default_ranking_and_respects_genre_shortage():
    """Preserve default ordering while enforcing unique artists and honest short or empty lists."""
    default = get_recommendations(CustomerContext(1), RecommendationQuery(genre="Rock"))
    assert [item["track_id"] for item in default["items"]] == [1146, 1147, 1148]
    varied = get_recommendations(
        CustomerContext(1), RecommendationQuery(genre="Rock", different_artists=True)
    )
    assert varied["returned"] == 3
    assert len({item["artist"] for item in varied["items"]}) == 3
    assert all(item["genre"] == "Rock" for item in varied["items"])
    assert varied["items"][0] == default["items"][0]
    for genre, count in [("Opera", 1), ("TV Shows", 0)]:
        result = get_recommendations(
            CustomerContext(1), RecommendationQuery(genre=genre, different_artists=True)
        )
        assert result["returned"] == count


@pytest.mark.parametrize("value", [1, "true", None])
def test_artist_variety_requires_a_boolean(value):
    """Reject coercion from integers, strings or null into the optional artist constraint."""
    with pytest.raises(ValidationError):
        RecommendationQuery(different_artists=value)
