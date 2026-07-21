import apply_bff_migration


def test_migration_failure_prints_only_safe_error_type(monkeypatch, capsys):
    monkeypatch.setenv(
        "POSTGRES_URL", "not-postgres://operator:secret@internal-db.example/munbon"
    )

    assert apply_bff_migration.main() == 1

    output = capsys.readouterr().out
    assert output == "BFF migration failed: PostgresDsnError\n"
    assert "secret" not in output
    assert "internal-db" not in output
