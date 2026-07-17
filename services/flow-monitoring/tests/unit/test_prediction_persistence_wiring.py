"""Source-level wiring locks for PR 4.1 prediction persistence.

main.py cannot be imported without the settings/db chain, so these lock the
wiring the way the repo's structural guards do: by asserting the source text
carries the exact seams. A missing seam here means the runtime would silently
lack persistence (503s forever) or recreate schema outside the migration."""

from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[2]
MAIN_PY = (SERVICE_ROOT / "src" / "main.py").read_text(encoding="utf-8")
CONTROL_PY = (SERVICE_ROOT / "src" / "api" / "control.py").read_text(
    encoding="utf-8"
)
MIGRATIONS_DIR = SERVICE_ROOT / "migrations"


def test_lifespan_wires_migration_probed_repository():
    assert "create_prediction_repository_if_migrated" in MAIN_PY
    assert "app.state.prediction_repository" in MAIN_PY


def test_lifespan_never_creates_prediction_schema():
    # The ONLY schema owner is the migration runner; the demand store's
    # ensure_schema pattern must not leak into prediction persistence.
    # Check the actual prediction wiring block (from the first prediction
    # mention in lifespan to the hydraulic-service section) for any
    # schema-creating call.
    start = MAIN_PY.index("prediction_repository_probe")
    end = MAIN_PY.index("HydraulicService")
    wiring_block = MAIN_PY[start:end]
    for forbidden in ("ensure_schema", "create_schema", "create_all",
                      "CREATE TABLE"):
        assert forbidden not in wiring_block, (
            f"prediction wiring must not carry {forbidden!r} — the migration "
            "runner is the only schema owner"
        )
    assert "CREATE TABLE" not in MAIN_PY


def test_routes_depend_on_app_state_repository():
    assert 'getattr(request.app.state, "prediction_repository", None)' in (
        CONTROL_PY
    )
    assert '"/predictions/{prediction_run_id}"' in CONTROL_PY


def test_migration_pair_is_tracked_and_nonempty():
    up = MIGRATIONS_DIR / "0001_prediction_persistence.up.sql"
    down = MIGRATIONS_DIR / "0001_prediction_persistence.down.sql"
    assert up.is_file() and up.stat().st_size > 0
    assert down.is_file() and down.stat().st_size > 0
