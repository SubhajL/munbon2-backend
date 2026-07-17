"""Path bootstrap ONLY (PR 4.2).

The old conftest carried async DB fixtures hardcoded to a local
postgres:postgres server (the source of 38 collection-time errors), a fake
Redis, and monkeypatches that never took effect. Integration suites now own
their fixtures (tests/integration/test_scheduler_postgres.py, env-gated to a
disposable loopback database)."""

import sys
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
for path in (str(SERVICE_ROOT), str(SERVICE_ROOT / "src")):
    if path not in sys.path:
        sys.path.insert(0, path)
