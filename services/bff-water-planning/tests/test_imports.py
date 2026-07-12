import importlib


def test_can_import_database_module():
    mod = importlib.import_module("src.database")
    assert hasattr(mod, "Database"), "Database class should exist in src.database"
