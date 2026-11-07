"""Offline acceptance contracts; all credential material is synthetic."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(os.environ.get("S01_SCANNER_ROOT", Path(__file__).resolve().parents[2]))
SCANNER = ROOT / "tools/security/scan_tracked_secrets.py"
CANARY = "s01-synthetic-" + "not-for-authentication"
AWS_CANARY = "AKIA" + "1234567890ABCDEF"
KEY_MARKER = "BEGIN " + "RSA PRIVATE KEY"
LEGACY_PASSWORD = "legacy-" + "fixture-password"
LEGACY_HOST = "192.0.2.74"
POLICY_PATH = ".github/workflows/secret-scan.yml"
BASELINE_PATH = ".security/full-tree-baseline.txt"
BASELINE = f"# synthetic approved carriers\nlegacy.txt\n{POLICY_PATH}\n"
RULES = {
    "legacy-password",
    "legacy-host",
    "aws-access-key",
    "private-key",
    "credential-url",
    "literal-assignment",
    "environment-fallback",
}
ERRORS = {
    "INVALID_ARGUMENT",
    "INVALID_REF",
    "INVALID_RANGE",
    "INVALID_REPOSITORY",
    "INVALID_POLICY",
    "BASELINE_EXPANSION",
    "UNSUPPORTED_ENTRY",
    "UNSUPPORTED_ENCODING",
    "INPUT_UNREADABLE",
    "INPUT_TOO_LARGE",
    "GIT_FAILURE",
}


def policy_text() -> str:
    return (
        "jobs:\n"
        "  scan-diff:\n"
        "    run: |\n"
        "      pw='legacy-''fixture-password'\n"
        "      ip='192\\.0\\.2\\.74'\n"
        '      hard="($pw|$ip|AKIA[0-9A-Z]{16}|BEGIN [A-Z ]*PRIVATE KEY)"\n'
        "  full-tree-baseline:\n"
        "    run: |\n"
        "      pw='legacy-''fixture-password'\n"
        "      ip='192.0.2.74'\n"
    )


class Repository:
    def __init__(self, path: Path):
        self.path = path
        path.mkdir()
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "s01@example.invalid")
        self.git("config", "user.name", "Synthetic S01 Fixture")
        self.put(POLICY_PATH, policy_text())
        self.put(BASELINE_PATH, BASELINE)
        self.policy = self.commit()
        (path / POLICY_PATH).unlink()
        self.base = self.commit()

    def git(self, *args: str) -> str:
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
        result = subprocess.run(
            ["git", "-C", str(self.path), *args],
            capture_output=True,
            env=env,
            timeout=20,
        )
        if result.returncode:
            pytest.fail("synthetic Git fixture setup failed", pytrace=False)
        return result.stdout.decode().strip()

    def put(self, name: str, text: str | bytes) -> None:
        p = self.path / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(text.encode() if isinstance(text, str) else text)

    def commit(self) -> str:
        self.git("add", "-A")
        self.git("commit", "-qm", "synthetic fixture", "--allow-empty")
        return self.git("rev-parse", "HEAD")

    def scan(self, mode: str = "candidate", **selectors: str) -> tuple[int, dict]:
        return invoke(self.path, self.policy, mode, **selectors)


def invoke(
    repo: Path, policy: str, mode: str, *, extra: tuple[str, ...] = (), **selectors: str
) -> tuple[int, dict]:
    if not SCANNER.is_file():
        pytest.fail(
            "required scanner CLI does not exist (expected behavior RED)", pytrace=False
        )
    args = [
        sys.executable,
        str(SCANNER),
        "--repo",
        str(repo),
        "--policy-ref",
        policy,
        "--mode",
        mode,
    ]
    for key, value in selectors.items():
        args += ["--" + key.replace("_", "-"), value]
    result = subprocess.run(args + list(extra), capture_output=True, timeout=30)
    output = result.stdout + result.stderr
    for value in (CANARY, LEGACY_PASSWORD, AWS_CANARY, KEY_MARKER):
        if value.encode() in output:
            pytest.fail("scanner leaked synthetic credential material", pytrace=False)
    if result.stderr:
        pytest.fail("scanner emitted non-JSON stderr", pytrace=False)
    try:
        report = json.loads(result.stdout)
    except (ValueError, UnicodeDecodeError):
        pytest.fail("scanner did not emit one JSON report", pytrace=False)
    assert set(report) == {"status", "findings", "errors"}
    assert report["status"] in {"clean", "blocked", "error"}
    assert result.returncode == {"clean": 0, "blocked": 1, "error": 2}[report["status"]]
    assert isinstance(report["errors"], list)
    assert all(e in ERRORS for e in report["errors"])
    assert bool(report["errors"]) == (report["status"] == "error")
    for finding in report["findings"]:
        assert set(finding) == {"file", "line", "rule", "classification", "status"}
        assert finding["rule"] in RULES
        assert isinstance(finding["line"], int) and finding["line"] > 0
        assert finding["classification"] in {
            "credential-candidate",
            "legacy-host",
            "test-placeholder",
            "redaction-sentinel",
        }
        assert finding["status"] in {"blocked", "allowed"}
    canonical = sorted(
        {
            tuple(f[k] for k in ("file", "line", "rule", "classification", "status"))
            for f in report["findings"]
        }
    )
    actual = [
        tuple(f[k] for k in ("file", "line", "rule", "classification", "status"))
        for f in report["findings"]
    ]
    assert actual == canonical
    if result.returncode != 2:
        assert (result.returncode == 1) == any(
            f["status"] == "blocked" for f in report["findings"]
        )
    return result.returncode, report


def has(
    report: dict, rule: str, file: str, line: int = 1, status: str = "blocked"
) -> bool:
    return any(
        f["rule"] == rule
        and f["file"] == file
        and f["line"] == line
        and f["status"] == status
        for f in report["findings"]
    )


@pytest.fixture
def repo(tmp_path: Path) -> Repository:
    return Repository(tmp_path / "repo")


def test_literal_credential_is_blocked_without_echoing_value(repo: Repository):
    repo.put("config.py", '\npassword = "' + CANARY + '"\n')
    repo.commit()
    code, report = repo.scan()
    assert code == 1
    assert has(report, "literal-assignment", "config.py", 2)


@pytest.mark.parametrize(
    "source",
    [
        'password = os.environ["DB_PASSWORD"]\n',
        'password = os.getenv("DB_PASSWORD")\n',
        'password = os.environ.get("DB_PASSWORD")\n',
        "DB_PASSWORD=${DB_PASSWORD}\n",
        'DB_PASSWORD="$DB_PASSWORD"\n',
        "const password = process.env.DB_PASSWORD;\n",
    ],
)
def test_environment_only_configuration_has_no_literal_fallback(
    repo: Repository, source: str
):
    repo.put("config.py", source)
    repo.commit()
    code, report = repo.scan()
    assert code == 0
    assert report["findings"] == []


@pytest.mark.parametrize(
    "sentinel", ["REDACTED", "__REDACTED__", "[REDACTED]", "<REDACTED>"]
)
def test_redaction_sentinel_is_not_misreported_as_live_secret(
    repo: Repository, sentinel: str
):
    repo.put("bootstrap.py", f'password = "{sentinel}"\n')
    repo.commit()
    code, report = repo.scan()
    assert code == 0
    assert any(
        f["classification"] == "redaction-sentinel" and f["status"] == "allowed"
        for f in report["findings"]
    )


@pytest.mark.parametrize(
    "literal", ["password", "postgres", "test-password", "changeme", "dummy"]
)
def test_nonlocal_bootstrap_default_requires_disposition(
    repo: Repository, literal: str
):
    repo.put("scripts/test-remote.sh", f'PGPASSWORD="{literal}" remote-client\n')
    repo.commit()
    code, report = repo.scan()
    assert code == 1
    assert has(report, "literal-assignment", "scripts/test-remote.sh")


def test_explicit_test_placeholder_is_classified_but_unknown_test_secret_blocks(
    repo: Repository,
):
    repo.put("tests/unit/test_config.py", 'password = "test-password"\n')
    repo.commit()
    code, report = repo.scan()
    assert code == 0
    assert any(f["classification"] == "test-placeholder" for f in report["findings"])
    repo.put("tests/unit/test_config.py", 'password = "' + CANARY + '"\n')
    code, report = repo.scan()
    assert code == 1
    assert has(report, "literal-assignment", "tests/unit/test_config.py")


@pytest.mark.parametrize(
    "template",
    [
        'password: "{}"\n',
        '{{"api_key": "{}"}}\n',
        'const access_token = "{}";\n',
        "PGPASSWORD={} client\n",
        "CREATE ROLE fixture PASSWORD '{}';\n",
        "client --password '{}'\n",
        "client -P '{}'\n",
        'DB_PASSWORD="{}"\n',
    ],
)
def test_secret_assignment_forms_share_policy(repo: Repository, template: str):
    repo.put("source.txt", template.format(CANARY))
    repo.commit()
    code, report = repo.scan()
    assert code == 1
    assert has(report, "literal-assignment", "source.txt")


@pytest.mark.parametrize(
    "template",
    [
        'password = os.getenv("DB_PASSWORD", "{}")\n',
        'password = os.environ.get("DB_PASSWORD", "{}")\n',
        "DB_PASSWORD=${{DB_PASSWORD:-{}}}\n",
        "DB_PASSWORD=${{DB_PASSWORD-{}}}\n",
        'const password = process.env.DB_PASSWORD || "{}";\n',
        'const password = process.env.DB_PASSWORD ?? "{}";\n',
    ],
)
def test_literal_environment_fallback_is_blocked(repo: Repository, template: str):
    repo.put("config.txt", template.format(CANARY))
    repo.commit()
    code, report = repo.scan()
    assert code == 1
    assert has(report, "environment-fallback", "config.txt")


@pytest.mark.parametrize(
    "host", ["db.remote.invalid", "localhost", "postgres", "test-host"]
)
def test_credential_urls_cannot_use_host_exemptions(repo: Repository, host: str):
    repo.put("config.txt", "postgresql://fixture:" + CANARY + "@" + host + "/data\n")
    repo.commit()
    code, report = repo.scan()
    assert code == 1
    assert has(report, "credential-url", "config.txt")


def test_environment_url_and_redacted_url_are_allowed(repo: Repository):
    repo.put(
        "config.txt",
        "postgresql://fixture:${DB_PASSWORD}@db.remote.invalid/data\npostgresql://fixture:REDACTED@db.remote.invalid/data\n",
    )
    repo.commit()
    code, report = repo.scan()
    assert code == 0
    assert has(report, "credential-url", "config.txt", 2, "allowed")


def test_diff_and_full_tree_checks_share_one_scanner_policy(repo: Repository):
    repo.put("shared.py", 'password = "' + CANARY + '"\n')
    head = repo.commit()
    records = []
    for mode, selectors in [
        ("candidate", {}),
        ("index", {}),
        ("tree", {"ref": head}),
        ("range", {"base": repo.base, "head": head}),
    ]:
        code, report = repo.scan(mode, **selectors)
        assert code == 1
        records.append(report["findings"])
    assert all(records[0] == r for r in records[1:])


@pytest.mark.parametrize(
    "payload", ["no-newline", "nul", "crlf", "rename", "copy", "add-delete", "textconv"]
)
def test_newline_binary_rename_and_range_cases_cannot_hide_findings(
    repo: Repository, payload: str
):
    content = 'password = "' + CANARY + '"'
    if payload == "nul":
        content = "\0" + content + "\0"
    if payload == "crlf":
        content = "# fixture\r\n" + content + "\r\n"
    repo.put("source.txt", content)
    repo.commit()
    target = "source.txt"
    if payload == "rename":
        repo.git("mv", "source.txt", "renamed.txt")
        target = "renamed.txt"
        repo.commit()
    if payload == "copy":
        repo.put("copy.txt", content)
        target = "copy.txt"
        repo.commit()
    if payload == "add-delete":
        (repo.path / "source.txt").unlink()
        repo.commit()
    if payload == "textconv":
        marker = repo.path.parent / "MUST_NOT_EXIST"
        driver = repo.path.parent / "unsafe-driver.sh"
        driver.write_text(f'#!/bin/sh\ntouch "{marker}"\nprintf safe\n')
        driver.chmod(0o700)
        repo.put(".gitattributes", "*.txt diff=unsafe -text\n")
        repo.git("config", "diff.unsafe.textconv", str(driver))
        repo.git("config", "diff.external", str(driver))
        repo.commit()
    code, report = repo.scan(
        "range", base=repo.base, head=repo.git("rev-parse", "HEAD")
    )
    assert code == 1
    assert has(report, "literal-assignment", target, 2 if payload == "crlf" else 1)
    if payload == "textconv":
        assert not marker.exists()


def test_index_candidate_and_commit_select_distinct_bytes(repo: Repository):
    repo.put("config.py", 'password = "' + CANARY + '"\n')
    head = repo.commit()
    repo.put("config.py", "password = os.environ['DB_PASSWORD']\n")
    assert repo.scan()[0] == 0
    assert repo.scan("index")[0] == 1
    assert repo.scan("tree", ref=head)[0] == 1
    repo.git("add", "config.py")
    repo.put("config.py", 'password = "' + CANARY + '"\n')
    assert repo.scan("index")[0] == 0
    assert repo.scan()[0] == 1


def test_tracked_deletion_is_not_a_read_error(repo: Repository):
    repo.put("deleted.py", 'password = "' + CANARY + '"\n')
    repo.commit()
    (repo.path / "deleted.py").unlink()
    assert repo.scan()[0] == 0
    assert repo.scan("index")[0] == 1


def test_untracked_and_ignored_operator_files_are_not_inputs(repo: Repository):
    repo.put(".gitignore", "private/\n")
    repo.commit()
    repo.put("private/operator.py", 'password = "' + CANARY + '"\n')
    repo.put("untracked.py", 'password = "' + CANARY + '"\n')
    assert repo.scan()[0] == 0


def test_tracked_ignored_file_is_still_scanned(repo: Repository):
    repo.put(".gitignore", "ignored.py\n")
    repo.put("ignored.py", 'password = "' + CANARY + '"\n')
    repo.git("add", "-f", "ignored.py")
    repo.commit()
    code, report = repo.scan()
    assert code == 1
    assert has(report, "literal-assignment", "ignored.py")


@pytest.mark.parametrize(
    "entry", ["file-symlink", "parent-symlink", "committed-symlink", "gitlink"]
)
def test_unsupported_entries_never_follow_operator_paths(repo: Repository, entry: str):
    repo.put("nested/config.py", "safe = True\n")
    head = repo.commit()
    outside = repo.path.parent / "operator"
    outside.mkdir()
    (outside / "config.py").write_text('password = "' + CANARY + '"\n')
    if entry == "file-symlink":
        p = repo.path / "nested/config.py"
        p.unlink()
        p.symlink_to(outside / "config.py")
    elif entry == "parent-symlink":
        (repo.path / "nested/config.py").unlink()
        (repo.path / "nested").rmdir()
        (repo.path / "nested").symlink_to(outside, target_is_directory=True)
    elif entry == "committed-symlink":
        (repo.path / "link.py").symlink_to(outside / "config.py")
        head = repo.commit()
    else:
        repo.git("update-index", "--add", "--cacheinfo", f"160000,{head},module")
    code, report = (
        repo.scan("tree", ref=head) if entry == "committed-symlink" else repo.scan()
    )
    assert code == 2
    assert "UNSUPPORTED_ENTRY" in report["errors"]
    assert not report["findings"]


@pytest.mark.parametrize(
    "payload",
    [b"\xff\xfep\x00w\x00", b"\xffopaque", b"x" * (16 * 1024 * 1024 + 1)],
    ids=["utf16", "invalid-utf8", "over-limit"],
)
def test_unsupported_encoding_and_oversize_fail_closed(
    repo: Repository, payload: bytes
):
    repo.put("opaque.bin", payload)
    repo.commit()
    code, report = repo.scan()
    assert code == 2
    expected = (
        "INPUT_TOO_LARGE" if len(payload) > 16 * 1024 * 1024 else "UNSUPPORTED_ENCODING"
    )
    assert expected in report["errors"]


def test_unusual_filenames_are_lossless_and_control_safe(repo: Repository):
    path = 'odd name\nwith\ttab "and quote".py'
    repo.put(path, 'password = "' + CANARY + '"\n')
    repo.commit()
    code, report = repo.scan()
    assert code == 1
    assert has(report, "literal-assignment", path)


def test_report_and_test_logs_contain_no_secret_value(repo: Repository):
    path = "password=" + CANARY + ".txt"
    repo.put(path, 'password = "' + CANARY + '"\n')
    repo.commit()
    code, report = repo.scan()
    assert code == 1
    assert has(report, "literal-assignment", "[redacted-path]")


@pytest.mark.parametrize(
    "invalid",
    ["HEAD", "-h", "0" * 40, "f" * 40, "HEAD~1000", "x\n" + CANARY],
    ids=["symbolic", "option", "zero", "missing", "revision", "sensitive"],
)
def test_invalid_or_missing_ref_never_uses_fallback(repo: Repository, invalid: str):
    code, report = repo.scan("tree", ref=invalid)
    assert code == 2
    assert set(report["errors"]) & {"INVALID_REF", "INVALID_ARGUMENT"}


def test_invalid_cli_reports_no_argument_echo(repo: Repository):
    for mode, selectors in [
        ("tree", {}),
        ("range", {"head": repo.base}),
        ("candidate", {"ref": repo.base}),
        ("unknown", {}),
    ]:
        code, report = repo.scan(mode, **selectors)
        assert code == 2
        assert "INVALID_ARGUMENT" in report["errors"]
    code, report = invoke(
        repo.path, repo.policy, "candidate", extra=("--unknown", CANARY)
    )
    assert code == 2
    assert "INVALID_ARGUMENT" in report["errors"]


def test_repository_root_must_be_exact(repo: Repository, tmp_path: Path):
    for path in [repo.path / ".security", tmp_path]:
        code, report = invoke(path, repo.policy, "candidate")
        assert code == 2
        assert "INVALID_REPOSITORY" in report["errors"]


def test_empty_range_is_clean_but_reverse_or_divergent_range_is_error(repo: Repository):
    assert repo.scan("range", base=repo.base, head=repo.base)[0] == 0
    repo.put("new.txt", "safe\n")
    head = repo.commit()
    code, report = repo.scan("range", base=head, head=repo.base)
    assert code == 2
    assert "INVALID_RANGE" in report["errors"]
    repo.git("checkout", "-qb", "divergent", repo.policy)
    repo.put("divergent.txt", "safe\n")
    divergent = repo.commit()
    code, report = repo.scan("range", base=head, head=divergent)
    assert code == 2
    assert "INVALID_RANGE" in report["errors"]


def test_merge_side_commit_with_deleted_secret_is_scanned(repo: Repository):
    repo.git("checkout", "-qb", "side")
    repo.put("temporary.py", 'password = "' + CANARY + '"\n')
    repo.commit()
    (repo.path / "temporary.py").unlink()
    repo.commit()
    repo.git("checkout", "main")
    repo.put("main.txt", "safe\n")
    repo.commit()
    repo.git("merge", "--no-ff", "-qm", "synthetic merge", "side")
    head = repo.git("rev-parse", "HEAD")
    assert repo.scan("tree", ref=head)[0] == 0
    code, report = repo.scan("range", base=repo.base, head=head)
    assert code == 1
    assert has(report, "literal-assignment", "temporary.py")


def test_range_does_not_scan_unchanged_unrelated_blobs(repo: Repository):
    repo.put("old.py", 'password = "' + CANARY + '"\n')
    base = repo.commit()
    repo.put("new.txt", "safe\n")
    head = repo.commit()
    assert repo.scan("range", base=base, head=head)[0] == 0
    assert repo.scan("tree", ref=head)[0] == 1


def test_baseline_cannot_expand_to_accept_a_credential(repo: Repository):
    repo.put("new.py", 'password = "' + CANARY + '"\n')
    repo.put(BASELINE_PATH, BASELINE + "new.py\n")
    head = repo.commit()
    for mode, selectors in [
        ("candidate", {}),
        ("index", {}),
        ("tree", {"ref": head}),
        ("range", {"base": repo.base, "head": head}),
    ]:
        code, report = repo.scan(mode, **selectors)
        assert code == 2
        assert "BASELINE_EXPANSION" in report["errors"]


def test_baseline_carrier_only_waives_host_not_credentials(repo: Repository):
    repo.put("legacy.txt", LEGACY_HOST + "\n")
    repo.commit()
    code, report = repo.scan()
    assert code == 0
    assert has(report, "legacy-host", "legacy.txt", status="allowed")
    repo.put("legacy.txt", LEGACY_PASSWORD + "\n")
    code, report = repo.scan()
    assert code == 1
    assert has(report, "legacy-password", "legacy.txt")
    repo.put("legacy.txt", 'password="' + CANARY + '"\n')
    assert repo.scan()[0] == 1


def test_baseline_shrink_deletion_and_temporary_growth(repo: Repository):
    repo.put("legacy.txt", LEGACY_HOST + "\n")
    repo.put(BASELINE_PATH, "# empty after shrink\n")
    repo.commit()
    code, report = repo.scan()
    assert code == 1
    assert has(report, "legacy-host", "legacy.txt")
    (repo.path / BASELINE_PATH).unlink()
    assert repo.scan()[0] == 1
    repo.put(BASELINE_PATH, BASELINE + "new.txt\n")
    repo.commit()
    repo.put(BASELINE_PATH, BASELINE)
    head = repo.commit()
    code, report = repo.scan("range", base=repo.base, head=head)
    assert code == 2
    assert "BASELINE_EXPANSION" in report["errors"]


@pytest.mark.parametrize(
    "baseline",
    ["../outside\n", "/absolute\n", "legacy.txt\nlegacy.txt\n", "bad\\path\n"],
)
def test_malformed_baseline_is_error(repo: Repository, baseline: str):
    repo.put(BASELINE_PATH, baseline)
    repo.commit()
    code, report = repo.scan()
    assert code == 2
    assert "INVALID_POLICY" in report["errors"]


def test_legacy_policy_is_pinned_private_and_not_executed(repo: Repository):
    repo.put(POLICY_PATH, "pw='weakened'\n")
    repo.put("new.txt", LEGACY_PASSWORD + "\n")
    repo.commit()
    code, report = repo.scan()
    assert code == 1
    assert has(report, "legacy-password", "new.txt")
    bad_policy = repo.git("rev-parse", "HEAD")
    code, report = invoke(repo.path, bad_policy, "candidate")
    assert code == 2
    assert "INVALID_POLICY" in report["errors"]


@pytest.mark.parametrize(
    "content,rule",
    [
        ("aws", "aws-access-key"),
        ("key", "private-key"),
        ("legacy", "legacy-password"),
        ("host", "legacy-host"),
    ],
)
def test_historical_hard_patterns_remain_blocking(
    repo: Repository, content: str, rule: str
):
    value = {
        "aws": "AKIA" + "1234567890ABCDEF",
        "key": "-----BEGIN " + "RSA PRIVATE KEY-----",
        "legacy": LEGACY_PASSWORD,
        "host": LEGACY_HOST,
    }[content]
    repo.put("new.txt", value)
    repo.commit()
    code, report = repo.scan()
    assert code == 1
    assert has(report, rule, "new.txt")


def test_inherited_git_environment_cannot_redirect_inputs(
    repo: Repository, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    other = Repository(tmp_path / "other")
    repo.put("source.py", 'password = "' + CANARY + '"\n')
    repo.commit()
    monkeypatch.setenv("GIT_DIR", str(other.path / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(other.path))
    monkeypatch.setenv("GIT_INDEX_FILE", str(other.path / ".git/index"))
    code, report = repo.scan()
    assert code == 1
    assert has(report, "literal-assignment", "source.py")


def test_unmerged_index_is_not_silently_scanned(repo: Repository):
    repo.put("conflict.py", "safe = 0\n")
    repo.commit()
    repo.git("checkout", "-qb", "side")
    repo.put("conflict.py", "safe = 1\n")
    repo.commit()
    repo.git("checkout", "main")
    repo.put("conflict.py", "safe = 2\n")
    repo.commit()
    result = subprocess.run(
        ["git", "-C", str(repo.path), "merge", "side"], capture_output=True
    )
    assert result.returncode != 0
    code, report = repo.scan("index")
    assert code == 2
    assert "UNSUPPORTED_ENTRY" in report["errors"]


def test_adjacent_quoted_legacy_ip_policy_matches_real_grammar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    original = policy_text()
    adjacent = original.replace(
        "ip='192\\.0\\.2\\.74'", "ip='192\\.0''\\.2\\.74'"
    ).replace("ip='192.0.2.74'", "ip='192.0''.2.74'")
    assert adjacent != original
    monkeypatch.setattr(sys.modules[__name__], "policy_text", lambda: adjacent)
    repo = Repository(tmp_path / "repo")
    code, report = repo.scan("range", base=repo.base, head=repo.base)
    assert code == 0
    assert report == {"status": "clean", "findings": [], "errors": []}


def test_allowed_fallback_cannot_hide_another_literal_on_same_line(repo: Repository):
    repo.put(
        "config.py",
        'password = os.getenv("DB_PASSWORD", "REDACTED"); api_key = "' + CANARY + '"\n',
    )
    repo.commit()
    code, report = repo.scan()
    assert code == 1
    assert has(report, "environment-fallback", "config.py", status="allowed")
    assert has(report, "literal-assignment", "config.py")


@pytest.mark.parametrize("order", ["before", "after"])
@pytest.mark.parametrize(
    "independent",
    [
        'api_key = "{value}"',
        "CREATE ROLE fixture PASSWORD '{value}'",
        "client --password '{value}'",
        "client -P '{value}'",
    ],
    ids=["assignment", "sql", "long-cli", "short-cli"],
)
def test_fallback_deduplication_preserves_independent_same_line_rules(
    repo: Repository, independent: str, order: str
):
    fallback = 'password = os.getenv("DB_PASSWORD", "REDACTED")'
    literal = independent.format(value=CANARY)
    pieces = [literal, fallback] if order == "before" else [fallback, literal]
    repo.put("config.txt", "; ".join(pieces) + "\n")
    repo.commit()
    code, report = repo.scan()
    assert code == 1
    assert has(report, "environment-fallback", "config.txt", status="allowed")
    assert has(report, "literal-assignment", "config.txt")


def test_multiple_fallback_spans_do_not_shift_or_hide_remaining_literal(
    repo: Repository,
):
    repo.put(
        "config.txt",
        'password = os.getenv("DB_PASSWORD", "REDACTED"); '
        'api_key = "' + CANARY + '"; '
        'token = process.env.ACCESS_TOKEN || "__REDACTED__"\n',
    )
    repo.commit()
    code, report = repo.scan()
    assert code == 1
    assert has(report, "environment-fallback", "config.txt", status="allowed")
    assert has(report, "literal-assignment", "config.txt")
    assert not any(
        f["rule"] == "literal-assignment" and f["status"] == "allowed"
        for f in report["findings"]
    )


@pytest.mark.parametrize("mode", ["candidate", "index", "tree", "range"])
def test_committed_operator_symlink_is_rejected_in_every_mode(
    repo: Repository, mode: str
):
    (repo.path / "operator-link").symlink_to(repo.path.parent / "not-a-scan-input")
    head = repo.commit()
    selectors = (
        {"ref": head}
        if mode == "tree"
        else {"base": repo.base, "head": head}
        if mode == "range"
        else {}
    )
    code, report = repo.scan(mode, **selectors)
    assert code == 2
    assert report == {
        "status": "error",
        "findings": [],
        "errors": ["UNSUPPORTED_ENTRY"],
    }


def test_repository_warp_is_regular_canonical_policy_pointer():
    alias = ROOT / "WARP.md"
    assert not alias.is_symlink(), "WARP.md must be a regular policy pointer"
    assert alias.is_file()
    assert alias.read_text(encoding="utf-8") == (
        "# Repository instructions\n\n"
        "Read [CLAUDE.md](CLAUDE.md) for canonical repository policy and\n"
        "[AGENTS.md](AGENTS.md) for agent safety requirements.\n"
    )
    assert (ROOT / "CLAUDE.md").is_file()
    assert (ROOT / "AGENTS.md").is_file()


def test_repository_operator_link_is_removed_without_replacement():
    assert not os.path.lexists(ROOT / "view-conversations")


@pytest.mark.parametrize("mode", ["candidate", "index", "tree", "range"])
@pytest.mark.parametrize(
    "template",
    [
        'config = {{"password": "{value}"}}\n',
        "const config = {{'api_key': '{value}'}};\n",
    ],
    ids=["python-container", "javascript-container"],
)
def test_nonsecret_container_assignment_cannot_hide_secret_field(
    repo: Repository, mode: str, template: str
):
    repo.put("config.txt", template.format(value=CANARY))
    head = repo.commit()
    selectors = (
        {"ref": head}
        if mode == "tree"
        else {"base": repo.base, "head": head}
        if mode == "range"
        else {}
    )
    code, report = repo.scan(mode, **selectors)
    assert code == 1
    assert has(report, "literal-assignment", "config.txt")


@pytest.mark.parametrize(
    "key",
    ['"password"', "'api_key'", '"DB_PASSWORD"'],
    ids=["double-quoted", "single-quoted", "prefixed"],
)
def test_quoted_credential_assignment_filename_is_redacted_without_leaking(
    repo: Repository, key: str
):
    repo.put(key + "=" + CANARY + ".txt", 'password="' + CANARY + '"\n')
    repo.commit()
    code, report = repo.scan()
    assert code == 1
    assert has(report, "literal-assignment", "[redacted-path]")


def test_tracked_fifo_is_rejected_without_waiting_for_a_writer(repo: Repository):
    repo.put("input.txt", "safe\n")
    repo.commit()
    path = repo.path / "input.txt"
    path.unlink()
    os.mkfifo(path)
    result = subprocess.run(
        [
            sys.executable,
            str(SCANNER),
            "--repo",
            str(repo.path),
            "--policy-ref",
            repo.policy,
            "--mode",
            "candidate",
        ],
        capture_output=True,
        timeout=3,
    )
    assert result.returncode == 2
    assert result.stderr == b""
    assert json.loads(result.stdout) == {
        "status": "error",
        "findings": [],
        "errors": ["UNSUPPORTED_ENTRY"],
    }


@pytest.mark.parametrize("suffix", ["literal", "-literal", "/literal"])
def test_hardening_braced_environment_reference_with_suffix_is_not_env_only(
    repo: Repository, suffix: str
):
    repo.put("config.txt", "password=${DB_PASSWORD}" + suffix + "\n")
    repo.commit()
    code, report = repo.scan()
    assert code == 1
    assert has(report, "literal-assignment", "config.txt")


@pytest.mark.parametrize(
    "source",
    [
        'password = process.env.DB_PASSWORD || api_key = "{value}"\n',
        'password: process.env.DB_PASSWORD ?? token: "{value}"\n',
        'password = process.env.DB_PASSWORD || (api_key = "{value}")\n',
    ],
    ids=["assignment", "property", "parenthesized"],
)
def test_hardening_variable_default_cannot_consume_independent_assignment(
    repo: Repository, source: str
):
    repo.put("config.txt", source.replace("{value}", CANARY))
    repo.commit()
    code, report = repo.scan()
    assert code == 1
    assert has(report, "literal-assignment", "config.txt")


@pytest.mark.parametrize("mode", ["candidate", "index", "tree", "range"])
@pytest.mark.parametrize(
    "source",
    [
        'password = "" + "{value}"\n',
        'password=""{value}\n',
        'client --password "${DB_PASSWORD}"{value}\n',
        'client --password ""{value}\n',
        "ALTER ROLE fixture PASSWORD '' || '{value}';\n",
    ],
    ids=["empty-python", "empty-shell", "env-cli", "empty-cli", "empty-sql"],
)
def test_hardening_review_composed_empty_or_env_prefix_blocks_all_modes(
    repo: Repository, mode: str, source: str
):
    repo.put("config.txt", source.replace("{value}", CANARY))
    head = repo.commit()
    selectors = (
        {"ref": head}
        if mode == "tree"
        else {"base": repo.base, "head": head}
        if mode == "range"
        else {}
    )
    code, report = repo.scan(mode, **selectors)
    assert code == 1
    assert any(f["status"] == "blocked" for f in report["findings"])


@pytest.mark.parametrize(
    "source",
    [
        'password = ""\n',
        "client --password ''\n",
        'client --password "${DB_PASSWORD}"\n',
        "ALTER ROLE fixture PASSWORD '';\n",
    ],
    ids=["assignment", "cli-empty", "cli-env", "sql-empty"],
)
def test_hardening_review_standalone_empty_or_env_values_stay_clean(
    repo: Repository, source: str
):
    repo.put("config.txt", source)
    repo.commit()
    code, report = repo.scan()
    assert code == 0
    assert report["findings"] == []


@pytest.mark.parametrize("kind", ["javascript", "python", "shell"])
def test_hardening_review_nonsecret_key_fallback_filename_is_redacted(
    repo: Repository, kind: str
):
    names = {
        "javascript": 'config=process.env.DB_PASSWORD||"' + CANARY + '".txt',
        "python": 'config=os.getenv("DB_PASSWORD","' + CANARY + '").txt',
        "shell": "config=${DB_PASSWORD:-" + CANARY + "}.txt",
    }
    repo.put(names[kind], 'password="' + CANARY + '"\n')
    repo.commit()
    code, report = repo.scan()
    assert code == 1
    assert has(report, "literal-assignment", "[redacted-path]")


@pytest.mark.parametrize("mode", ["candidate", "index", "tree", "range"])
@pytest.mark.parametrize(
    "prefix",
    [
        'password=""',
        'password="REDACTED"',
        'client --password "${DB_PASSWORD}"',
        "password=",
        "client --password ",
    ],
    ids=[
        "empty-assignment",
        "sentinel-assignment",
        "environment-cli",
        "unquoted-assignment",
        "unquoted-cli",
    ],
)
def test_hardening_masked_fallback_suffix_cannot_hide_original_composition(
    repo: Repository, mode: str, prefix: str
):
    repo.put("config.txt", prefix + CANARY + "=${DB_PASSWORD:-REDACTED}\n")
    head = repo.commit()
    selectors = (
        {"ref": head}
        if mode == "tree"
        else {"base": repo.base, "head": head}
        if mode == "range"
        else {}
    )
    code, report = repo.scan(mode, **selectors)
    assert code == 1
    assert has(report, "literal-assignment", "config.txt")
    assert has(report, "environment-fallback", "config.txt", status="allowed")


HARDENING_FALLBACKS = [
    "password: process.env.DB_PASSWORD || '{value}',\n",
    '"api_key": process.env.API_KEY ?? "{value}",\n',
    'password = os.getenv("DB_PASSWORD") or "{value}"\n',
    'password = os.environ.get("DB_PASSWORD") or "{value}"\n',
    'password = os.environ["DB_PASSWORD"] or "{value}"\n',
    'const password = process.env.DB_PASSWORD || "{value}";\n',
    'password = os.getenv("DB_PASSWORD", "{value}")\n',
    'password = os.environ.get("DB_PASSWORD", "{value}")\n',
    "DB_PASSWORD=${DB_PASSWORD:-{value}}\n",
    "DB_PASSWORD: ${DB_PASSWORD:-{value}}\n",
    'password = "${DB_PASSWORD:-{value}}"\n',
    'config = {"password": process.env.DB_PASSWORD || "{value}"}\n',
]
HARDENING_FALLBACK_IDS = [
    "js-property-or",
    "js-property-nullish",
    "python-getenv-or",
    "python-environ-get-or",
    "python-environ-or",
    "js-assignment-or",
    "python-getenv-default",
    "python-environ-default",
    "shell-default",
    "yaml-default",
    "quoted-shell-default",
    "nested-js-property",
]


@pytest.mark.parametrize("mode", ["candidate", "index", "tree", "range"])
@pytest.mark.parametrize(
    "template", HARDENING_FALLBACKS[:3], ids=HARDENING_FALLBACK_IDS[:3]
)
def test_hardening_escalated_fallbacks_block_in_every_selector(
    repo: Repository, mode: str, template: str
):
    repo.put("config.txt", template.replace("{value}", CANARY))
    head = repo.commit()
    selectors = (
        {"ref": head}
        if mode == "tree"
        else {"base": repo.base, "head": head}
        if mode == "range"
        else {}
    )
    code, report = repo.scan(mode, **selectors)
    assert code == 1
    assert has(report, "environment-fallback", "config.txt")


@pytest.mark.parametrize("kind", ["literal", "sentinel"])
@pytest.mark.parametrize("template", HARDENING_FALLBACKS, ids=HARDENING_FALLBACK_IDS)
def test_hardening_fallback_forms_share_literal_and_sentinel_policy(
    repo: Repository, template: str, kind: str
):
    value = CANARY if kind == "literal" else "REDACTED"
    repo.put("config.txt", template.replace("{value}", value))
    repo.commit()
    code, report = repo.scan()
    assert code == (1 if kind == "literal" else 0)
    assert has(
        report,
        "environment-fallback",
        "config.txt",
        status="blocked" if kind == "literal" else "allowed",
    )
    assert len(report["findings"]) == 1


@pytest.mark.parametrize(
    "source",
    [
        'password = os.getenv("DB_PASSWORD", "")\n',
        'password = os.getenv("DB_PASSWORD", None)\n',
        'password = os.getenv("DB_PASSWORD", fallback_value)\n',
        'password = os.environ.get("DB_PASSWORD", "")\n',
        'password = os.environ.get("DB_PASSWORD", None)\n',
        'password = os.environ.get("DB_PASSWORD", fallback_value)\n',
        'password: process.env.DB_PASSWORD || ""\n',
        "password: process.env.DB_PASSWORD ?? fallbackValue\n",
        "DB_PASSWORD=${DB_PASSWORD:-}\n",
        'DB_PASSWORD="${DB_PASSWORD:-}"\n',
        "DB_PASSWORD: ${DB_PASSWORD:-}\n",
        'password = os.getenv("DB_PASSWORD") or ""\n',
    ],
    ids=[
        "getenv-empty",
        "getenv-none",
        "getenv-variable",
        "environ-empty",
        "environ-none",
        "environ-variable",
        "js-empty",
        "js-variable",
        "shell-empty",
        "shell-quoted-empty",
        "yaml-empty",
        "python-or-empty",
    ],
)
def test_hardening_empty_and_variable_defaults_are_not_literal_secrets(
    repo: Repository, source: str
):
    repo.put("config.txt", source)
    repo.commit()
    code, report = repo.scan()
    assert code == 0
    assert report["findings"] == []


@pytest.mark.parametrize(
    "source",
    [
        'password = os.getenv("DB_PASSWORD", "")',
        "DB_PASSWORD=${DB_PASSWORD:-}",
        'password: process.env.DB_PASSWORD || ""',
    ],
    ids=["python", "shell", "js"],
)
def test_hardening_empty_default_does_not_mask_independent_literal(
    repo: Repository, source: str
):
    repo.put("config.txt", source + '; api_key = "' + CANARY + '"\n')
    repo.commit()
    code, report = repo.scan()
    assert code == 1
    assert has(report, "literal-assignment", "config.txt")


@pytest.mark.parametrize(
    "source",
    [
        'password = "REDACTED" + "{value}"\n',
        'password = "REDACTED" "{value}"\n',
        'password: process.env.DB_PASSWORD || ("REDACTED" + "{value}"),\n',
        'password = os.getenv("DB_PASSWORD") or ("REDACTED" + "{value}")\n',
        "DB_PASSWORD=${DB_PASSWORD:-REDACTED}/{value}\n",
        'DB_PASSWORD="${DB_PASSWORD:-REDACTED}"{value}\n',
        'password="REDACTED"{value}\n',
        'password = os.getenv("DB_PASSWORD", "REDACTED") if flag else "{value}"\n',
    ],
    ids=[
        "literal-concat",
        "literal-adjacency",
        "js-parenthesized",
        "python-parenthesized",
        "shell-path-suffix",
        "shell-word-suffix",
        "literal-word-suffix",
        "python-conditional",
    ],
)
def test_hardening_composed_sentinel_prefix_is_not_an_allowed_literal(
    repo: Repository, source: str
):
    repo.put("config.txt", source.replace("{value}", CANARY))
    repo.commit()
    code, report = repo.scan()
    assert code == 1
    assert any(f["status"] == "blocked" for f in report["findings"])


@pytest.mark.parametrize("mode", ["candidate", "index", "tree", "range"])
def test_hardening_empty_username_credential_url_blocks_every_selector(
    repo: Repository, mode: str
):
    repo.put("config.txt", "CACHE_URL=redis://:" + CANARY + "@cache.invalid:6379/0\n")
    head = repo.commit()
    selectors = (
        {"ref": head}
        if mode == "tree"
        else {"base": repo.base, "head": head}
        if mode == "range"
        else {}
    )
    code, report = repo.scan(mode, **selectors)
    assert code == 1
    assert has(report, "credential-url", "config.txt")


@pytest.mark.parametrize("kind", ["environment", "empty", "sentinel"])
def test_hardening_empty_username_url_keeps_noncredential_controls(
    repo: Repository, kind: str
):
    value = {"environment": "${DB_PASSWORD}", "empty": "", "sentinel": "REDACTED"}[kind]
    repo.put("config.txt", "CACHE_URL=redis://:" + value + "@cache.invalid/0\n")
    repo.commit()
    code, report = repo.scan()
    assert code == 0
    if kind == "sentinel":
        assert has(report, "credential-url", "config.txt", status="allowed")
    else:
        assert report["findings"] == []


@pytest.mark.parametrize("kind", ["literal", "sentinel"])
@pytest.mark.parametrize(
    "source",
    [
        'config["password"] = "{value}"\n',
        "os.environ['DB_PASSWORD'] = '{value}'\n",
        'curl -d "{\\"password\\":\\"{value}\\"}"\n',
    ],
    ids=["subscript", "environment-write", "escaped-json"],
)
def test_hardening_subscript_and_escaped_keys_follow_literal_policy(
    repo: Repository, source: str, kind: str
):
    value = CANARY if kind == "literal" else "REDACTED"
    repo.put("config.txt", source.replace("{value}", value))
    repo.commit()
    code, report = repo.scan()
    assert code == (1 if kind == "literal" else 0)
    assert has(
        report,
        "literal-assignment",
        "config.txt",
        status="blocked" if kind == "literal" else "allowed",
    )


def test_hardening_quote_view_never_removes_original_blocked_value(repo: Repository):
    repo.put("config.txt", 'password = "REDACTED\\"' + CANARY + '"\n')
    repo.commit()
    code, report = repo.scan()
    assert code == 1
    assert has(report, "literal-assignment", "config.txt")


@pytest.mark.parametrize(
    "source",
    [
        "RUN mkdir -p /srv/app\n",
        "docker run -p 8080:80 image\n",
        "ssh -p 22 fixture.invalid\n",
        "psql -p 5432\n",
    ],
    ids=["mkdir", "docker-port", "ssh-port", "postgres-port"],
)
def test_hardening_lowercase_short_p_is_not_a_password_option(
    repo: Repository, source: str
):
    repo.put("config.txt", source)
    repo.commit()
    code, report = repo.scan()
    assert code == 0
    assert report["findings"] == []


@pytest.mark.parametrize("option", ["-P", "--password", "--PASSWORD"])
def test_hardening_password_options_remain_blocking(repo: Repository, option: str):
    repo.put("config.txt", "client " + option + " '" + CANARY + "'\n")
    repo.commit()
    code, report = repo.scan()
    assert code == 1
    assert has(report, "literal-assignment", "config.txt")


@pytest.mark.parametrize("kind", ["identifier", "scheme-like"])
def test_hardening_long_token_runs_finish_within_bounded_cli_time(
    repo: Repository, kind: str
):
    source = "a" * 1_000_000 if kind == "identifier" else "a." * 500_000
    repo.put("long.txt", source + "\n")
    repo.commit()
    result = subprocess.run(
        [
            sys.executable,
            str(SCANNER),
            "--repo",
            str(repo.path),
            "--policy-ref",
            repo.policy,
            "--mode",
            "candidate",
        ],
        capture_output=True,
        timeout=10,
    )
    assert result.returncode == 0
    assert result.stderr == b""
    assert json.loads(result.stdout) == {
        "status": "clean",
        "findings": [],
        "errors": [],
    }


@pytest.mark.parametrize("form", ["assignment", "fallback"])
@pytest.mark.parametrize(
    "value",
    ["REDACTED ", " REDACTED", " test-password ", "   "],
    ids=[
        "sentinel-trailing-space",
        "sentinel-leading-space",
        "placeholder-padding",
        "nonempty-whitespace",
    ],
)
def test_hardening_only_exact_sentinels_and_placeholders_are_allowed(
    repo: Repository, value: str, form: str
):
    source = (
        'password = "' + value + '"\n'
        if form == "assignment"
        else 'password = os.getenv("DB_PASSWORD", "' + value + '")\n'
    )
    repo.put("tests/unit/test_config.py", source)
    repo.commit()
    code, report = repo.scan()
    assert code == 1
    assert any(f["status"] == "blocked" for f in report["findings"])


@pytest.mark.parametrize(
    "kind", ["aws", "key-marker", "cli", "sql", "escaped-key", "subscript"]
)
def test_hardening_sensitive_filename_shapes_are_redacted(repo: Repository, kind: str):
    names = {
        "aws": AWS_CANARY + ".txt",
        "key-marker": KEY_MARKER + ".txt",
        "cli": "client -P " + CANARY + ".txt",
        "sql": "PASSWORD '" + CANARY + "'.txt",
        "escaped-key": '\\"password\\"=' + CANARY + ".txt",
        "subscript": 'config["password"]=' + CANARY + ".txt",
    }
    repo.put(names[kind], 'password="' + CANARY + '"\n')
    repo.commit()
    code, report = repo.scan()
    assert code == 1
    assert has(report, "literal-assignment", "[redacted-path]")
