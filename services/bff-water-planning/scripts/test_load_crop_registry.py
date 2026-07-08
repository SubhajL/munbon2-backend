"""F-07 unit tests for the crop_registry loader's pure mapping (no DB driver needed).
Run: pytest --noconftest -o addopts="" scripts/test_load_crop_registry.py

Tuple order matches INSERT_COLUMNS: (layer_name, Zone, sec_no, area_rai, status).
"""
import math
import os
import tempfile

import pytest

from load_crop_registry import load_rows, parse_row


class TestParseRow:
    def test_maps_valid_row_including_zone(self):
        row = {"layer_name": "area_1", "Zone": "1A", "sec_no": "3", "area_rai": "972.0", "status": "active"}
        assert parse_row(row) == ("area_1", "1A", 3, 972.0, "active")

    def test_zone_is_optional_and_defaults_to_empty(self):
        row = {"layer_name": "area_2", "sec_no": "5", "area_rai": "10", "status": "active"}
        assert parse_row(row) == ("area_2", "", 5, 10.0, "active")

    def test_strips_whitespace(self):
        row = {"layer_name": " area_2 ", "Zone": " 1B ", "sec_no": "5", "area_rai": "10", "status": " active "}
        assert parse_row(row) == ("area_2", "1B", 5, 10.0, "active")

    def test_sec_no_tolerates_float_formatted_integer(self):
        # GIS/shapefile CSV exports routinely float-format integers ("3.0").
        row = {"layer_name": "a", "sec_no": "3.0", "area_rai": "1", "status": "active"}
        assert parse_row(row)[2] == 3

    @pytest.mark.parametrize("missing", ["layer_name", "sec_no", "area_rai", "status"])
    def test_rejects_empty_required_column(self, missing):
        row = {"layer_name": "a", "sec_no": "1", "area_rai": "1", "status": "active"}
        row[missing] = ""
        with pytest.raises(ValueError):
            parse_row(row)

    @pytest.mark.parametrize("missing", ["layer_name", "sec_no", "area_rai", "status"])
    def test_none_from_ragged_row_raises_valueerror_not_typeerror(self, missing):
        # csv.DictReader yields None for a short/ragged row; must be ValueError, not TypeError.
        row = {"layer_name": "a", "sec_no": "1", "area_rai": "1", "status": "active"}
        row[missing] = None
        with pytest.raises(ValueError):
            parse_row(row)

    @pytest.mark.parametrize("bad", ["nan", "inf", "-inf", "-5"])
    def test_rejects_nonfinite_or_negative_area(self, bad):
        row = {"layer_name": "a", "sec_no": "1", "area_rai": bad, "status": "active"}
        with pytest.raises(ValueError):
            parse_row(row)


class TestLoadRows:
    def test_loads_rows_from_csv_with_zone(self):
        content = (
            "layer_name,Zone,sec_no,area_rai,status\n"
            "area_1,1A,3,972.0,active\n"
            "area_2,,5,10,active\n"
        )
        fd, path = tempfile.mkstemp(suffix=".csv")
        try:
            with os.fdopen(fd, "w") as f:
                f.write(content)
            assert load_rows(path) == [
                ("area_1", "1A", 3, 972.0, "active"),
                ("area_2", "", 5, 10.0, "active"),
            ]
        finally:
            os.remove(path)
