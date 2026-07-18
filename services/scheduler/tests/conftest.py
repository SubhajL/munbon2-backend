"""Path bootstrap + required-env bootstrap (PR 4.2 / 4.4a-1).

The old conftest carried async DB fixtures hardcoded to a local
postgres:postgres server (the source of 38 collection-time errors), a fake
Redis, and monkeypatches that never took effect. Integration suites now own
their fixtures (tests/integration/test_scheduler_postgres.py, env-gated to a
disposable loopback database).

PR 4.4a-1 makes several JWT settings REQUIRED with fail-closed validators
(a strong secret, an explicit issuer/audience, and an explicit claim-policy
mode). Every test that constructs ``Settings`` would otherwise fail, so the
required JWT env is seeded here — as OS env vars, which pydantic-settings v2
ranks ABOVE the developer ``.env`` file, so a weak/absent ``.env`` secret can
never make the suite pass under false pretenses. ``setdefault`` lets a real
exported value win, and the default mode is ``compat`` so the existing draft/
lifecycle API tests keep their role-less tokens."""

import os
import sys
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
for path in (str(SERVICE_ROOT), str(SERVICE_ROOT / "src")):
    if path not in sys.path:
        sys.path.insert(0, path)

# A 47-byte, non-repeating, non-denylisted secret so the strong-secret validator
# accepts the test process regardless of the developer .env's JWT_SECRET_KEY.
os.environ.setdefault(
    "JWT_SECRET_KEY", "test-scheduler-jwt-secret-key-0123456789abcdef"
)
os.environ.setdefault("JWT_ISSUER", "munbon-auth-test")
os.environ.setdefault("JWT_AUDIENCE", "munbon-scheduler-test")
os.environ.setdefault("JWT_ACCESS_TOKEN_TYPE", "access")
os.environ.setdefault("JWT_CLAIM_POLICY_MODE", "compat")
