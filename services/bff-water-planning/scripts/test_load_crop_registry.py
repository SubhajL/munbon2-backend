"""F-07 unit tests for the crop_registry loader's pure mapping (no DB driver needed).
Run: pytest --noconftest -o addopts="" scripts/test_load_crop_registry.py
"""
import os
import tempfile

import pytest

from load_crop_registry import load_rows, parse_row


class TestParseRow:
    def test_maps_valid_row_to_typed_tuple(self):
        row = {"layer_name": "area_1", "sec_no": "3", "area_rai": "972.0", "status": "active"}
        assert parse_row(row) == ("area_1", 3, 972.0, "active")

    def test_strips_whitespace(self):
        row = {"layer_name": " area_2 ", "sec_no": "5", "area_rai": "10", "status": " active "}
        assert parse_row(row) == ("area_2", 5, 10.0, "active")

    @pytest.mark.parametrize("missing", ["layer_name", "sec_no", "area_rai", "status"])
    def test_rejects_missing_required_column(self, missing):
        row = {"layer_name": "a", "sec_no": "1", "area_rai": "1", "status": "active"}
        row[missing] = ""
        with pytest.raises(ValueError):
            parse_row(row)

    def test_rejects_negative_area(self):
        with pytest.raises(ValueError):
            parse_row({"layer_name": "a", "sec_no": "1", "area_rai": "-5", "status": "active"})


class TestLoadRows:
    def test_loads_rows_from_csv(self):
        content = "layer_name,sec_no,area_rai,status\narea_1,3,972.0,active\narea_2,5,10,active\n"
        fd, path = tempfile.mkstemp(suffix=".csv")
        try:
            with os.fdopen(fd, "w") as f:
                f.write(content)
            rows = load_rows(path)
            assert rows == [("area_1", 3, 972.0, "active"), ("area_2", 5, 10.0, "active")]
        finally:
            os.remove(path)
