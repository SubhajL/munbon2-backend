import os
import sys
from pathlib import Path

# `main.py` and every module under src/ use src-rooted imports
# (`from config import settings`), so src must be on the path — the service
# root alone is not enough.
SERVICE_ROOT = Path(__file__).resolve().parents[1]
for path in (str(SERVICE_ROOT), str(SERVICE_ROOT / "src")):
    if path not in sys.path:
        sys.path.insert(0, path)

# Settings() is instantiated at import time and cors_origins has no default;
# provide it so the suite never depends on a developer's .env (same pattern as
# the flow-monitoring CI dummy-env, PR #28).
os.environ.setdefault("CORS_ORIGINS", "http://localhost:3000")
