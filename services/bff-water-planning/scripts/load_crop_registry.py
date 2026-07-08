"""F-07: tracked loader for gis.crop_registry.

Previously the table was read by scripts but written by nothing in-repo, so it had no
reproducible, tracked population path. This loader ingests crop-registry rows from a CSV
source (path from CROP_REGISTRY_SOURCE) into gis.crop_registry, using DB credentials from
the environment (never hardcoded). It FAILS CLOSED when the source is not configured.

Columns match what the readers select (see populate_weekly_demands_with_events.py):
layer_name, "Zone" (only area_1 uses it), sec_no, area_rai, status. The load is IDEMPOTENT
via ON CONFLICT on the table's natural key, so re-running never duplicates rows (which would
double-count weekly water demands).

Long-term, retire gis.crop_registry for gis.agricultural_plots (F-06). The upstream source is
a GIS shapefile export not in this repo — export it to CSV (columns above) and set
CROP_REGISTRY_SOURCE.

Usage:
    POSTGRES_HOST=... POSTGRES_PASSWORD=... CROP_REGISTRY_SOURCE=crop_registry.csv \\
        python scripts/load_crop_registry.py
"""
import csv
import math
import os
import sys

REQUIRED_COLUMNS = ("layer_name", "sec_no", "area_rai", "status")
# Column order for INSERT / the tuples parse_row returns.
INSERT_COLUMNS = ("layer_name", "Zone", "sec_no", "area_rai", "status")


def parse_row(row: dict) -> tuple:
    """Map one CSV row to a gis.crop_registry tuple (INSERT_COLUMNS order).

    Raises ValueError on any missing/blank required field (including a short/ragged row
    where csv.DictReader yields None) or a non-finite/negative area. "Zone" is optional
    (only area_1 uses it) and defaults to "".
    """
    def required(name: str) -> str:
        value = row.get(name)
        if value is None or str(value).strip() == "":
            raise ValueError(f"row missing required column: {name!r}")
        return str(value).strip()

    layer_name = required("layer_name")
    sec_no = int(float(required("sec_no")))  # tolerate "3" and "3.0" (CSV/shapefile floats)
    area_rai = float(required("area_rai"))
    if not math.isfinite(area_rai) or area_rai < 0:
        raise ValueError(f"area_rai must be finite and >= 0, got {area_rai!r}")
    status = required("status")
    zone = str(row.get("Zone") or "").strip()
    return (layer_name, zone, sec_no, area_rai, status)


def load_rows(path: str) -> list:
    with open(path, newline="", encoding="utf-8") as handle:
        return [parse_row(r) for r in csv.DictReader(handle)]


def db_config() -> dict:
    return {
        "host": os.environ.get("POSTGRES_HOST", "localhost"),
        "port": int(os.environ.get("POSTGRES_PORT", "5432")),
        "dbname": os.environ.get("GIS_DB_NAME", "munbon_gis"),
        "user": os.environ.get("POSTGRES_USER", "postgres"),
        "password": os.environ.get("POSTGRES_PASSWORD", ""),
    }


def main() -> None:
    source = os.environ.get("CROP_REGISTRY_SOURCE")
    if not source:
        sys.exit(
            "CROP_REGISTRY_SOURCE is not set. Point it at a crop-registry CSV export "
            f"with columns {', '.join(REQUIRED_COLUMNS)} (+ optional Zone). Populating "
            "gis.crop_registry requires the upstream GIS shapefile export, which is not in this repo."
        )
    rows = load_rows(source)
    if not rows:
        sys.exit(f"{source} contained no rows; nothing to load (refusing a silent no-op).")
    import psycopg2  # lazy import: unit tests of parse_row/load_rows need no DB driver

    conn = psycopg2.connect(**db_config())
    try:
        with conn, conn.cursor() as cur:
            cur.executemany(
                'INSERT INTO gis.crop_registry (layer_name, "Zone", sec_no, area_rai, status) '
                "VALUES (%s, %s, %s, %s, %s) "
                'ON CONFLICT (layer_name, "Zone", sec_no) '
                "DO UPDATE SET area_rai = EXCLUDED.area_rai, status = EXCLUDED.status",
                rows,
            )
        print(f"loaded {len(rows)} rows into gis.crop_registry (idempotent upsert)")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
