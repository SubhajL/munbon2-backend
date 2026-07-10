"""
Pytest configuration for the Flow Monitoring Service.

Wave 1.9: the old DB/legacy-hydraulics fixture stack is gone with the legacy
suites it served. Every current suite is self-contained; this file only makes
`src/` importable when pytest is launched without PYTHONPATH.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
