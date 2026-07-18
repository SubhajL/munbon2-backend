"""Typed failures for the strict control-plan upstream clients (PR 4.3a)."""


class UpstreamUnavailableError(Exception):
    """Upstream service, its store, or the network is unavailable (HTTP 503)."""


class UpstreamContractViolation(Exception):
    """Upstream answered with a payload that violates its contract (HTTP 502)."""


class RequirementStateError(Exception):
    """Requirements exist but are not in a plannable exact state (HTTP 409)."""

    def __init__(self, reason: str, detail: dict | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.detail = detail or {}


class RequirementsUnpublishedError(UpstreamUnavailableError):
    """No published requirement run covers a requested scope (HTTP 503)."""


class FlowLineageConflictError(Exception):
    """Flow rejected the prediction pins: the model drifted mid-draft (409)."""


class PredictionRequestRejectedError(Exception):
    """Flow rejected our composed prediction request: a scheduler bug (500)."""
