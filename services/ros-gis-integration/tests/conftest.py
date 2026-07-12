import sys
from pathlib import Path

# Modules under src/ use src-rooted imports (`from config import settings`),
# so src must be on the path — same harness pattern as bff-water-planning
# (Wave 2.6a) and flow-monitoring.
SERVICE_ROOT = Path(__file__).resolve().parents[1]
for path in (str(SERVICE_ROOT), str(SERVICE_ROOT / "src")):
    if path not in sys.path:
        sys.path.insert(0, path)
