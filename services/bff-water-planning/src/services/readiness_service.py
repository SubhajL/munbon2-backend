"""BFF dependency-truth readiness (PR 4.4a-2).

`/ready` concurrently probes every REQUIRED upstream — the scheduler `/ready`,
flow-monitoring `/ready`, and ros-gis `/ready` — over the lifespan-owned pooled
`httpx.AsyncClient`. Each probe is bounded TWO ways: the httpx per-phase
connect/read limits, AND a hard per-probe WALL-CLOCK (`asyncio.timeout`). httpx's
`Timeout` has no wall-clock — a slow-drip upstream keeps resetting the read
timeout and `/ready` would hang — so the wall-clock is the real ceiling that
guarantees one hung upstream can never stall the check.

Each target also declares the EXACT self-reported status it must return. All
three `/ready` endpoints return "ready", so a `/ready`→`/health` misroute that
answers liveness ("healthy") can never pass as readiness. Any timeout, non-200,
malformed body, wrong/absent status, closed
pooled client, or unexpected error makes the BFF NOT ready (503).

The returned ``checks`` hold only safe status strings — never a hostname, URL, or
raw exception text.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class ProbeTarget:
    name: str
    url: str
    # The EXACT status the upstream must self-report to count as serviceable.
    # Every target requires "ready"; liveness ("healthy") can never satisfy
    # readiness.
    expected_status: str


@dataclass(frozen=True)
class UpstreamProbe:
    name: str
    ok: bool
    status: str


@dataclass(frozen=True)
class ReadinessResult:
    ready: bool
    checks: dict[str, str]


async def probe_upstream(
    client: httpx.AsyncClient,
    target: ProbeTarget,
    timeout: httpx.Timeout,
    wall_clock_seconds: float,
) -> UpstreamProbe:
    """One GET bounded by BOTH the httpx per-phase limits and a hard wall-clock,
    classified into a safe status string. Never raises (except a real task
    cancellation, which is propagated)."""
    try:
        async with asyncio.timeout(wall_clock_seconds):
            response = await client.get(target.url, timeout=timeout)
    except asyncio.CancelledError:
        # A genuine task cancellation is not an upstream fault — never swallow it.
        raise
    except (asyncio.TimeoutError, TimeoutError):
        # The per-probe wall-clock fired: a slow-drip/hung upstream, not ready.
        return UpstreamProbe(target.name, False, "timeout")
    except httpx.TimeoutException:
        return UpstreamProbe(target.name, False, "timeout")
    except Exception:
        # Any other failure (transport error, a closed client mid-flight, a
        # malformed request) fails closed without leaking the exception text.
        return UpstreamProbe(target.name, False, "unreachable")

    if response.status_code != 200:
        # A scheduler/flow /ready that answered 503 lands here: upstream is up but
        # NOT ready → the BFF is not ready either.
        return UpstreamProbe(target.name, False, "unhealthy")
    try:
        body = response.json()
    except ValueError:
        return UpstreamProbe(target.name, False, "malformed")
    if not isinstance(body, dict):
        return UpstreamProbe(target.name, False, "malformed")
    if body.get("status") != target.expected_status:
        # Wrong OR absent status — including a /health "healthy" answered where a
        # /ready "ready" was required — is not serviceable.
        return UpstreamProbe(target.name, False, "unhealthy")
    return UpstreamProbe(target.name, True, "ok")


async def probe_required_upstreams(
    client: httpx.AsyncClient | None,
    targets: list[ProbeTarget],
    timeout: httpx.Timeout,
    wall_clock_seconds: float,
) -> ReadinessResult:
    """Probe every required upstream concurrently; ready only if ALL are ok.

    Fails closed when the pooled client is missing or already closed (a startup
    that never built it, or a shutdown race): every upstream is reported
    unreachable rather than raising a RuntimeError out through `gather`."""
    if client is None or getattr(client, "is_closed", False):
        return ReadinessResult(
            False, {target.name: "unreachable" for target in targets}
        )
    probes = await asyncio.gather(
        *(
            probe_upstream(client, target, timeout, wall_clock_seconds)
            for target in targets
        )
    )
    checks = {probe.name: probe.status for probe in probes}
    ready = all(probe.ok for probe in probes)
    return ReadinessResult(ready, checks)


def build_probe_timeout(settings) -> httpx.Timeout:
    """The httpx per-phase limits (connect/read). The wall-clock ceiling is
    separate — see `build_probe_wall_clock_seconds`."""
    return httpx.Timeout(
        settings.upstream_probe_total_timeout_seconds,
        connect=settings.upstream_probe_connect_timeout_seconds,
        read=settings.upstream_probe_read_timeout_seconds,
    )


def build_probe_wall_clock_seconds(settings) -> float:
    """The hard per-probe wall-clock bound (seconds). This — not any httpx
    'total' — is what guarantees a hung upstream can't stall `/ready`."""
    return settings.upstream_probe_total_timeout_seconds


def build_required_targets(settings) -> list[ProbeTarget]:
    """The BFF's required upstream dependency-truth surfaces."""
    return [
        ProbeTarget(
            "scheduler",
            f"{settings.scheduler_url.rstrip('/')}/ready",
            expected_status="ready",
        ),
        ProbeTarget(
            "flow_monitoring",
            f"{settings.flow_monitoring_url.rstrip('/')}/ready",
            expected_status="ready",
        ),
        ProbeTarget(
            "ros",
            f"{settings.ros_service_url.rstrip('/')}/ready",
            expected_status="ready",
        ),
    ]
