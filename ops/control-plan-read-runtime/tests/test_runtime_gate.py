import json

import pytest

import runtime_gate


MIB = 1024 * 1024


def _meminfo(available_mib: int, swap_total_mib: int, swap_free_mib: int) -> str:
    return (
        "MemTotal:        4096000 kB\n"
        f"MemAvailable:    {available_mib * 1024} kB\n"
        f"SwapTotal:       {swap_total_mib * 1024} kB\n"
        f"SwapFree:        {swap_free_mib * 1024} kB\n"
    )


def _pm2(*, restart_count: int = 0, status: str = "online") -> str:
    return json.dumps(
        [
            {
                "name": name,
                "pm2_env": {
                    "status": status,
                    "restart_time": restart_count,
                    "env": {"POSTGRES_URL": "postgresql://operator:secret@db/x"},
                },
            }
            for name in runtime_gate.PROCESS_NAMES
        ]
    )


@pytest.mark.parametrize(
    ("available_mib", "swap_used_mib", "expected"),
    [
        (330, 873, ["mem_available_below_512_mib"]),
        (511, 0, ["mem_available_below_512_mib"]),
        (512, 1024, []),
        (2048, 1025, ["swap_used_above_1024_mib"]),
    ],
)
def test_capacity_boundaries(available_mib, swap_used_mib, expected):
    capacity = runtime_gate.parse_meminfo(
        _meminfo(available_mib, 2048, 2048 - swap_used_mib)
    )

    assert runtime_gate.capacity_errors(capacity) == expected


def test_meminfo_requires_every_capacity_field_without_echoing_input():
    with pytest.raises(runtime_gate.GateError, match="invalid_meminfo") as exc:
        runtime_gate.parse_meminfo("MemAvailable: secret-host kB\n")

    assert "secret-host" not in str(exc.value)


def test_restart_snapshot_projects_only_names_and_counts():
    snapshot = runtime_gate.restart_snapshot(_pm2(restart_count=7))

    assert snapshot == {name: 7 for name in runtime_gate.PROCESS_NAMES}
    assert "secret" not in json.dumps(snapshot)


def test_restart_snapshot_treats_not_yet_created_process_as_zero():
    assert runtime_gate.restart_snapshot("[]") == {
        name: 0 for name in runtime_gate.PROCESS_NAMES
    }


def test_stability_sample_rejects_missing_offline_restart_and_readiness():
    processes = json.loads(_pm2(restart_count=3))
    processes[0]["pm2_env"]["status"] = "stopped"
    processes.pop()
    baseline = {name: 2 for name in runtime_gate.PROCESS_NAMES}
    readiness = {name: True for name in runtime_gate.PROCESS_NAMES}
    readiness["scheduler"] = False

    errors = runtime_gate.stability_errors(
        json.dumps(processes),
        baseline,
        readiness,
        runtime_gate.parse_meminfo(_meminfo(1024, 1024, 1024)),
    )

    assert "flow-monitoring_not_online" in errors
    assert "flow-monitoring_restarted" in errors
    assert "bff-water-planning_missing" in errors
    assert "scheduler_not_ready" in errors
    assert "secret" not in repr(errors)


def test_readiness_probe_requires_http_200_and_exact_ready():
    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return b'{"status":"ready","checks":{"postgres":"ok"}}'

    assert runtime_gate.probe_readiness(
        "http://127.0.0.1:3011/ready", lambda *_a, **_k: Response()
    )


@pytest.mark.parametrize(
    "payload",
    [b'{"status":"healthy"}', b'{"status":"not ready"}', b"not-json"],
)
def test_readiness_probe_fails_closed_without_echoing_body(payload):
    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return payload + b" internal-host secret"

    assert not runtime_gate.probe_readiness(
        "http://127.0.0.1:3011/ready", lambda *_a, **_k: Response()
    )


def test_monitor_requires_a_sample_at_or_after_full_duration():
    times = iter([0.0, 0.0, 4.0, 5.0])
    samples = []

    result = runtime_gate.monitor_stability(
        duration_seconds=5,
        interval_seconds=1,
        sample=lambda: samples.append("sample") or [],
        monotonic=lambda: next(times),
        sleep=lambda _seconds: None,
    )

    assert result == []
    assert len(samples) == 3


def test_monitor_stops_on_first_safe_error():
    assert runtime_gate.monitor_stability(
        duration_seconds=300,
        interval_seconds=5,
        sample=lambda: ["scheduler_restarted"],
        monotonic=lambda: 0,
        sleep=lambda _seconds: None,
    ) == ["scheduler_restarted"]


def test_startup_monitor_allows_transient_state_until_first_green_sample():
    times = iter([0.0, 0.0, 5.0])
    samples = iter(
        [
            ["scheduler_not_online", "scheduler_not_ready"],
            [],
        ]
    )

    assert (
        runtime_gate.monitor_startup(
            timeout_seconds=120,
            interval_seconds=5,
            sample=lambda: next(samples),
            monotonic=lambda: next(times),
            sleep=lambda _seconds: None,
        )
        == []
    )


def test_startup_monitor_fails_immediately_on_restart_or_capacity_fault():
    assert runtime_gate.monitor_startup(
        timeout_seconds=120,
        interval_seconds=5,
        sample=lambda: ["scheduler_restarted"],
        monotonic=lambda: 0,
        sleep=lambda _seconds: None,
    ) == ["scheduler_restarted"]
