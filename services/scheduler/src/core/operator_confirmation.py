"""Exact operator confirmation phrases for control-authority mutations."""

from __future__ import annotations

from typing import Optional


class OperatorConfirmationError(Exception):
    """The presented confirmation does not bind the requested mutation."""


_PLAN_ACTIONS = frozenset({"approve-shadow", "activate", "hold", "resume", "grant"})
_GRANT_ACTIONS = frozenset({"renew", "revoke"})


def expected_confirmation(
    action: str, identity: str, version: Optional[int] = None
) -> str:
    """Build the one accepted phrase for a closed-set control action."""
    if action in _PLAN_ACTIONS:
        if not identity or isinstance(version, bool) or not isinstance(version, int):
            raise OperatorConfirmationError(
                "a plan action requires plan id and version"
            )
        return f"{action.upper()} {identity} v{version}"
    if action in _GRANT_ACTIONS:
        if not identity or version is not None:
            raise OperatorConfirmationError("a grant action requires only a grant id")
        return f"{action.upper()} {identity}"
    raise OperatorConfirmationError(f"unsupported control action: {action!r}")


def require_exact_confirmation(
    presented: Optional[str],
    action: str,
    identity: str,
    version: Optional[int] = None,
) -> None:
    """Fail closed unless the presented phrase exactly matches the mutation."""
    if presented != expected_confirmation(action, identity, version):
        raise OperatorConfirmationError(
            "operator confirmation does not match the action"
        )
