"""RFC-8785 JSON Canonicalization Scheme (JCS) — the Python producer/verifier.

PR 4.3c consumes the 6.1a device-capability snapshot and must reproduce, BYTE FOR
BYTE, the canonical JSON + capability_hash that the TypeScript SCADA service emits
via the `canonicalize` reference lib — otherwise a cross-language capability_hash
diverges. The only subtle part is number formatting: JCS uses ES6
``Number.prototype.toString`` (shortest round-tripping form), which differs from
Python ``json.dumps`` on integer-valued floats (``2.0`` -> ``"2"``), the
fixed/exponent boundary (``1e-7`` -> ``"1e-7"``, not ``"1e-07"``), and negative
zero (``-0.0`` -> ``"0"``). ``test_canonical_json.py`` pins every case against the
6.1a golden vector.
"""

from __future__ import annotations

import hashlib
import json
import math
from decimal import Decimal
from typing import Any


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _es6_number(value: float | int) -> str:
    """Format a JSON number exactly as ES6 ``Number.prototype.toString`` (== JCS)."""
    if isinstance(value, bool):
        raise ValueError("a bool is not a JSON number")
    if isinstance(value, int):
        return str(value)
    if not math.isfinite(value):
        raise ValueError("a JSON number must be finite")
    if value == 0:
        return "0"  # collapses -0.0 as well
    sign = "-" if value < 0 else ""
    # repr() gives the shortest round-tripping decimal; normalize() strips the
    # trailing zeros repr keeps (e.g. "2.0"), giving the exact significant digits.
    digits_tuple = Decimal(repr(abs(value))).normalize().as_tuple()
    digits = "".join(str(d) for d in digits_tuple.digits)
    k = len(digits)
    point = k + digits_tuple.exponent  # decimal-point position within `digits`
    if k <= point <= 21:
        body = digits + "0" * (point - k)
    elif 0 < point <= 21:
        body = digits[:point] + "." + digits[point:]
    elif -6 < point <= 0:
        body = "0." + "0" * (-point) + digits
    else:
        mantissa = digits[0] + ("." + digits[1:] if k > 1 else "")
        exponent = point - 1
        body = f"{mantissa}e{'+' if exponent >= 0 else '-'}{abs(exponent)}"
    return sign + body


def canonicalize(value: Any) -> str:
    """Return the RFC-8785 canonical JSON string for a JSON-compatible value.

    Objects sort their keys; arrays preserve order; numbers use ES6 shortest form.
    Fails closed (``ValueError``) on a non-finite number or an unserialisable type
    rather than emit a non-canonical or lossy encoding.
    """
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return "null"
    if isinstance(value, (int, float)):
        return _es6_number(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, dict):
        for key in value:
            if not isinstance(key, str):
                raise ValueError("JCS object keys must be strings")
        items = sorted(value.items(), key=lambda kv: kv[0])
        return (
            "{"
            + ",".join(
                json.dumps(key, ensure_ascii=False) + ":" + canonicalize(item)
                for key, item in items
            )
            + "}"
        )
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(canonicalize(item) for item in value) + "]"
    raise ValueError(f"value of type {type(value).__name__} is not JSON-serialisable")
