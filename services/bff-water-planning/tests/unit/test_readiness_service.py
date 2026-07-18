"""BFF dependency-truth readiness + pooled-client wiring (PR 4.4a-2).

Layers, all network-free:
- Probes (httpx.MockTransport / a slow async transport): each required upstream is
  probed over the pooled client, bounded by BOTH the httpx per-phase limits and a
  hard per-probe wall-clock; any timeout/non-200/malformed/wrong-status fails the
  BFF readiness, and the body leaks no host/URL/exception text.
- Expected-status: a target requires its EXACT self-reported status, so liveness
  ("healthy") can never satisfy a readiness ("ready") probe and vice versa.
- Fail-closed client: a missing/closed pooled client makes /ready 503 (never a
  RuntimeError out through gather).
- Lifespan: a fallible startup step still closes the pooled client (no leak).
- Pooled client wiring + health liveness.
"""

import asyncio
import time
from types import SimpleNamespace

import httpx
import pytest
from fastapi.responses import JSONResponse

from api.routes import control_plans
from clients.scheduler_client import SchedulerClient
from config import settings as app_settings
from services.readiness_service import (
    ProbeTarget,
    ReadinessResult,
    build_probe_timeout,
    build_probe_wall_clock_seconds,
    build_required_targets,
    probe_required_upstreams,
    probe_upstream,
)

READY_BODY = {"status": "ready", "checks": {}}
HEALTHY_BODY = {"status": "healthy"}
_WALL_CLOCK = 5.0

# Distinct target factories keep each probe's REQUIRED status explicit.
def _scheduler_target(url="http://s/ready") -> ProbeTarget:
    return ProbeTarget("scheduler", url, expected_status="ready")


def _flow_target(url="http://f/ready") -> ProbeTarget:
    return ProbeTarget("flow_monitoring", url, expected_status="ready")


def _ros_target(url="http://r/health") -> ProbeTarget:
    return ProbeTarget("ros", url, expected_status="healthy")


def _pooled_client(handler) -> tuple[httpx.AsyncClient, list[httpx.Request]]:
    captured: list[httpx.Request] = []

    def _wrapped(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return handler(request)

    return httpx.AsyncClient(transport=httpx.MockTransport(_wrapped)), captured


class _SlowTransport(httpx.AsyncBaseTransport):
    """A transport that sleeps `delay` seconds before answering and enforces NO
    httpx timeouts itself — exactly the slow-drip case httpx.Timeout cannot bound.
    Only the readiness wall-clock can stop it."""

    def __init__(self, delay: float, response: httpx.Response):
        self._delay = delay
        self._response = response

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(self._delay)
        self._response.request = request
        return self._response


def _slow_client(delay: float, body=None) -> httpx.AsyncClient:
    body = READY_BODY if body is None else body
    return httpx.AsyncClient(
        transport=_SlowTransport(delay, httpx.Response(200, json=body))
    )


def _timeout() -> httpx.Timeout:
    return httpx.Timeout(5.0, connect=2.0, read=3.0)


def _generous_timeout() -> httpx.Timeout:
    # Deliberately larger than any test's wall-clock so ONLY the wall-clock can
    # bound a slow-drip probe (proves the fix, not the httpx read timeout).
    return httpx.Timeout(30.0, connect=10.0, read=10.0)


# --- single-probe classification --------------------------------------------
class TestProbeUpstream:
    @pytest.mark.asyncio
    async def test_healthy_ready_upstream_is_ok(self):
        client, _ = _pooled_client(lambda r: httpx.Response(200, json=READY_BODY, request=r))
        probe = await probe_upstream(client, _scheduler_target(), _timeout(), _WALL_CLOCK)
        assert (probe.ok, probe.status) == (True, "ok")

    @pytest.mark.asyncio
    async def test_503_ready_upstream_is_unhealthy(self):
        client, _ = _pooled_client(
            lambda r: httpx.Response(503, json={"status": "not ready"}, request=r)
        )
        probe = await probe_upstream(client, _flow_target(), _timeout(), _WALL_CLOCK)
        assert (probe.ok, probe.status) == (False, "unhealthy")

    @pytest.mark.asyncio
    async def test_200_but_unhealthy_status_is_unhealthy(self):
        client, _ = _pooled_client(
            lambda r: httpx.Response(200, json={"status": "unhealthy"}, request=r)
        )
        probe = await probe_upstream(client, _ros_target(), _timeout(), _WALL_CLOCK)
        assert (probe.ok, probe.status) == (False, "unhealthy")

    @pytest.mark.asyncio
    async def test_non_json_body_is_malformed(self):
        client, _ = _pooled_client(lambda r: httpx.Response(200, content=b"<html>", request=r))
        probe = await probe_upstream(client, _ros_target(), _timeout(), _WALL_CLOCK)
        assert (probe.ok, probe.status) == (False, "malformed")

    @pytest.mark.asyncio
    async def test_transport_error_is_unreachable(self):
        def handler(r):
            raise httpx.ConnectError("connection refused", request=r)

        client, _ = _pooled_client(handler)
        probe = await probe_upstream(client, _scheduler_target(), _timeout(), _WALL_CLOCK)
        assert (probe.ok, probe.status) == (False, "unreachable")

    @pytest.mark.asyncio
    async def test_httpx_read_timeout_is_classified_as_timeout(self):
        def handler(r):
            raise httpx.ReadTimeout("read timed out", request=r)

        client, _ = _pooled_client(handler)
        probe = await probe_upstream(client, _scheduler_target(), _timeout(), _WALL_CLOCK)
        assert (probe.ok, probe.status) == (False, "timeout")

    # FIX 3 (HIGH): liveness is NOT readiness.
    @pytest.mark.asyncio
    async def test_scheduler_health_status_is_rejected_as_not_ready(self):
        # A /ready→/health misroute: scheduler answers 200 {"status":"healthy"}.
        # The scheduler target REQUIRES exactly "ready", so this is not serviceable.
        client, _ = _pooled_client(
            lambda r: httpx.Response(200, json=HEALTHY_BODY, request=r)
        )
        probe = await probe_upstream(client, _scheduler_target(), _timeout(), _WALL_CLOCK)
        assert (probe.ok, probe.status) == (False, "unhealthy")

    @pytest.mark.asyncio
    async def test_ros_ready_status_is_rejected_as_not_healthy(self):
        # The ros target REQUIRES exactly "healthy"; a "ready" answer is not accepted.
        client, _ = _pooled_client(
            lambda r: httpx.Response(200, json={"status": "ready"}, request=r)
        )
        probe = await probe_upstream(client, _ros_target(), _timeout(), _WALL_CLOCK)
        assert (probe.ok, probe.status) == (False, "unhealthy")

    # FIX 2 (HIGH): a slow-drip upstream is bounded by the wall-clock, not the
    # httpx read timeout (which this transport ignores).
    @pytest.mark.asyncio
    async def test_probe_is_bounded_by_wall_clock_not_httpx_read_timeout(self):
        client = _slow_client(delay=5.0)
        start = time.perf_counter()
        probe = await probe_upstream(
            client, _scheduler_target(), _generous_timeout(), wall_clock_seconds=0.1
        )
        elapsed = time.perf_counter() - start
        await client.aclose()
        assert (probe.ok, probe.status) == (False, "timeout")
        # Resolved via the ~0.1s wall-clock, NOT by hanging ~5s for the drip.
        assert elapsed < 2.0


# --- aggregate readiness ----------------------------------------------------
class TestProbeRequiredUpstreams:
    @pytest.mark.asyncio
    async def test_ready_only_when_all_upstreams_ok(self):
        def handler(r):
            if r.url.path == "/health":
                return httpx.Response(200, json=HEALTHY_BODY, request=r)
            return httpx.Response(200, json=READY_BODY, request=r)

        client, captured = _pooled_client(handler)
        targets = [_scheduler_target(), _flow_target(), _ros_target()]
        result = await probe_required_upstreams(client, targets, _timeout(), _WALL_CLOCK)
        assert isinstance(result, ReadinessResult)
        assert result.ready is True
        assert result.checks == {"scheduler": "ok", "flow_monitoring": "ok", "ros": "ok"}
        # every required upstream was actually probed (concurrently)
        assert len(captured) == 3

    @pytest.mark.asyncio
    async def test_bff_ready_fails_when_any_required_upstream_fails(self):
        def handler(r):
            if r.url.host == "scheduler":
                return httpx.Response(503, json={"status": "not ready"}, request=r)
            if r.url.path == "/health":
                return httpx.Response(200, json=HEALTHY_BODY, request=r)
            return httpx.Response(200, json=READY_BODY, request=r)

        client, _ = _pooled_client(handler)
        targets = [
            _scheduler_target("http://scheduler/ready"),
            _flow_target("http://flow/ready"),
            _ros_target("http://ros/health"),
        ]
        result = await probe_required_upstreams(client, targets, _timeout(), _WALL_CLOCK)
        assert result.ready is False
        assert result.checks["scheduler"] == "unhealthy"
        # the other upstreams are still probed independently and stay ok
        assert result.checks["flow_monitoring"] == "ok"
        assert result.checks["ros"] == "ok"

    @pytest.mark.asyncio
    async def test_bff_ready_times_out_each_probe_within_bound(self):
        # One upstream times out (httpx read timeout); the others succeed — proving
        # each probe is independently bounded and one hung upstream can't block it.
        def handler(r):
            if r.url.host == "flow":
                raise httpx.ReadTimeout("timed out", request=r)
            if r.url.path == "/health":
                return httpx.Response(200, json=HEALTHY_BODY, request=r)
            return httpx.Response(200, json=READY_BODY, request=r)

        client, _ = _pooled_client(handler)
        targets = [
            _scheduler_target("http://scheduler/ready"),
            _flow_target("http://flow/ready"),
            _ros_target("http://ros/health"),
        ]
        result = await probe_required_upstreams(client, targets, _timeout(), _WALL_CLOCK)
        assert result.ready is False
        assert result.checks["flow_monitoring"] == "timeout"
        assert result.checks["scheduler"] == "ok"

    # FIX 2 (HIGH): aggregate /ready is not ready when an upstream hangs past the
    # wall-clock, and resolves quickly rather than stalling.
    @pytest.mark.asyncio
    async def test_aggregate_not_ready_when_upstream_hangs_past_wall_clock(self):
        client = _slow_client(delay=5.0)
        targets = [_scheduler_target("http://scheduler/ready")]
        start = time.perf_counter()
        result = await probe_required_upstreams(
            client, targets, _generous_timeout(), wall_clock_seconds=0.1
        )
        elapsed = time.perf_counter() - start
        await client.aclose()
        assert result.ready is False
        assert result.checks["scheduler"] == "timeout"
        assert elapsed < 2.0

    @pytest.mark.asyncio
    async def test_readiness_body_never_leaks_url_or_host(self):
        def handler(r):
            raise httpx.ConnectError("connect to 10.9.9.9:3021 failed", request=r)

        client, _ = _pooled_client(handler)
        targets = [_scheduler_target("http://10.9.9.9:3021/ready")]
        result = await probe_required_upstreams(client, targets, _timeout(), _WALL_CLOCK)
        blob = repr(result.checks)
        assert "10.9.9.9" not in blob
        assert result.checks == {"scheduler": "unreachable"}

    # FIX 4 (MEDIUM): a missing/closed pooled client fails closed (503), never a
    # RuntimeError out through gather, and leaks nothing.
    @pytest.mark.asyncio
    async def test_missing_pooled_client_is_not_ready(self):
        targets = [_scheduler_target("http://scheduler/ready"), _ros_target("http://ros/health")]
        result = await probe_required_upstreams(None, targets, _timeout(), _WALL_CLOCK)
        assert result.ready is False
        assert result.checks == {"scheduler": "unreachable", "ros": "unreachable"}

    @pytest.mark.asyncio
    async def test_closed_pooled_client_is_not_ready(self):
        client, _ = _pooled_client(lambda r: httpx.Response(200, json=READY_BODY, request=r))
        await client.aclose()  # closed pooled client (shutdown race / never-built)
        targets = [_scheduler_target("http://scheduler/ready")]
        result = await probe_required_upstreams(client, targets, _timeout(), _WALL_CLOCK)
        assert result.ready is False
        assert result.checks == {"scheduler": "unreachable"}


# --- /ready endpoint (fail-closed 503) --------------------------------------
class TestReadyEndpoint:
    @pytest.mark.asyncio
    async def test_ready_endpoint_returns_503_when_upstream_hangs(self, monkeypatch):
        # End-to-end through main.readiness_check: a slow-drip scheduler is bounded
        # by the wall-clock and the endpoint answers 503 (never hangs).
        import main
        from services import readiness_service as rs

        slow = _slow_client(delay=5.0)
        monkeypatch.setattr(
            rs, "build_required_targets",
            lambda s: [_scheduler_target("http://scheduler/ready")],
        )
        monkeypatch.setattr(rs, "build_probe_timeout", lambda s: _generous_timeout())
        monkeypatch.setattr(rs, "build_probe_wall_clock_seconds", lambda s: 0.1)
        request = SimpleNamespace(
            app=SimpleNamespace(state=SimpleNamespace(http_client=slow))
        )
        response = await main.readiness_check(request)
        await slow.aclose()
        assert isinstance(response, JSONResponse)
        assert response.status_code == 503

    @pytest.mark.asyncio
    async def test_ready_endpoint_503_when_pooled_client_missing(self, monkeypatch):
        import main
        from services import readiness_service as rs

        monkeypatch.setattr(
            rs, "build_required_targets",
            lambda s: [_scheduler_target("http://scheduler/ready")],
        )
        request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))
        response = await main.readiness_check(request)
        assert isinstance(response, JSONResponse)
        assert response.status_code == 503


# --- timeout + target builders ----------------------------------------------
class TestBuilders:
    def test_probe_timeout_is_bounded_from_settings(self):
        timeout = build_probe_timeout(app_settings)
        assert timeout.connect == app_settings.upstream_probe_connect_timeout_seconds
        assert timeout.read == app_settings.upstream_probe_read_timeout_seconds
        # every phase is finite (bounded), never None
        assert all(
            v is not None for v in (timeout.connect, timeout.read, timeout.pool)
        )

    def test_probe_wall_clock_is_the_total_timeout_setting(self):
        assert (
            build_probe_wall_clock_seconds(app_settings)
            == app_settings.upstream_probe_total_timeout_seconds
        )

    def test_required_targets_use_ready_and_health_surfaces_with_exact_status(self):
        targets = {t.name: t for t in build_required_targets(app_settings)}
        assert targets["scheduler"].url.endswith("/ready")
        assert targets["scheduler"].expected_status == "ready"
        assert targets["flow_monitoring"].url.endswith("/ready")
        assert targets["flow_monitoring"].expected_status == "ready"
        assert targets["ros"].url.endswith("/health")
        assert targets["ros"].expected_status == "healthy"


# --- pooled client wiring ----------------------------------------------------
class TestPooledClient:
    def test_get_scheduler_client_reuses_the_lifespan_pooled_client(self):
        pooled, _ = _pooled_client(lambda r: httpx.Response(200, json={}, request=r))
        request = SimpleNamespace(
            app=SimpleNamespace(state=SimpleNamespace(http_client=pooled))
        )
        client = control_plans.get_scheduler_client(request)
        assert client._http_client is pooled

    @pytest.mark.asyncio
    async def test_scheduler_reads_go_through_the_pooled_client(self):
        pooled, captured = _pooled_client(
            lambda r: httpx.Response(200, json={"plan_id": "p"}, request=r)
        )
        client = SchedulerClient(base_url="http://scheduler.test", http_client=pooled)

        await client._get_control_plan_document("/api/v1/x", "tok")
        await client._get_control_plan_document("/api/v1/y", "tok")

        # both reads reused the ONE pooled client/transport (no per-read client)
        assert [r.url.path for r in captured] == ["/api/v1/x", "/api/v1/y"]
        assert all(r.headers["Authorization"] == "Bearer tok" for r in captured)

    def test_scheduler_service_url_setting_was_removed(self):
        # The duplicate SCHEDULER_SERVICE_URL field is gone; scheduler_url stays.
        assert not hasattr(app_settings, "scheduler_service_url")
        assert app_settings.scheduler_url


# --- lifespan cleanup (FIX 7) ------------------------------------------------
class _FakeAsyncClient:
    def __init__(self):
        self.aclose_called = False

    async def aclose(self):
        self.aclose_called = True


class TestLifespanCleanup:
    @pytest.mark.asyncio
    async def test_pooled_client_is_closed_when_startup_raises(self, monkeypatch):
        # FIX 7: the pooled client is created BEFORE the fallible startup steps; a
        # raise from one of them must still close it (cleanup in `finally`), not
        # leak a live connection pool.
        import main

        fake_client = _FakeAsyncClient()

        async def _noop(*a, **k):
            return None

        async def _boom(*a, **k):
            raise RuntimeError("startup failed")

        monkeypatch.setattr(main.httpx, "AsyncClient", lambda *a, **k: fake_client)
        monkeypatch.setattr(main.db_manager, "initialize", _noop)
        monkeypatch.setattr(main.db_manager, "close", _noop)
        monkeypatch.setattr(main.daily_demand_scheduler, "start_scheduler", _boom)
        monkeypatch.setattr(main.daily_demand_scheduler, "stop_scheduler", lambda: None)
        monkeypatch.setattr(main.ros_sync_service, "stop_periodic_sync", lambda: None)
        monkeypatch.setattr(main.redis_config, "create_redis_client", _noop)
        monkeypatch.setattr(main.redis_config, "disconnect", _noop)
        # Skip the fire-and-forget ROS sync task so no pending task is orphaned.
        monkeypatch.setattr(main.settings, "use_mock_server", True)

        app = SimpleNamespace(state=SimpleNamespace())
        with pytest.raises(RuntimeError, match="startup failed"):
            async with main.lifespan(app):
                pass  # unreachable: startup raises before yield

        assert fake_client.aclose_called is True


# --- health liveness ---------------------------------------------------------
class TestHealthLivenessOnly:
    @pytest.mark.asyncio
    async def test_bff_health_makes_no_dependency_claim(self):
        import main

        body = await main.health_check()
        assert body["status"] == "healthy"
        # no fabricated upstream/database claims (the old hardcoded block is gone)
        assert "databases" not in body
        assert "external_services" not in body
        assert set(body) == {"status", "service", "version"}
        # the version mismatch is fixed: report the real 2.0.0 app version
        assert body["version"] == main.app.version == "2.0.0"
