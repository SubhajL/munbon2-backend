"""F-07: tracked loader for gis.crop_registry.

Previously the table was read by scripts but written by nothing in-repo, so it had no
reproducible, tracked population path. This loader ingests crop-registry rows from a CSV
source (whose path is given by CROP_REGISTRY_SOURCE) into gis.crop_registry, using DB
credentials from the environment (never hardcoded). It FAILS CLOSED when the source is not
configured — it does not silently run against an empty/absent source.

Long-term, gis.crop_registry should be retired in favour of gis.agricultural_plots (the
maintained table); this gives it a reproducible loader until then. The upstream source is a
GIS shapefile export, which is not in this repo — export it to a CSV with the columns below
and point CROP_REGISTRY_SOURCE at it.

Usage:
    POSTGRES_HOST=... POSTGRES_PASSWORD=... CROP_REGISTRY_SOURCE=crop_registry.csv \\
        python scripts/load_crop_registry.py
"""
import csv
import os
import sys

REQUIRED_COLUMNS = ("layer_name", "sec_no", "area_rai", "status")


def parse_row(row: dict) -> tuple:
    """Map one CSV row to a gis.crop_registry tuple. Raises ValueError on missing/invalid fields."""
    missing = [c for c in REQUIRED_COLUMNS if not str(row.get(c, "")).strip()]
    if missing:
        raise ValueError(f"row missing required columns: {missing}")
    area_rai = float(row["area_rai"])
    if area_rai < 0:
        raise ValueError(f"area_rai must be >= 0, got {area_rai}")
    return (str(row["layer_name"]).strip(), int(row["sec_no"]), area_rai, str(row["status"]).strip())


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
            f"with columns {', '.join(REQUIRED_COLUMNS)}. Populating gis.crop_registry "
            "requires the upstream GIS shapefile export, which is not in this repo."
        )
    rows = load_rows(source)
    import psycopg2  # lazy import: unit tests of parse_row/load_rows need no DB driver

    conn = psycopg2.connect(**db_config())
    try:
        with conn, conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO gis.crop_registry (layer_name, sec_no, area_rai, status) "
                "VALUES (%s, %s, %s, %s)",
                rows,
            )
        print(f"loaded {len(rows)} rows into gis.crop_registry")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
