"""PR 6.3a — the dispatch-job factory: dark-by-default wiring + a minting token provider."""
import pytest

from datetime import datetime, timezone
from types import SimpleNamespace

import httpx
import jwt

from jobs.shadow_dispatch_once import build_scada_validation_client

NOW = datetime(2026, 7, 20, 3, 0, 0, tzinfo=timezone.utc)
SECRET = "a-strong-dedicated-service-secret-0123456789xyz"


def _settings(base_url=None, secret=None, execution_mode="disabled"):
    return SimpleNamespace(
        scheduler_scada_base_url=base_url,
        scheduler_service_jwt_secret=secret,
        scheduler_service_jwt_issuer="munbon-scheduler",
        scheduler_service_jwt_audience="munbon-scada-machine-boundary",
        scheduler_service_jwt_subject="scheduler-shadow-dispatcher",
        scheduler_service_jwt_max_age_seconds=300,
        control_execution_mode=execution_mode,
    )


def _mock_http():
    return httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(200))
    )


def test_dark_without_base_url():
    client = build_scada_validation_client(_settings(secret=SECRET), clock=lambda: NOW)
    assert client is None


def test_dark_without_service_secret():
    client = build_scada_validation_client(
        _settings(base_url="http://scada.local"), clock=lambda: NOW
    )
    assert client is None


def test_configured_builds_a_client_whose_token_provider_mints_a_valid_service_token():
    client = build_scada_validation_client(
        _settings(base_url="http://scada.local", secret=SECRET),
        clock=lambda: NOW,
        http_client=_mock_http(),
    )
    assert client is not None
    payload = jwt.decode(
        client._token_provider(),
        SECRET,
        algorithms=["HS256"],
        audience="munbon-scada-machine-boundary",
        issuer="munbon-scheduler",
        options={"verify_exp": False},
    )
    assert payload["type"] == "service"
    assert payload["sub"] == "scheduler-shadow-dispatcher"
    assert payload["exp"] - payload["iat"] == 300
    assert payload["scope"] == "command_intents.validate"


def test_factory_threads_execution_mode_from_the_injected_settings():
    # L4: the open-loop service must read the INJECTED settings' mode, not the module global.
    from jobs.shadow_dispatch_once import build_shadow_dispatch_service

    settings = _settings(
        base_url="http://scada.local", secret=SECRET, execution_mode="disabled"
    )
    service = build_shadow_dispatch_service(
        settings, object(), clock=lambda: NOW, http_client=_mock_http()
    )
    assert service._open_loop._execution_mode == "disabled"


def test_operator_factory_uses_the_injected_settings_for_bound_service_tokens():
    from jobs.shadow_dispatch_once import build_operator_dispatch_service

    settings = _settings(
        base_url="http://scada.local",
        secret=SECRET,
        execution_mode="operator_approved_open_loop",
    )
    service = build_operator_dispatch_service(
        settings,
        object(),
        snapshot=SimpleNamespace(),
        clock=lambda: NOW,
        http_client=_mock_http(),
    )

    assert service._token_settings is settings


def test_build_readback_client_dark_without_config():
    from jobs.shadow_dispatch_once import build_readback_client

    assert (
        build_readback_client(_settings(), clock=lambda: NOW) is None
    )  # no base_url/secret


def test_build_readback_client_configured():
    from jobs.shadow_dispatch_once import build_readback_client

    client = build_readback_client(
        _settings(base_url="http://scada.local", secret=SECRET),
        clock=lambda: NOW,
        http_client=_mock_http(),
    )
    assert client is not None
    payload = jwt.decode(
        client._token_provider(),
        SECRET,
        algorithms=["HS256"],
        audience="munbon-scada-machine-boundary",
        issuer="munbon-scheduler",
        options={"verify_exp": False},
    )
    assert payload["scope"] == "gate_readback.read"


def test_build_readback_reconciliation_service_threads_mode():
    from jobs.shadow_dispatch_once import build_readback_reconciliation_service

    settings = _settings(execution_mode="shadow")
    settings.control_readback_reconciliation_mode = "enforce"
    svc = build_readback_reconciliation_service(settings, object(), clock=lambda: NOW)
    assert svc._mode == "enforce"


@pytest.mark.asyncio
async def test_reconcile_active_plans_is_dark_without_a_client():
    from jobs.shadow_dispatch_once import reconcile_active_plans

    reports = await reconcile_active_plans(object(), None, None, object(), baselines={})
    assert reports == []


class _FakeReadbackClient:
    def __init__(self, *, raises=None):
        self.called = False
        self._raises = raises

    async def get_gate_readback(self):
        self.called = True
        if self._raises is not None:
            raise self._raises
        return {}


class _FakeRepoKeys:
    def __init__(self, keys):
        self._keys = keys

    async def load_active_shadow_plan_keys(self, session):
        return self._keys


class _RollbackSession:
    def __init__(self):
        self.rollbacks = 0

    async def rollback(self):
        self.rollbacks += 1


@pytest.mark.asyncio
async def test_operator_dispatch_releases_transaction_locks_after_every_plan_attempt():
    from jobs.shadow_dispatch_once import dispatch_operator_active_plans

    class Service:
        async def run_execute_dispatch_once(self, session, plan_id, plan_version):
            if plan_version == 2:
                raise RuntimeError("isolated")
            return SimpleNamespace(action="pending")

    session = _RollbackSession()
    reports = await dispatch_operator_active_plans(
        Service(), session, _FakeRepoKeys([("plan", 1), ("plan", 2)])
    )

    assert ([report.action for report in reports], session.rollbacks) == (
        ["pending"],
        2,
    )


@pytest.mark.asyncio
async def test_reconcile_active_plans_short_circuits_without_touching_scada_when_no_baselines():
    from jobs.shadow_dispatch_once import reconcile_active_plans

    client = _FakeReadbackClient()
    reports = await reconcile_active_plans(
        object(), client, None, _FakeRepoKeys([]), baselines={}
    )
    assert reports == []
    assert (
        client.called is False
    )  # never polls SCADA when there is nothing to reconcile


@pytest.mark.asyncio
async def test_reconcile_active_plans_isolates_a_readback_outage():
    from jobs.shadow_dispatch_once import reconcile_active_plans
    from services.clients.scada_client_errors import ScadaUnavailableError

    client = _FakeReadbackClient(raises=ScadaUnavailableError("down"))
    # baselines non-empty so it reaches the (failing) fetch — must NOT raise.
    reports = await reconcile_active_plans(
        object(), client, None, _FakeRepoKeys([]), baselines={("k", 1): {"G1": 2}}
    )
    assert reports == []
