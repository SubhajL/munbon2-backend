"""
core.demand_store — the Wave 2.4 immutable versioned store contract + the pure
in-memory reference implementation.

HIGH #8 semantics: demand records, allocation records, and delivery observations are
three SEPARATE append-only stores. Nothing is ever updated in place — a correction is
the next version (strictly latest+1) of the same logical key; identical resubmissions
replay idempotently; rewriting an existing version is an immutability violation.

`db.demand_store_postgres.PostgresDemandStore` implements the same interface (pinned
by test) for the runtime path; this in-memory twin is the executable specification.
"""
from copy import deepcopy
from dataclasses import dataclass

from core.demand_contract import content_hash

__all__ = [
    "EXCLUDED_FROM_HASH",
    "KINDS",
    "DemandStoreError",
    "DemandStoreUnavailable",
    "DuplicateIdempotencyKey",
    "ImmutabilityViolation",
    "InMemoryDemandStore",
    "PutResult",
    "VersionConflict",
    "semantic_content_hash",
    "validate_put_args",
]

KINDS = ("demand", "allocation", "delivery")

# Transport/envelope fields: a crash-recovered producer regenerates these while the
# record it derived is identical — they must not defeat idempotent replay.
EXCLUDED_FROM_HASH = frozenset({"idempotency_key", "computed_at"})


def semantic_content_hash(record: dict) -> str:
    """content_hash over the record's semantic content (transport fields excluded)."""
    return content_hash(
        {key: value for key, value in record.items() if key not in EXCLUDED_FROM_HASH}
    )


class DemandStoreUnavailable(RuntimeError):
    """The backing store failed — answer unavailable (fail closed), never empty.

    Lives in core (not db) so api.control can classify it as 503 without breaking
    its no-db-imports isolation rule.
    """


class DemandStoreError(ValueError):
    """A store request violates the append-only versioned-store contract."""


class ImmutabilityViolation(DemandStoreError):
    """An existing (logical_key, version) was resubmitted with different content."""


class VersionConflict(DemandStoreError):
    """A submitted version is not exactly latest+1 for its logical key."""


class DuplicateIdempotencyKey(DemandStoreError):
    """An idempotency key was reused for different content."""


@dataclass(frozen=True)
class PutResult:
    replayed: bool
    version: int
    content_hash: str


def validate_put_args(kind: str, version: int, idempotency_key: str) -> None:
    if kind not in KINDS:
        raise DemandStoreError(f"unknown kind {kind!r}; expected one of {KINDS}")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise DemandStoreError("version must be a positive integer")
    if not idempotency_key or not idempotency_key.strip():
        raise DemandStoreError("idempotency key must be non-empty")


def require_known_kind(kind: str) -> None:
    if kind not in KINDS:
        raise DemandStoreError(f"unknown kind {kind!r}; expected one of {KINDS}")


class InMemoryDemandStore:
    """Append-only reference store; envelopes are defensive copies both ways."""

    def __init__(self):
        self._records: dict[str, dict[str, list[dict]]] = {kind: {} for kind in KINDS}
        self._idempotency: dict[str, dict[str, tuple[str, int, str]]] = {
            kind: {} for kind in KINDS
        }

    async def put(
        self,
        kind: str,
        logical_key: str,
        version: int,
        idempotency_key: str,
        record: dict,
    ) -> PutResult:
        validate_put_args(kind, version, idempotency_key)
        digest = semantic_content_hash(record)
        seen = self._idempotency[kind].get(idempotency_key)
        if seen is not None:
            if seen == (logical_key, version, digest):
                return PutResult(replayed=True, version=version, content_hash=digest)
            raise DuplicateIdempotencyKey(
                f"idempotency key {idempotency_key!r} was already used for different content"
            )
        # No setdefault before validation: a rejected put must leave no trace
        # (an empty history list would crash current() forever after one 409).
        history = self._records[kind].get(logical_key, [])
        existing = next((e for e in history if e["version"] == version), None)
        if existing is not None:
            if existing["content_hash"] == digest:
                # Replay by content: BIND the new key so its later reuse for
                # different content still raises DuplicateIdempotencyKey.
                self._idempotency[kind][idempotency_key] = (
                    logical_key,
                    version,
                    digest,
                )
                return PutResult(replayed=True, version=version, content_hash=digest)
            raise ImmutabilityViolation(
                f"{kind} {logical_key!r} version {version} exists with different content — "
                "corrections must be submitted as the next version"
            )
        latest_version = history[-1]["version"] if history else 0
        if version != latest_version + 1:
            raise VersionConflict(
                f"{kind} {logical_key!r}: expected version {latest_version + 1}, got {version}"
            )
        self._records[kind].setdefault(logical_key, []).append(
            {
                "logical_key": logical_key,
                "version": version,
                "content_hash": digest,
                "record": deepcopy(record),
            }
        )
        self._idempotency[kind][idempotency_key] = (logical_key, version, digest)
        return PutResult(replayed=False, version=version, content_hash=digest)

    async def latest(self, kind: str, logical_key: str) -> dict | None:
        require_known_kind(kind)
        history = self._records[kind].get(logical_key)
        return deepcopy(history[-1]) if history else None

    async def current(self, kind: str) -> list[dict]:
        require_known_kind(kind)
        return [deepcopy(history[-1]) for history in self._records[kind].values()]

    async def history(self, kind: str, logical_key: str) -> list[dict]:
        require_known_kind(kind)
        return deepcopy(self._records[kind].get(logical_key, []))
