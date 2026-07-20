"""PR 6.3a — typed failures for the SCADA machine-boundary client.

Mirror the fail-closed taxonomy of ``control_client_errors``: each maps a distinct SCADA
outcome to a distinct scheduler-side handling. NONE of these is ever silently swallowed.
"""

from __future__ import annotations


class ScadaClientError(Exception):
    """Base machine-boundary client failure."""


class ScadaUnavailableError(ScadaClientError):
    """SCADA is dark (503) or unreachable (transport/timeout). RETRYABLE: the dispatcher
    persists nothing and re-dispatches next tick (SCADA replays its idempotent receipt)."""


class ScadaServiceAuthError(ScadaClientError):
    """SCADA rejected the service token (401). A minting/secret/clock misconfiguration."""


class ScadaIntentRejectedError(ScadaClientError):
    """SCADA returned 422 schema_invalid — the compiled intent violates the frozen 6.0 schema.
    Unreachable absent a Python<->Ajv schema drift (the outbox intent passed the IDENTICAL schema
    at compile time). There is no receipt to persist, so the intent is re-attempted LOUDLY once
    per dispatch tick (the tick interval is the backoff) until the source drift is fixed — a
    bounded dead-letter for it is a PR 6.4 (observability) concern."""


class ScadaContractViolation(ScadaClientError):
    """A non-200/409 status, a non-JSON/contract-violating body, or a receipt whose echoed
    identity (intent_id / idempotency_key / intent_content_hash) does not match what was
    dispatched. Never persisted."""
