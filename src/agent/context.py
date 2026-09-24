"""Shared input definitions and validation for the agent and database.

CustomerContext comes from the trusted caller (simulated in Studio), separately
from chat. Query models hold business filters and never include customer identity.
"""

# --- Imports -----------------------------------------------------------------

from dataclasses import dataclass
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

# --- Trusted runtime context: immutable for an invocation ---------------------


@dataclass(frozen=True)
class CustomerContext:
    """Immutable customer identity supplied by the trusted invocation adapter.

    A positive ID validates the value's shape; it does not authenticate a person.
    The adapter must authorize that identity and its thread/checkpoint access.
    """

    customer_id: int

    def __post_init__(self) -> None:
        """Require a positive SQLite-sized integer at construction and execution-time recheck."""
        # bool is an int subclass; do not silently accept it as an identity.
        if type(self.customer_id) is not int or not 0 < self.customer_id <= 2**63 - 1:
            raise ValueError(
                "customer_id must be a positive 64-bit integer from the trusted caller"
            )


def require_customer(context: CustomerContext | None) -> CustomerContext:
    """Return validated trusted context, or raise ValueError before data access.

    Used by both graph middleware and sensitive tools so direct execution or
    resume cannot treat missing identity as an unscoped database query.
    """
    if not isinstance(context, CustomerContext):
        raise ValueError("Trusted CustomerContext is required; identity cannot come from chat")
    context.__post_init__()
    return context


# --- Model-selected filters: reusable field constraints -----------------------

# Strict integer/boolean fields avoid coercion at the trust boundary. Text is
# trimmed and bounded here; literal matching and ownership remain SQL concerns.

PositiveId = Annotated[int, Field(strict=True, gt=0, le=2**63 - 1)]
SearchText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
PageSize = Annotated[int, Field(strict=True, ge=1, le=50)]
PageOffset = Annotated[int, Field(strict=True, ge=0, le=10_000)]
RecommendationCount = Annotated[int, Field(strict=True, ge=1, le=10)]
DifferentArtists = Annotated[bool, Field(strict=True)]
SupportReason = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)
]


# --- Validated purchase filters ----------------------------------------------


class PurchaseQuery(BaseModel):
    """Bounded invoice/search filters; customer identity is intentionally absent.

    Optional filters narrow the caller's records. Offset/limit select invoice
    lines, not complete invoices. Extra fields are rejected before SQL executes.
    """

    model_config = ConfigDict(extra="forbid")
    invoice_id: PositiveId | None = None
    search: SearchText | None = None
    limit: PageSize = 20
    offset: PageOffset = 0


# --- Music discovery: catalog filters and recommendation preferences ----------


class CatalogQuery(BaseModel):
    """Public catalog filters with bounded paging and optional exact genre.

    Search is a literal substring across track, album and artist. These inputs
    never establish whether the caller owns a catalog result.
    """

    model_config = ConfigDict(extra="forbid")
    search: SearchText | None = None
    genre: SearchText | None = None
    limit: PageSize = 20
    offset: PageOffset = 0


class RecommendationQuery(BaseModel):
    """Select genre, count and optional one-track-per-artist recommendations.

    These are preference filters. The caller cannot disable music eligibility
    or ownership exclusions; SQL always enforces both.
    """

    model_config = ConfigDict(extra="forbid")
    genre: SearchText | None = None
    limit: RecommendationCount = 3
    different_artists: DifferentArtists = False


# --- Support action: reviewed business arguments, never approval or identity ---


class SupportRequestInput(BaseModel):
    """Validate the final invoice and reason after any reviewer edits.

    Neither approval nor customer identity belongs in model-selected arguments.
    The middleware supplies the review gate; storage rechecks invoice ownership.
    """

    model_config = ConfigDict(extra="forbid")
    invoice_id: PositiveId
    reason: SupportReason
