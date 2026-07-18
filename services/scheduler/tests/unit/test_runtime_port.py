"""Canonical scheduler runtime port = 3021 (PR 4.4a-2).

The scheduler's runtime port drifted (start.sh hardcoded 3012, PM2 said 3012)
while `core/config.py` and the BFF already used 3021. This locks the code-owned
default at 3021 and pins start.sh to honor `$PORT` with a 3021 default — never
the retired 3012. The PM2/BFF side of the agreement is locked in the infra jest
suite (`infra/pm2/__tests__/build-irrigation-config.spec.ts`).

The env-preservation behavior is asserted BEHAVIORALLY: the real start.sh
env-loading block is extracted and executed under bash to prove a PM2-injected
PORT beats a stale `.env` PORT while an unset var still falls back to `.env`.
"""

import os
import subprocess
from pathlib import Path

from core.config import Settings

SERVICE_ROOT = Path(__file__).resolve().parents[2]
START_SH = SERVICE_ROOT / "start.sh"


def _extract_env_loading_block(start_sh_text: str) -> str:
    """Return the exact `.env`-loading block from start.sh (`if [ -f .env ]; then`
    through its closing `fi`). Executing the REAL block — not a hand-copied twin —
    means a regression that reverts start.sh to the clobbering `export $(cat .env
    | xargs)` form makes the behavioral test below fail.
    """
    lines = start_sh_text.splitlines()
    start = next(
        i for i, ln in enumerate(lines) if ln.strip() == "if [ -f .env ]; then"
    )
    end = next(i for i in range(start + 1, len(lines)) if lines[i].strip() == "fi")
    return "\n".join(lines[start : end + 1])


def test_config_default_service_port_is_3021():
    # Hermetic: the code-owned default, independent of any developer .env.
    assert Settings.model_fields["service_port"].default == 3021


def test_start_sh_honors_port_env_defaulting_to_3021():
    text = START_SH.read_text(encoding="utf-8")
    assert '--port "${PORT:-3021}"' in text
    # The retired hardcoded port must be gone.
    assert "--port 3012" not in text


def test_start_sh_migrates_before_exec_uvicorn():
    text = START_SH.read_text(encoding="utf-8")
    migrate_idx = text.index("migrate.py apply-all")
    exec_idx = text.index("exec ./venv/bin/uvicorn")
    # Migrate-before-start: uvicorn is exec'd only after apply-all, and a failed
    # apply-all aborts (so PM2 never boots a falsely-ready process).
    assert migrate_idx < exec_idx
    assert "|| exit 1" in text


_UNSET_SENTINEL = "__UNSET__"


def _run_env_block(tmp_path, injected_env, dotenv_contents, probe_keys):
    """Execute start.sh's real .env-loading block under bash with `injected_env`
    as the process environment and `dotenv_contents` written to ./.env, then read
    back each key in `probe_keys`. Returns {key: value|None} (None = still unset)."""
    block = _extract_env_loading_block(START_SH.read_text(encoding="utf-8"))
    (tmp_path / ".env").write_text(dotenv_contents, encoding="utf-8")
    echoes = "\n".join(
        f'printf "{key}=%s\\n" "${{{key}-{_UNSET_SENTINEL}}}"' for key in probe_keys
    )
    (tmp_path / "run.sh").write_text(f"{block}\n{echoes}\n", encoding="utf-8")
    proc = subprocess.run(
        ["bash", "run.sh"],
        cwd=tmp_path,
        env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"), **injected_env},
        capture_output=True,
        text=True,
        check=True,
    )
    result = {}
    for line in proc.stdout.splitlines():
        key, _, value = line.partition("=")
        if key in probe_keys:
            result[key] = None if value == _UNSET_SENTINEL else value
    return result


def test_start_sh_env_injected_port_beats_stale_dotenv(tmp_path):
    # PM2 injects PORT=3021; the tracked .env carries the retired 3012 and an
    # extra var PM2 does NOT inject. Fail-closed contract: the injected value is
    # authoritative (never clobbered), while a var absent from the environment
    # still falls back to .env. Runs the REAL start.sh block under bash — the old
    # `export $(cat .env | xargs)` form would make PORT resolve to 3012 here.
    values = _run_env_block(
        tmp_path,
        injected_env={"PATH": "/usr/bin:/bin", "PORT": "3021"},
        dotenv_contents="PORT=3012\nFOO=frombutdotenv\n# comment line\n",
        probe_keys=("PORT", "FOO"),
    )
    assert values["PORT"] == "3021"  # injected PM2 value wins
    assert values["FOO"] == "frombutdotenv"  # unset var falls back to .env


def test_start_sh_env_absent_injection_falls_back_to_dotenv(tmp_path):
    # With no PORT injected, the .env value is used (fallback still works).
    values = _run_env_block(
        tmp_path,
        injected_env={"PATH": "/usr/bin:/bin"},
        dotenv_contents="PORT=3012\n",
        probe_keys=("PORT",),
    )
    assert values["PORT"] == "3012"
