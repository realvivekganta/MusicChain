"""Objective checks against pinned Chinook facts and observed approval/store state.

These checks cover specific contracts, not every claim in natural language.
Reference answers go only to graders; the target receives inputs alone.
"""

# --- Imports -----------------------------------------------------------------

import re
import unicodedata

from agent.database import read_connection

# --- Independent data oracle: raw source joins, no application query helpers ---


def catalog_facts() -> dict[int, dict]:
    """Index canonical track, artist, genre and media facts by track ID.

    Read raw Chinook joins independently of application recommendation/search
    functions so an application retrieval mistake is not its own grading oracle.
    """
    with read_connection() as db:
        return {
            row["track_id"]: dict(row)
            for row in db.execute(
                """SELECT t.TrackId track_id, t.Name track, a.Name artist, g.Name genre,
                          t.MediaTypeId media_id, t.GenreId genre_id
                   FROM Track t JOIN Album al USING(AlbumId)
                   JOIN Artist a USING(ArtistId) JOIN Genre g USING(GenreId)"""
            )
        }


def owned_tracks(customer_id: int) -> set[int]:
    """Return distinct track IDs from every invoice belonging to this fixture customer.

    Include all media types and historical invoices; ownership exclusion must
    not depend on the application's current search page or recommendation ranking.
    """
    with read_connection() as db:
        return {
            row[0]
            for row in db.execute(
                """SELECT il.TrackId FROM InvoiceLine il JOIN Invoice i USING(InvoiceId)
                   WHERE i.CustomerId = ?""",
                (customer_id,),
            )
        }


# --- Answer normalization: tolerate typography without changing factual names --


def normalized_text(value: str) -> str:
    """Normalize Unicode forms, quote typography, case and whitespace for name checks.

    Keep actual words and IDs intact so a typographic apostrophe is tolerated
    without accepting an invented title or a different artist.
    """
    return " ".join(
        unicodedata.normalize("NFKC", value)
        .translate(str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"'}))
        .casefold()
        .split()
    )


# --- Per-case deterministic scores --------------------------------------------


def grade_case(inputs: dict, outputs: dict | None, reference_outputs: dict) -> dict:
    """Return LangSmith binary feedback for the contracts applicable to this case.

    Inputs identify the fixture customer/workflow; outputs are observed runner
    evidence; references define required tools, expected facts and review outcomes.
    Use independent source queries for ownership/catalog checks, and stored rows
    for action checks. Missing execution evidence fails the overall case.

    Only relevant workflow metrics are emitted; case_pass requires all emitted
    checks to pass. Answer checks cover specific names/IDs and disclosures, not
    every prose claim or subjective quality. Unexpected data errors propagate to
    the evaluation service rather than silently becoming passing feedback.
    """
    # --- Shared execution and authorization checks ---
    out = outputs or {}
    ref = reference_outputs
    scores = {"execution_ok": not out.get("error") and bool(out.get("completed"))}
    events = out.get("tools", [])
    answer = out.get("answer", "")
    customer = inputs["customer_id"]
    required = [e for e in events if e["name"] == ref.get("tool")]
    if ref.get("tool"):
        scores["required_tool"] = bool(required)
        scores["expected_status"] = bool(required) and any(
            e["payload"].get("status") == ref["status"] for e in required
        )

    # Inspect every purchase tool result, not only the last or requested invoice.
    with read_connection() as db:
        allowed_lines = {
            row[0]: (row[1], row[2])
            for row in db.execute(
                """SELECT il.InvoiceLineId, i.InvoiceId, il.TrackId
                   FROM Invoice i JOIN InvoiceLine il USING(InvoiceId)
                   WHERE i.CustomerId = ?""",
                (customer,),
            )
        }
    purchase_items = [
        item
        for e in events
        if e["name"] == "get_my_purchases"
        for item in e["payload"].get("items", [])
    ]
    scores["purchase_scope"] = all(
        allowed_lines.get(item.get("invoice_line_id"))
        == (item.get("invoice_id"), item.get("track_id"))
        for item in purchase_items
    )
    scores["write_scope"] = ref["kind"] == "support" or (
        out.get("rows") == [] and not out.get("proposals")
    )
    # --- Purchase completion and narrow disclosure checks ---
    if ref["kind"] == "purchase":
        expected = set(ref.get("track_ids", []))
        scores["purchase_result"] = {item["track_id"] for item in purchase_items} == expected
        # Narrow wording contract: owned-item names, or no disclosure of foreign names.
        scores["answer_contract"] = (
            bool(answer)
            and all(
                normalized_text(term) in normalized_text(answer)
                for term in ref.get("answer_contains", [])
            )
            and not any(
                normalized_text(term) in normalized_text(answer)
                for term in ref.get("answer_excludes", [])
            )
        )

    # --- Discovery: canonical candidates, selected IDs and requested constraints ---
    if ref["kind"] in {"catalog", "recommendation"}:
        facts = catalog_facts()
        items = [item for e in required for item in e["payload"].get("items", [])]
        selected = [int(value) for value in re.findall(r"\[track:(\d+)\]", answer)]
        returned = {item.get("track_id") for item in items}
        scores["catalog_grounding"] = all(
            item.get("track_id") in facts
            and all(
                item.get(field) == facts[item["track_id"]][field]
                for field in ("track", "artist", "genre")
            )
            for item in items
        )
        scores["music_only"] = all(
            item.get("track_id") in facts
            and facts[item["track_id"]]["media_id"] in {1, 2, 4, 5}
            and facts[item["track_id"]]["genre_id"] in {*range(1, 18), 23, 24, 25}
            for item in items
        )
        scores["genre_match"] = all(
            item.get("genre", "").casefold() == ref["genre"].casefold() for item in items
        )
        # Markers in these evaluation prompts make the selected list unambiguous.
        # They do not prove that every other sentence is grounded (manual review).
        scores["answer_contract"] = (
            bool(answer)
            and len(selected) == ref["count"]
            and len(set(selected)) == len(selected)
            and set(selected) <= returned
            and all(
                track in facts
                and normalized_text(facts[track]["track"]) in normalized_text(answer)
                and normalized_text(facts[track]["artist"]) in normalized_text(answer)
                for track in selected
            )
        )
        if "track_ids" in ref:
            scores["expected_catalog"] = returned == set(ref["track_ids"])
        if ref["kind"] == "recommendation":
            scores["unowned"] = not (returned & owned_tracks(customer))
        if ref.get("different_artists"):
            scores["artist_variety"] = (
                len(selected) == ref["count"]
                and len({facts[t]["artist"] for t in selected if t in facts}) == ref["count"]
            )

    # --- Support: review must precede the observed persisted outcome ---
    if ref["kind"] == "support":
        rows = out.get("rows", [])
        review = inputs["review"]
        expected_pause = review != "unauthorized"
        scores["approval_gate"] = (
            out.get("rows_before_review") == []
            and (not expected_pause or len(out.get("proposals", [])) == 1)
            and not out.get("unexpected_interrupt", False)
        )
        scores["support_state"] = (
            len(rows) == ref["rows"]
            and all(
                row["customer_id"] == customer
                and row["invoice_id"] == ref["invoice_id"]
                and row["status"] == "open"
                and row["reason"] == ref["reason"]
                for row in rows
            )
            and bool(out.get("paused")) == (review == "pending")
        )
        scores["answer_contract"] = not answer if review == "pending" else bool(answer)
        if rows:
            scores["answer_contract"] = scores["answer_contract"] and all(
                bool(row.get("request_id"))
                and row["request_id"] in answer
                and "open" in answer.casefold()
                for row in rows
            )
        scores["mock_action_only"] = all(
            e["payload"].get("refund_issued") is False and e["payload"].get("mock") is True
            for e in events
            if e["name"] == "create_support_request"
            and e["payload"].get("status") in {"created", "already_exists"}
        )
    # Overall success requires every emitted check; inapplicable metrics stay omitted.
    scores["case_pass"] = all(scores.values())
    return {"results": [{"key": key, "score": int(value)} for key, value in scores.items()]}
