import hashlib
import json
from decimal import Decimal
from pathlib import Path

from services.requirement_source_loader import load_requirement_source_manifest

REPO_ROOT = Path(__file__).resolve().parents[4]
CONTRACT_ROOT = REPO_ROOT / "contracts/planning-depth-roster/v1"


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path):
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _contract_set_sha256(manifest):
    records = []
    for group in ("schemas", "fixtures"):
        for entry in manifest[group]:
            record = {key: entry[key] for key in entry if key != "sha256"}
            record["sha256"] = _sha256(CONTRACT_ROOT / entry["relative_path"])
            records.append(record)
    encoded = json.dumps(
        records,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def test_roster_contract_is_pinned_and_matches_the_approved_source_manifest():
    contract_manifest = _load(CONTRACT_ROOT / "manifest.json")
    fixture = _load(CONTRACT_ROOT / "roster.active-v5.example.json")
    source_manifest = load_requirement_source_manifest()

    entries = contract_manifest["schemas"] + contract_manifest["fixtures"]
    assert contract_manifest["contract_set_sha256"] == _contract_set_sha256(
        contract_manifest
    )
    for entry in entries:
        assert entry["sha256"] == _sha256(CONTRACT_ROOT / entry["relative_path"])
    assert {
        row["section_number"]: row["zone_number"]
        for row in source_manifest["section_master"]["section_memberships"]
    } == {
        int(row["section_id"].rsplit("-", 1)[1]): int(row["zone_id"].rsplit("-", 1)[1])
        for row in fixture["sections"]
    }
    assert Decimal(str(fixture["total_area_rai"])) == Decimal(
        source_manifest["section_master"]["total_area_rai"]
    )
    expected_areas = {
        row["section_number"]: Decimal(row["area_rai"])
        for source_key in ("excel_overrides", "gis_expected_areas")
        for row in source_manifest["section_master"][source_key]
    }
    assert {
        int(row["section_id"].rsplit("-", 1)[1]): Decimal(str(row["area_rai"]))
        for row in fixture["sections"]
    } == expected_areas
