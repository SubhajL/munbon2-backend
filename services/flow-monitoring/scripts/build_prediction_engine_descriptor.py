#!/usr/bin/env python3
"""Generate (or --check) the committed prediction-engine descriptor (PR 4.4b-1).

Deterministic: the descriptor is a fingerprint of the prediction closure's
file bytes alone — no git state, branch, timestamp, or dirty checkout. A clean
rebuild of the same tree yields a byte-identical descriptor. `--check`
recomputes from source and exits non-zero if the committed descriptor drifts
(a closure-file edit that was not re-pinned), so it is a local gate.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_ROOT / "src"))

from core.prediction_engine import (  # noqa: E402
    PredictionEngineError,
    build_prediction_engine_descriptor,
    load_prediction_engine_descriptor,
)

DEFAULT_OUTPUT = (
    SERVICE_ROOT / "data" / "prediction-engine" / "prediction-engine-v1.json"
)


def descriptor_text(descriptor: dict) -> str:
    """Deterministic serialization of the committed artifact (sorted keys)."""
    return json.dumps(descriptor, indent=2, sort_keys=True) + "\n"


def write_descriptor(source_root: Path, output_path: Path) -> dict:
    descriptor = build_prediction_engine_descriptor(source_root)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(descriptor_text(descriptor), encoding="utf-8")
    return descriptor


def descriptor_drift(source_root: Path, output_path: Path) -> str | None:
    """Return a drift reason, or None when the committed descriptor matches the
    descriptor rebuilt from source. Fail closed: a missing/malformed committed
    file is drift, not a silent pass."""
    rebuilt = build_prediction_engine_descriptor(source_root)
    try:
        committed = load_prediction_engine_descriptor(output_path)
    except PredictionEngineError as exc:
        return f"committed descriptor is missing or invalid: {exc}"
    if committed != rebuilt:
        return (
            "committed descriptor drifted from source: "
            f"committed build_digest={committed.get('build_digest')!r} "
            f"vs rebuilt {rebuilt['build_digest']!r}"
        )
    return None


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="recompute from source and fail (non-zero) on drift, never writing",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="path to the committed descriptor (default: the tracked artifact)",
    )
    args = parser.parse_args(argv)

    if args.check:
        drift = descriptor_drift(SERVICE_ROOT, args.output)
        if drift is not None:
            print(f"DRIFT: {drift}", file=sys.stderr)
            return 1
        print(f"OK: {args.output} matches the prediction closure")
        return 0

    descriptor = write_descriptor(SERVICE_ROOT, args.output)
    print(f"wrote {args.output} build_digest={descriptor['build_digest']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
