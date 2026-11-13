"""Offline acceptance contracts; all credential material is synthetic."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
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
    def __init__(self, path: Path, *, object_format: str = "sha1"):
        self.path = path
        path.mkdir()
        self.git("init", "-q", "-b", "main", "--object-format=" + object_format)
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


@pytest.mark.parametrize("mode", ["candidate", "index", "tree", "range"])
@pytest.mark.parametrize(
    "expression,classification,status",
    [
        (
            'password=process.env.DB_PASSWORD||"REDACTED"',
            "redaction-sentinel",
            "allowed",
        ),
        (
            "password=process.env.DB_PASSWORD??'__REDACTED__'",
            "redaction-sentinel",
            "allowed",
        ),
        ('password=process.env.DB_PASSWORD||""', None, None),
        ("password=process.env.DB_PASSWORD??fallbackValue", None, None),
        (
            'password=process.env.DB_PASSWORD||"{value}"',
            "credential-candidate",
            "blocked",
        ),
        (
            'password = process.env.DB_PASSWORD || "REDACTED"',
            "redaction-sentinel",
            "allowed",
        ),
    ],
    ids=["or-sentinel", "nullish-sentinel", "empty", "variable", "literal", "spaced"],
)
def test_hardening_standalone_js_fallback_before_closing_paren_stays_allowed(
    repo: Repository,
    mode: str,
    expression: str,
    classification: str | None,
    status: str | None,
):
    repo.put(
        "config.txt", "configure(" + expression.replace("{value}", CANARY) + ");\n"
    )
    head = repo.commit()
    selectors = (
        {"ref": head}
        if mode == "tree"
        else {"base": repo.base, "head": head}
        if mode == "range"
        else {}
    )
    code, report = repo.scan(mode, **selectors)
    findings = (
        []
        if classification is None
        else [
            {
                "file": "config.txt",
                "line": 1,
                "rule": "environment-fallback",
                "classification": classification,
                "status": status,
            }
        ]
    )
    assert report["findings"] == findings
    assert code == (1 if status == "blocked" else 0)


@pytest.mark.parametrize("mode", ["candidate", "index", "tree", "range"])
@pytest.mark.parametrize(
    "tail",
    ["", "  ;", ", next_value", "};"],
    ids=["end", "spaced-semicolon", "comma", "brace"],
)
def test_hardening_closing_paren_terminal_delimiters_keep_one_allowed_fallback(
    repo: Repository, mode: str, tail: str
):
    repo.put(
        "config.txt",
        'configure(password=process.env.DB_PASSWORD||"REDACTED")' + tail + "\n",
    )
    head = repo.commit()
    selectors = (
        {"ref": head}
        if mode == "tree"
        else {"base": repo.base, "head": head}
        if mode == "range"
        else {}
    )
    code, report = repo.scan(mode, **selectors)
    assert report["findings"] == [
        {
            "file": "config.txt",
            "line": 1,
            "rule": "environment-fallback",
            "classification": "redaction-sentinel",
            "status": "allowed",
        }
    ]
    assert code == 0


@pytest.mark.parametrize("mode", ["candidate", "index", "tree", "range"])
@pytest.mark.parametrize("order", ["before", "after"])
@pytest.mark.parametrize(
    "independent,classification,status",
    [
        ('api_key="REDACTED"', "redaction-sentinel", "allowed"),
        ("client --password 'REDACTED'", "redaction-sentinel", "allowed"),
        ("ALTER ROLE fixture PASSWORD 'REDACTED'", "redaction-sentinel", "allowed"),
        ('api_key="{value}"', "credential-candidate", "blocked"),
    ],
    ids=["allowed-assignment", "allowed-cli", "allowed-sql", "blocked-assignment"],
)
def test_hardening_closing_paren_keeps_independent_same_line_finding(
    repo: Repository,
    mode: str,
    order: str,
    independent: str,
    classification: str,
    status: str,
):
    fallback = 'configure(password=process.env.DB_PASSWORD||"REDACTED")'
    literal = independent.replace("{value}", CANARY)
    pieces = [literal, fallback] if order == "before" else [fallback, literal]
    repo.put("config.txt", "; ".join(pieces) + ";\n")
    head = repo.commit()
    selectors = (
        {"ref": head}
        if mode == "tree"
        else {"base": repo.base, "head": head}
        if mode == "range"
        else {}
    )
    code, report = repo.scan(mode, **selectors)
    assert report["findings"] == [
        {
            "file": "config.txt",
            "line": 1,
            "rule": "environment-fallback",
            "classification": "redaction-sentinel",
            "status": "allowed",
        },
        {
            "file": "config.txt",
            "line": 1,
            "rule": "literal-assignment",
            "classification": classification,
            "status": status,
        },
    ]
    assert code == (1 if status == "blocked" else 0)


@pytest.mark.parametrize("mode", ["candidate", "index", "tree", "range"])
@pytest.mark.parametrize(
    "suffix",
    [
        ') + "{value}";',
        ')+"{value}";',
        ').concat("{value}");',
        "){value};",
        "));",
        ") ]",
        ') if condition else "{value}"',
        ') && "{value}"',
        ') || "{value}"',
        ') ?? "{value}"',
    ],
    ids=[
        "spaced-plus",
        "adjacent-plus",
        "member",
        "adjacent-word",
        "nested",
        "other-closer",
        "conditional",
        "and",
        "or",
        "nullish",
    ],
)
def test_hardening_closing_paren_does_not_allow_composition_or_ambiguous_suffix(
    repo: Repository, mode: str, suffix: str
):
    repo.put(
        "config.txt",
        'configure(password=process.env.DB_PASSWORD||"REDACTED"'
        + suffix.replace("{value}", CANARY)
        + "\n",
    )
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


@pytest.mark.parametrize("mode", ["candidate", "index", "tree", "range"])
@pytest.mark.parametrize(
    "prefix",
    [
        "password=",
        'password=""',
        'password="REDACTED"',
        'client --password "${DB_PASSWORD}"',
        "client --password ",
    ],
    ids=[
        "bare-assignment",
        "empty-assignment",
        "sentinel-assignment",
        "environment-cli",
        "bare-cli",
    ],
)
def test_hardening_closing_paren_cannot_hide_enclosing_original_prefix(
    repo: Repository, mode: str, prefix: str
):
    repo.put(
        "config.txt",
        prefix + CANARY + '=process.env.DB_PASSWORD||"REDACTED");\n',
    )
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


def test_hardening_closing_paren_keeps_raw_view_and_python_env_call(repo: Repository):
    repo.put("config.txt", 'password=os.getenv("DB_PASSWORD")\n')
    repo.commit()
    assert repo.scan() == (0, {"status": "clean", "findings": [], "errors": []})
    repo.put(
        "config.txt",
        r"configure(password=process.env.DB_PASSWORD||\"REDACTED\");" + "\n",
    )
    code, report = repo.scan()
    assert code == 1
    assert has(report, "literal-assignment", "config.txt")


@pytest.mark.parametrize("mode", ["candidate", "index", "tree", "range"])
@pytest.mark.parametrize(
    "source",
    [
        'password=os.getenv("DB_PASSWORD")or"REDACTED");\n',
        'x[password=process.env.DB_PASSWORD||"REDACTED"];\n',
    ],
    ids=["python-or", "closing-bracket"],
)
def test_hardening_closing_paren_does_not_extend_other_fallbacks_or_closers(
    repo: Repository, mode: str, source: str
):
    repo.put("config.txt", source)
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


@pytest.mark.parametrize("mode", ["candidate", "index", "tree", "range"])
@pytest.mark.parametrize(
    "kind", ["comma-operator", "next-line-plus", "template-brace", "template-semicolon"]
)
def test_hardening_closing_paren_preserves_multiline_enclosing_credentials(
    repo: Repository, mode: str, kind: str
):
    expression = 'String(password=process.env.DB_PASSWORD||"REDACTED")'
    lines = {
        "comma-operator": "  (" + expression + ', "' + CANARY + '");\n',
        "next-line-plus": "  " + expression + '\n  + "' + CANARY + '";\n',
        "template-brace": "`prefix ${" + expression + "}suffix-" + CANARY + "`;\n",
        "template-semicolon": '`prefix\nconfigure(password=process.env.DB_PASSWORD||"REDACTED");\nsuffix-'
        + CANARY
        + "`;\n",
    }
    repo.put("config.txt", "const api_key =\n" + lines[kind])
    head = repo.commit()
    selectors = (
        {"ref": head}
        if mode == "tree"
        else {"base": repo.base, "head": head}
        if mode == "range"
        else {}
    )
    code, report = repo.scan(mode, **selectors)
    line = 3 if kind == "template-semicolon" else 2
    assert code == 1
    assert has(report, "literal-assignment", "config.txt", line)
    assert has(report, "environment-fallback", "config.txt", line, status="allowed")


@pytest.mark.parametrize("mode", ["candidate", "index", "tree", "range"])
@pytest.mark.parametrize(
    "source,target_line",
    [
        ('set_api_key(String({fallback}), "{value}");\n', 1),
        ('{call}, "{value}";\n', 1),
        ('{call}}"{value}";\n', 1),
        ("tag(`${String({fallback})}{value}`);\n", 1),
        ('note="{value}"; {call};\n', 1),
        ('api_key="REDACTED"; {call}; note="{value}";\n', 1),
        ('api_key=REDACTED; {call}; note="{value}";\n', 1),
        ("api_key:\n  {call}; {value}\n", 2),
        ('const api_key =\n{call};\n"{value}";\n', 2),
        ('{call}\n + "{value}";\n', 1),
        ('x="$(printf %s ";\n{call};\ny="{value})";\n', 2),
        ('note="""\n{call};\n{value}"""\n', 2),
        ("note='''\n{call};\n{value}'''\n", 2),
        ("/*\n{call};\n{value}\n*/\n", 2),
        ("const note=/\n{call};\n{value}/;\n", 2),
        ("note=<<END\n{call};\n{value}\nEND\n", 2),
        ("SELECT $tag$\n{call};\n{value}\n$tag$;\n", 2),
        ('note=";{value}"; {call};\n', 1),
        ('{call};\nnote="{value}";\n', 1),
        ('client --password "REDACTED";\n{call};\n{value}\n', 2),
        ("{call}, next_value\n{call};\n", 1),
    ],
    ids=[
        "nested-call",
        "comma-literal",
        "brace-literal",
        "inline-template",
        "unknown-prefix",
        "unknown-third-segment",
        "bare-sentinel-prefix",
        "yaml-scalar",
        "pending-assignment",
        "next-line-composition",
        "shell-substitution",
        "triple-double",
        "triple-single",
        "block-comment",
        "regexp-context",
        "heredoc-context",
        "dollar-quote",
        "quoted-semicolon",
        "later-unknown-revokes-earlier-proof",
        "multiline-cli-is-not-a-proof-boundary",
        "fragment-tail-is-not-multiline-grammar",
    ],
)
def test_hardening_lexical_certificate_never_clears_unsupported_context(
    repo: Repository, mode: str, source: str, target_line: int
):
    fallback = 'password=process.env.DB_PASSWORD||"REDACTED"'
    source = (
        source.replace("{call}", "configure(" + fallback + ")")
        .replace("{fallback}", fallback)
        .replace("{value}", CANARY)
    )
    repo.put("config.txt", source)
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
    assert has(report, "literal-assignment", "config.txt", target_line)
    assert has(
        report, "environment-fallback", "config.txt", target_line, status="allowed"
    )


@pytest.mark.parametrize("mode", ["candidate", "index", "tree", "range"])
@pytest.mark.parametrize(
    "separator",
    ["\x00", "\x0b", "\x0c", "\x1c", "\r", "\x85", "\u2028", "\u2029"],
    ids=["nul", "vertical-tab", "form-feed", "file-separator", "cr", "nel", "ls", "ps"],
)
def test_hardening_lexical_certificate_rejects_non_ascii_line_boundaries(
    repo: Repository, mode: str, separator: str
):
    repo.put(
        "config.txt",
        'configure(password=process.env.DB_PASSWORD||"REDACTED");'
        + separator
        + '"'
        + CANARY
        + '";\n',
    )
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


@pytest.mark.parametrize("mode", ["candidate", "index", "tree", "range"])
@pytest.mark.parametrize(
    "source,expected",
    [
        (
            'api_key="REDACTED";\n{call};\n',
            [(1, "literal-assignment"), (2, "environment-fallback")],
        ),
        (
            '{call};\napi_key="REDACTED";\n',
            [(1, "environment-fallback"), (2, "literal-assignment")],
        ),
        (
            'const api_key="REDACTED";\n{call};\n',
            [(1, "literal-assignment"), (2, "environment-fallback")],
        ),
        (
            "{call};\n  {call};\n",
            [(1, "environment-fallback"), (2, "environment-fallback")],
        ),
        ("\n \t\n{call};\n\n", [(3, "environment-fallback")]),
        ("\r\n \t\r\n{call};\r\n\r\n", [(3, "environment-fallback")]),
        (
            'api_key="REDACTED";\r\n{call};',
            [(1, "literal-assignment"), (2, "environment-fallback")],
        ),
        (
            'api_key="REDACTED";\n{call};',
            [(1, "literal-assignment"), (2, "environment-fallback")],
        ),
        ("{call};", [(1, "environment-fallback")]),
    ],
    ids=[
        "classified-before",
        "classified-after",
        "classified-declaration",
        "two-complete-calls",
        "ascii-blank-lines",
        "crlf-blank-lines",
        "crlf-no-final-newline",
        "lf-no-final-newline",
        "single-no-final-newline",
    ],
)
def test_hardening_lexical_certificate_preserves_exact_supported_findings(
    repo: Repository, mode: str, source: str, expected: list[tuple[int, str]]
):
    call = 'configure(password=process.env.DB_PASSWORD||"REDACTED")'
    repo.put("config.txt", source.replace("{call}", call))
    head = repo.commit()
    selectors = (
        {"ref": head}
        if mode == "tree"
        else {"base": repo.base, "head": head}
        if mode == "range"
        else {}
    )
    code, report = repo.scan(mode, **selectors)
    assert code == 0
    assert report == {
        "status": "clean",
        "errors": [],
        "findings": [
            {
                "file": "config.txt",
                "line": line,
                "rule": rule,
                "classification": "redaction-sentinel",
                "status": "allowed",
            }
            for line, rule in expected
        ],
    }


@pytest.mark.parametrize("mode", ["candidate", "index", "tree", "range"])
@pytest.mark.parametrize("secret_first", [True, False], ids=["before", "after"])
def test_hardening_lexical_certificate_preserves_independent_blocked_line(
    repo: Repository, mode: str, secret_first: bool
):
    secret = 'api_key="' + CANARY + '";'
    call = 'configure(password=process.env.DB_PASSWORD||"REDACTED");'
    repo.put(
        "config.txt",
        "\n".join([secret, call] if secret_first else [call, secret]) + "\n",
    )
    head = repo.commit()
    selectors = (
        {"ref": head}
        if mode == "tree"
        else {"base": repo.base, "head": head}
        if mode == "range"
        else {}
    )
    code, report = repo.scan(mode, **selectors)
    secret_line, call_line = (1, 2) if secret_first else (2, 1)
    assert code == 1
    assert report["findings"] == sorted(
        [
            {
                "file": "config.txt",
                "line": secret_line,
                "rule": "literal-assignment",
                "classification": "credential-candidate",
                "status": "blocked",
            },
            {
                "file": "config.txt",
                "line": call_line,
                "rule": "environment-fallback",
                "classification": "redaction-sentinel",
                "status": "allowed",
            },
        ],
        key=lambda finding: finding["line"],
    )


@pytest.mark.parametrize("mode", ["candidate", "index", "tree", "range"])
@pytest.mark.parametrize("order", ["before", "after"])
@pytest.mark.parametrize(
    "other",
    [
        'client --db_password="{value}"',
        'client --password= "{value}"',
        'ALTER ROLE fixture DB_PASSWORD "{value}"',
    ],
    ids=["prefixed-cli-option", "cli-equals-space", "prefixed-sql-word"],
)
def test_hardening_lexical_certificate_requires_actual_literal_owner(
    repo: Repository, mode: str, order: str, other: str
):
    call = 'configure(password=process.env.DB_PASSWORD||"REDACTED")'
    other = other.replace("{value}", CANARY)
    parts = [other, call] if order == "before" else [call, other]
    repo.put("config.txt", "; ".join(parts) + ";\n")
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


@pytest.mark.parametrize("mode", ["candidate", "index", "tree", "range"])
@pytest.mark.parametrize(
    "separator",
    ["]=", " ] : ", ":", " : "],
    ids=["bracket", "spaced-bracket-colon", "colon", "spaced-colon"],
)
@pytest.mark.parametrize("multiline", [False, True], ids=["single", "revokes-earlier"])
def test_hardening_lexical_certificate_review_malformed_keys_revoke_all_proofs(
    repo: Repository, mode: str, separator: str, multiline: bool
):
    valid = 'configure(password=process.env.DB_PASSWORD||"REDACTED");\n'
    malformed = (
        "configure(password" + separator + 'process.env.DB_PASSWORD||"REDACTED");\n'
    )
    repo.put("config.txt", (valid if multiline else "") + malformed)
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
    for line in range(1, 3 if multiline else 2):
        assert has(report, "literal-assignment", "config.txt", line)
        assert has(report, "environment-fallback", "config.txt", line, status="allowed")


@pytest.mark.parametrize("mode", ["candidate", "index", "tree", "range"])
@pytest.mark.parametrize("other_first", [True, False], ids=["before", "after"])
@pytest.mark.parametrize(
    "other",
    ['client --password "REDACTED";', "ALTER ROLE fixture PASSWORD 'REDACTED';"],
    ids=["cli-only-trigger", "sql-only-trigger"],
)
def test_hardening_lexical_certificate_review_multiline_other_is_single_veto(
    repo: Repository, mode: str, other_first: bool, other: str
):
    call = 'configure(password=process.env.DB_PASSWORD||"REDACTED");'
    repo.put(
        "config.txt", "\n".join([other, call] if other_first else [call, other]) + "\n"
    )
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
    call_line = 2 if other_first else 1
    assert has(report, "literal-assignment", "config.txt", call_line)
    assert has(
        report, "environment-fallback", "config.txt", call_line, status="allowed"
    )


@pytest.mark.parametrize("mode", ["candidate", "index", "tree", "range"])
@pytest.mark.parametrize(
    "source,expected",
    [
        (
            'client --password="REDACTED"; {call};\n',
            [(1, "environment-fallback"), (1, "literal-assignment")],
        ),
        (
            '{call}; client --password="REDACTED";\n',
            [(1, "environment-fallback"), (1, "literal-assignment")],
        ),
        (
            'client -P "REDACTED"; {call};\n',
            [(1, "environment-fallback"), (1, "literal-assignment")],
        ),
        (
            '{call}; client -P "REDACTED";\n',
            [(1, "environment-fallback"), (1, "literal-assignment")],
        ),
        (
            'let api_key = "REDACTED";\n{call};\n',
            [(1, "literal-assignment"), (2, "environment-fallback")],
        ),
        (
            'var api_key = "REDACTED";\n{call};\n',
            [(1, "literal-assignment"), (2, "environment-fallback")],
        ),
        (
            'configure(password=process.env.DB_PASSWORD||"[REDACTED]");\n',
            [(1, "environment-fallback")],
        ),
        (
            'configure(password=process.env.DB_PASSWORD||"<REDACTED>");\n',
            [(1, "environment-fallback")],
        ),
        ("{call}}\n", [(1, "environment-fallback")]),
    ],
    ids=[
        "cli-equals-before",
        "cli-equals-after",
        "short-p-before",
        "short-p-after",
        "let-spaced",
        "var-spaced",
        "bracket-marker",
        "angle-marker",
        "brace-without-semicolon",
    ],
)
def test_hardening_lexical_certificate_review_supported_branches_remain_exact(
    repo: Repository, mode: str, source: str, expected: list[tuple[int, str]]
):
    call = 'configure(password=process.env.DB_PASSWORD||"REDACTED")'
    repo.put("config.txt", source.replace("{call}", call))
    head = repo.commit()
    selectors = (
        {"ref": head}
        if mode == "tree"
        else {"base": repo.base, "head": head}
        if mode == "range"
        else {}
    )
    code, report = repo.scan(mode, **selectors)
    assert code == 0
    assert report["findings"] == [
        {
            "file": "config.txt",
            "line": line,
            "rule": rule,
            "classification": "redaction-sentinel",
            "status": "allowed",
        }
        for line, rule in expected
    ]


@pytest.mark.parametrize(
    "payload",
    [b"", b"\r", b"a" * (16 * 1024 * 1024)],
    ids=["empty", "cr-only", "max-token"],
)
def test_hardening_lexical_certificate_degenerate_blobs_remain_total(
    repo: Repository, payload: bytes
):
    repo.put("config.txt", payload)
    repo.commit()
    assert repo.scan() == (0, {"status": "clean", "findings": [], "errors": []})


# S01-INPUT-1: real Git identities, index flags and safe traversal boundaries.
def _input_expected_error(result: tuple[int, dict], error: str) -> None:
    assert result == (2, {"status": "error", "findings": [], "errors": [error]})


def _input_select(repo: Repository, selector: str, object_id: str) -> tuple[int, dict]:
    if selector.startswith("policy-"):
        mode = selector.removeprefix("policy-")
        selectors = (
            {"ref": repo.base}
            if mode == "tree"
            else {"base": repo.policy, "head": repo.base}
            if mode == "range"
            else {}
        )
        return invoke(repo.path, object_id, mode, **selectors)
    if selector == "ref":
        return repo.scan("tree", ref=object_id)
    if selector == "base":
        return repo.scan("range", base=object_id, head=repo.base)
    assert selector == "head"
    return repo.scan("range", base=repo.policy, head=object_id)


@pytest.mark.parametrize("object_format", ["sha1", "sha256"])
@pytest.mark.parametrize("alias_shape", ["native", "other-width", "uppercase"])
@pytest.mark.parametrize(
    "selector",
    [
        "policy-candidate",
        "policy-index",
        "policy-tree",
        "policy-range",
        "ref",
        "base",
        "head",
    ],
)
def test_input_hardening_ref_aliases_cannot_replace_immutable_ids(
    tmp_path: Path, object_format: str, alias_shape: str, selector: str
):
    repo = Repository(tmp_path / "repo", object_format=object_format)
    width = 40 if object_format == "sha1" else 64
    if alias_shape == "other-width":
        width = 64 if width == 40 else 40
    alias = ("AB" if alias_shape == "uppercase" else "ab") * (width // 2)
    repo.git("update-ref", "refs/heads/" + alias, repo.policy)
    _input_expected_error(_input_select(repo, selector, alias), "INVALID_REF")


@pytest.mark.parametrize(
    "selector",
    [
        "policy-candidate",
        "policy-index",
        "policy-tree",
        "policy-range",
        "ref",
        "base",
        "head",
    ],
)
def test_input_hardening_sha256_abbreviations_are_not_immutable_ids(
    tmp_path: Path, selector: str
):
    repo = Repository(tmp_path / "repo", object_format="sha256")
    _input_expected_error(
        _input_select(repo, selector, repo.policy[:40]), "INVALID_REF"
    )


@pytest.mark.parametrize("object_format", ["sha1", "sha256"])
@pytest.mark.parametrize("mode", ["candidate", "index", "tree", "range"])
def test_input_hardening_native_full_ids_preserve_all_selectors(
    tmp_path: Path, object_format: str, mode: str
):
    repo = Repository(tmp_path / "repo", object_format=object_format)
    repo.put("config.txt", 'password="' + CANARY + '"\n')
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


@pytest.mark.parametrize("flags", ["skip", "assume", "both"])
@pytest.mark.parametrize("nested", [False, True], ids=["root", "nested"])
@pytest.mark.parametrize("present", [False, True], ids=["missing", "present-clean"])
def test_input_hardening_candidate_refuses_flagged_index_entries(
    repo: Repository, flags: str, nested: bool, present: bool
):
    name = "nested/config.txt" if nested else "config.txt"
    repo.put(name, 'password="' + CANARY + '"\n')
    repo.commit()
    if flags in {"skip", "both"}:
        repo.git("update-index", "--skip-worktree", name)
    if flags in {"assume", "both"}:
        repo.git("update-index", "--assume-unchanged", name)
    if present:
        repo.put(name, "ordinary text\n")
    else:
        (repo.path / name).unlink()
        if nested:
            (repo.path / "nested").rmdir()
    _input_expected_error(repo.scan(), "UNSUPPORTED_ENTRY")


@pytest.mark.parametrize("flags", ["skip", "assume", "both"])
@pytest.mark.parametrize("mode", ["index", "tree"])
def test_input_hardening_flagged_index_and_tree_still_scan_raw_blobs(
    repo: Repository, flags: str, mode: str
):
    repo.put("config.txt", 'password="' + CANARY + '"\n')
    head = repo.commit()
    if flags in {"skip", "both"}:
        repo.git("update-index", "--skip-worktree", "config.txt")
    if flags in {"assume", "both"}:
        repo.git("update-index", "--assume-unchanged", "config.txt")
    repo.put("config.txt", "ordinary text\n")
    code, report = repo.scan(mode, **({"ref": head} if mode == "tree" else {}))
    assert code == 1
    assert has(report, "literal-assignment", "config.txt")


def test_input_hardening_sparse_checkout_is_not_a_clean_candidate(repo: Repository):
    repo.put("visible/ordinary.txt", "ordinary text\n")
    repo.put("hidden/config.txt", 'password="' + CANARY + '"\n')
    repo.commit()
    repo.git("sparse-checkout", "init", "--cone")
    repo.git("sparse-checkout", "set", "visible")
    assert not (repo.path / "hidden/config.txt").exists()
    _input_expected_error(repo.scan(), "UNSUPPORTED_ENTRY")
    repo.git("sparse-checkout", "disable")
    code, report = repo.scan()
    assert code == 1
    assert has(report, "literal-assignment", "hidden/config.txt")


def test_input_hardening_real_unflagged_deletion_remains_omitted(repo: Repository):
    repo.put("nested/config.txt", 'password="' + CANARY + '"\n')
    repo.commit()
    (repo.path / "nested/config.txt").unlink()
    (repo.path / "nested").rmdir()
    assert repo.scan() == (0, {"status": "clean", "findings": [], "errors": []})


def _input_platform_scan(
    repo: Repository, setup: str, mode: str = "candidate", **selectors: str
) -> tuple[int, dict]:
    shim = (
        "import os,runpy,sys\n" + setup + "\n"
        "sys.argv=sys.argv[1:]\nrunpy.run_path(sys.argv[0],run_name='__main__')\n"
    )
    args = [
        sys.executable,
        "-I",
        "-c",
        shim,
        str(SCANNER),
        "--repo",
        str(repo.path),
        "--policy-ref",
        repo.policy,
        "--mode",
        mode,
    ]
    for key, value in selectors.items():
        args += ["--" + key.replace("_", "-"), value]
    result = subprocess.run(args, capture_output=True, timeout=30)
    assert not result.stderr, "synthetic platform shim emitted diagnostics"
    for value in (CANARY, LEGACY_PASSWORD, AWS_CANARY, KEY_MARKER):
        assert (
            value.encode() not in result.stdout
        ), "platform shim leaked fixture material"
    report = json.loads(result.stdout)
    assert set(report) == {"status", "findings", "errors"}
    assert result.returncode == {"clean": 0, "blocked": 1, "error": 2}[report["status"]]
    return result.returncode, report


_INPUT_PLATFORM_SETUPS = [
    "del os.O_NOFOLLOW",
    "os.O_DIRECTORY=0",
    "os.supports_dir_fd=set()",
    (
        "real_open=os.open\n"
        "def no_dirfd(*args,**kwargs):\n"
        "    if 'dir_fd' in kwargs: raise NotImplementedError('synthetic only')\n"
        "    return real_open(*args,**kwargs)\n"
        "os.open=no_dirfd\nos.supports_dir_fd=set(os.supports_dir_fd)|{no_dirfd}"
    ),
]


@pytest.mark.parametrize(
    "setup",
    _INPUT_PLATFORM_SETUPS,
    ids=["nofollow", "directory", "dirfd-capability", "dirfd-call"],
)
@pytest.mark.parametrize("entry", ["leaf", "parent"])
def test_input_hardening_platform_cannot_follow_operator_shaped_links(
    repo: Repository, setup: str, entry: str
):
    repo.put("nested/config.txt", "ordinary text\n")
    repo.commit()
    outside = repo.path.parent / "synthetic-outside"
    outside.mkdir()
    (outside / "config.txt").write_text('password="' + CANARY + '"\n')
    (repo.path / "nested/config.txt").unlink()
    if entry == "leaf":
        (repo.path / "nested/config.txt").symlink_to(outside / "config.txt")
    else:
        (repo.path / "nested").rmdir()
        (repo.path / "nested").symlink_to(outside, target_is_directory=True)
    _input_expected_error(_input_platform_scan(repo, setup), "UNSUPPORTED_ENTRY")


@pytest.mark.parametrize(
    "setup",
    _INPUT_PLATFORM_SETUPS,
    ids=["nofollow", "directory", "dirfd-capability", "dirfd-call"],
)
def test_input_hardening_candidate_requires_platform_even_for_regular_files(
    repo: Repository, setup: str
):
    repo.put("config.txt", "ordinary text\n")
    repo.commit()
    _input_expected_error(_input_platform_scan(repo, setup), "UNSUPPORTED_ENTRY")


@pytest.mark.parametrize(
    "setup",
    _INPUT_PLATFORM_SETUPS,
    ids=["nofollow", "directory", "dirfd-capability", "dirfd-call"],
)
@pytest.mark.parametrize("mode", ["index", "tree", "range"])
def test_input_hardening_immutable_modes_do_not_need_candidate_primitives(
    repo: Repository, setup: str, mode: str
):
    repo.put("config.txt", 'password="' + CANARY + '"\n')
    head = repo.commit()
    selectors = (
        {"ref": head}
        if mode == "tree"
        else {"base": repo.base, "head": head}
        if mode == "range"
        else {}
    )
    code, report = _input_platform_scan(repo, setup, mode, **selectors)
    assert code == 1
    assert has(report, "literal-assignment", "config.txt")


@pytest.mark.parametrize(
    "response",
    [
        "--show-object-format=storage\n",
        "sha1\nsha256\nsha1\n",
        "",
        "SHA1\nSHA1\nSHA1\n",
        " sha1\nsha1\nsha1\n",
    ],
    ids=["old-git-echo", "mixed", "empty", "uppercase", "whitespace"],
)
def test_input_hardening_unknown_object_format_never_defaults_to_sha1(
    repo: Repository, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, response: str
):
    real_git = shutil.which("git")
    assert real_git is not None
    directory = tmp_path / "shim-bin"
    directory.mkdir()
    wrapper = directory / "git"
    wrapper.write_text(
        "#!" + sys.executable + "\nimport os,sys\n"
        "if any(arg.startswith('--show-object-format') for arg in sys.argv[1:]):\n"
        "    sys.stdout.write(" + repr(response) + ");sys.exit(0)\n"
        "os.execv(" + repr(real_git) + ",['git',*sys.argv[1:]])\n"
    )
    wrapper.chmod(0o700)
    monkeypatch.setenv("PATH", str(directory) + os.pathsep + os.environ.get("PATH", ""))
    _input_expected_error(repo.scan(), "INVALID_REPOSITORY")


@pytest.mark.parametrize("symlink", [False, True], ids=["regular", "link"])
def test_input_hardening_grafts_cannot_hide_intermediate_credentials(
    repo: Repository, symlink: bool
):
    base = repo.base
    repo.put("config.txt", 'password="' + CANARY + '"\n')
    repo.commit()
    (repo.path / "config.txt").unlink()
    repo.commit()
    head = repo.commit()
    code, report = repo.scan("range", base=base, head=head)
    assert code == 1
    assert has(report, "literal-assignment", "config.txt")
    grafts = repo.path / ".git/info/grafts"
    content = head + " " + base + "\n"
    if symlink:
        target = repo.path.parent / "synthetic-grafts"
        target.write_text(content)
        grafts.symlink_to(target)
    else:
        grafts.write_text(content)
    _input_expected_error(repo.scan("range", base=base, head=head), "INVALID_RANGE")


def test_input_hardening_shallow_range_requires_complete_history(
    repo: Repository, tmp_path: Path
):
    repo.put(POLICY_PATH, policy_text())
    head = repo.commit()
    clone = tmp_path / "shallow-clone"
    repo.git(
        "clone", "--no-local", "--depth=1", "--branch=main", str(repo.path), str(clone)
    )
    assert (clone / ".git/shallow").is_file()
    code, report = invoke(clone, head, "tree", ref=head)
    assert code == 0
    assert report["errors"] == []
    _input_expected_error(
        invoke(clone, head, "range", base=head, head=head), "INVALID_RANGE"
    )


# S01-R1-REPAIR-1: deterministic actual-main concurrency and parser contracts.
def _repair_scan(
    repo: Repository, setup: str, mode: str = "candidate", **selectors: str
) -> tuple[int, dict]:
    script = (
        "import importlib.util,os,pathlib,sys\n"
        "sys.dont_write_bytecode=True\n"
        "spec=importlib.util.spec_from_file_location('synthetic_repair',sys.argv[1])\n"
        "m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m\n"
        "spec.loader.exec_module(m)\n"
        + setup
        + "\nraise SystemExit(m.main(sys.argv[2:]))\n"
    )
    args = [
        sys.executable,
        "-I",
        "-c",
        script,
        str(SCANNER),
        "--repo",
        str(repo.path),
        "--policy-ref",
        repo.policy,
        "--mode",
        mode,
    ]
    for key, value in selectors.items():
        args += ["--" + key.replace("_", "-"), value]
    result = subprocess.run(args, capture_output=True, timeout=30)
    assert not result.stderr, "synthetic repair shim emitted diagnostics"
    for value in (CANARY, LEGACY_PASSWORD, AWS_CANARY, KEY_MARKER):
        assert (
            value.encode() not in result.stdout
        ), "repair shim leaked fixture material"
    report = json.loads(result.stdout)
    assert set(report) == {"status", "findings", "errors"}
    assert result.returncode == {"clean": 0, "blocked": 1, "error": 2}[report["status"]]
    return result.returncode, report


@pytest.mark.parametrize("flags", ["skip-worktree", "assume-unchanged"])
@pytest.mark.parametrize("restore", [False, True], ids=["persistent", "aba"])
def test_review_repair_index_flag_mutation_cannot_omit_credential(
    repo: Repository, flags: str, restore: bool
):
    content = 'password="' + CANARY + '"\n'
    repo.put("config.txt", content)
    repo.commit()
    setup = (
        "original=m._index_entries\n"
        "def interleave(root,**kwargs):\n"
        "    entries=original(root,**kwargs)\n"
        "    m._git_command(root,['update-index','--" + flags + "','config.txt'])\n"
        "    (root/'config.txt').unlink()\n"
        "    return entries\n"
        "m._index_entries=interleave\n"
    )
    if restore:
        setup += (
            "read=m._read_candidate_file\n"
            "def restore_after_read(root,path):\n"
            "    data=read(root,path)\n"
            "    if path=='config.txt':\n"
            "        (root/path).write_text(" + repr(content) + ")\n"
            "        m._git_command(root,['update-index','--no-" + flags + "',path])\n"
            "    return data\n"
            "m._read_candidate_file=restore_after_read\n"
        )
    _input_expected_error(_repair_scan(repo, setup), "UNSUPPORTED_ENTRY")


def test_review_repair_index_same_semantics_aba_is_not_quiescent(repo: Repository):
    repo.put("config.txt", "ordinary text\n")
    repo.commit()
    setup = (
        "original=m._index_entries\n"
        "def interleave(root,**kwargs):\n"
        "    entries=original(root,**kwargs)\n"
        "    m._git_command(root,['update-index','--skip-worktree','config.txt'])\n"
        "    m._git_command(root,['update-index','--no-skip-worktree','config.txt'])\n"
        "    return entries\n"
        "m._index_entries=interleave\n"
    )
    _input_expected_error(_repair_scan(repo, setup), "UNSUPPORTED_ENTRY")


@pytest.mark.parametrize("mutation", ["rotate", "same-bytes", "ancestor-aba"])
def test_review_repair_worktree_capture_cannot_mix_moving_states(
    repo: Repository, mutation: str
):
    secret = 'password="' + CANARY + '"\n'
    ordinary = "x" * (len(secret) - 1) + "\n"
    repo.put("nested/a.txt", ordinary)
    repo.put("nested/b.txt", secret if mutation == "rotate" else ordinary)
    repo.commit()
    action = (
        "        a=root/'nested/a.txt';b=root/'nested/b.txt'\n"
        "        sa=a.stat();sb=b.stat()\n"
        "        a.write_text("
        + repr(secret)
        + ");b.write_text("
        + repr(ordinary)
        + ")\n"
        "        os.utime(a,ns=(sa.st_atime_ns,sa.st_mtime_ns))\n"
        "        os.utime(b,ns=(sb.st_atime_ns,sb.st_mtime_ns))\n"
        if mutation == "rotate"
        else "        p=root/path;data_before=p.read_bytes();s=p.stat()\n"
        "        p.write_bytes(b'z'*len(data_before));p.write_bytes(data_before)\n"
        "        os.utime(p,ns=(s.st_atime_ns,s.st_mtime_ns))\n"
        if mutation == "same-bytes"
        else "        (root/'nested').rename(root/'moved')\n"
        "        (root/'moved').rename(root/'nested')\n"
    )
    setup = (
        "original=m._read_candidate_file\n"
        "def interleave(root,path):\n"
        "    data=original(root,path)\n"
        "    if path=='nested/a.txt':\n" + action + "    return data\n"
        "m._read_candidate_file=interleave\n"
    )
    _input_expected_error(_repair_scan(repo, setup), "UNSUPPORTED_ENTRY")


@pytest.mark.parametrize("split", [False, True], ids=["ordinary-index", "split-index"])
def test_review_repair_unchanged_deletion_and_split_index_controls(
    repo: Repository, split: bool
):
    repo.put("nested/config.txt", 'password="' + CANARY + '"\n')
    repo.commit()
    if split:
        repo.git("update-index", "--split-index")
    (repo.path / "nested/config.txt").unlink()
    (repo.path / "nested").rmdir()
    assert repo.scan() == (0, {"status": "clean", "findings": [], "errors": []})


def test_review_repair_linked_worktree_uses_its_own_index(
    repo: Repository, tmp_path: Path
):
    repo.put("config.txt", 'password="' + CANARY + '"\n')
    repo.commit()
    linked = tmp_path / "linked"
    repo.git("worktree", "add", "-q", "-b", "synthetic-linked", str(linked))
    code, report = invoke(linked, repo.policy, "candidate")
    assert code == 1 and has(report, "literal-assignment", "config.txt")


def _repair_intermediate(repo: Repository) -> tuple[str, str]:
    base = repo.base
    repo.put("config.txt", 'password="' + CANARY + '"\n')
    repo.commit()
    (repo.path / "config.txt").unlink()
    return base, repo.commit()


@pytest.mark.parametrize("transient", [False, True], ids=["persistent", "transient"])
def test_review_repair_late_graft_cannot_hide_intermediate(
    repo: Repository, transient: bool
):
    base, head = _repair_intermediate(repo)
    assert repo.scan("range", base=base, head=head)[0] == 1
    setup = (
        "original=m._validate_range_history\ncount=0\n"
        "def interleave(root):\n"
        "    global count\n"
        "    count+=1\n"
        + ("    if count==2: (root/'.git/info/grafts').unlink()\n" if transient else "")
        + "    original(root)\n"
        "    if count==1: (root/'.git/info/grafts').write_text("
        + repr(head + " " + base + "\n")
        + ")\n"
        "m._validate_range_history=interleave\n"
    )
    result = _repair_scan(repo, setup, "range", base=base, head=head)
    if transient:
        assert result[0] == 1 and has(result[1], "literal-assignment", "config.txt")
    else:
        _input_expected_error(result, "INVALID_RANGE")


def test_review_repair_transient_base_graft_cannot_exclude_side_history(
    repo: Repository,
):
    base = repo.base
    repo.git("checkout", "-qb", "side", repo.policy)
    repo.put("temporary.py", 'password="' + CANARY + '"\n')
    repo.commit()
    (repo.path / "temporary.py").unlink()
    side = repo.commit()
    repo.git("checkout", "-q", "main")
    repo.put("ordinary.txt", "ordinary text\n")
    repo.commit()
    repo.git("merge", "--no-ff", "-qm", "synthetic merge", "side")
    head = repo.git("rev-parse", "HEAD")
    assert repo.scan("range", base=base, head=head)[0] == 1
    setup = (
        "original=m._validate_range_history\ncount=0\n"
        "def interleave(root):\n"
        "    global count\n"
        "    count+=1\n"
        "    if count==2: (root/'.git/info/grafts').unlink()\n"
        "    original(root)\n"
        "    if count==1: (root/'.git/info/grafts').write_text("
        + repr(base + " " + repo.policy + " " + side + "\n")
        + ")\n"
        "m._validate_range_history=interleave\n"
    )
    code, report = _repair_scan(repo, setup, "range", base=base, head=head)
    assert code == 1 and has(report, "literal-assignment", "temporary.py")


def test_review_repair_transient_shallow_cannot_hide_intermediate(repo: Repository):
    base, deleted = _repair_intermediate(repo)
    repo.git("checkout", "-qb", "side", base)
    repo.put("side.txt", "ordinary text\n")
    repo.commit()
    repo.git("checkout", "-q", "main")
    repo.git("merge", "--no-ff", "-qm", "synthetic merge", "side")
    head = repo.git("rev-parse", "HEAD")
    setup = (
        "original=m._validate_range_history\ncount=0\n"
        "def interleave(root):\n"
        "    global count\n"
        "    count+=1\n"
        "    if count==2: (root/'.git/shallow').unlink()\n"
        "    original(root)\n"
        "    if count==1: (root/'.git/shallow').write_text("
        + repr(deleted + "\n")
        + ")\n"
        "m._validate_range_history=interleave\n"
    )
    code, report = _repair_scan(repo, setup, "range", base=base, head=head)
    assert code == 1 and has(report, "literal-assignment", "config.txt")


@pytest.mark.parametrize("mode", ["candidate", "tree", "range"])
def test_review_repair_embedded_newline_repository_path(tmp_path: Path, mode: str):
    repo = Repository(tmp_path / "repo\nembedded")
    base, head = _repair_intermediate(repo)
    if mode != "range":
        repo.put("config.txt", 'password="' + CANARY + '"\n')
        head = repo.commit()
    selectors = (
        {"base": base, "head": head}
        if mode == "range"
        else {"ref": head}
        if mode == "tree"
        else {}
    )
    code, report = repo.scan(mode, **selectors)
    assert code == 1 and has(report, "literal-assignment", "config.txt")


def test_review_repair_dangling_graft_is_rejected_without_following(repo: Repository):
    (repo.path / ".git/info/grafts").symlink_to(repo.path / "does-not-exist")
    _input_expected_error(
        repo.scan("range", base=repo.base, head=repo.base), "INVALID_RANGE"
    )


@pytest.mark.parametrize("object_format", ["sha1", "sha256"])
@pytest.mark.parametrize("parser", ["tree", "index", "range"])
@pytest.mark.parametrize("shape", ["wrong-width", "uppercase", "zero", "nonhex"])
def test_review_repair_raw_object_ids_fail_closed_through_main(
    tmp_path: Path, object_format: str, parser: str, shape: str
):
    repo = Repository(tmp_path / "repo", object_format=object_format)
    repo.put("ordinary.txt", "ordinary text\n")
    head = repo.commit()
    width = 40 if object_format == "sha1" else 64
    bad = (
        "a" * (64 if width == 40 else 40)
        if shape == "wrong-width"
        else "A" * width
        if shape == "uppercase"
        else "0" * width
        if shape == "zero"
        else "g" * width
    )
    if parser == "tree":
        condition = "'ls-tree' in args and args[-1]==" + repr(head)
        replacement = repr(("100644 blob " + bad + "\tordinary.txt\0").encode())
        mode, selectors, error = "tree", {"ref": head}, "UNSUPPORTED_ENTRY"
    elif parser == "index":
        condition = "'ls-files' in args"
        replacement = repr(("H 100644 " + bad + " 0\tordinary.txt\0").encode())
        mode, selectors, error = "index", {}, "UNSUPPORTED_ENTRY"
    else:
        condition = "'rev-list' in args"
        replacement = repr((bad + " " + repo.base + "\n").encode())
        mode, selectors, error = (
            "range",
            {"base": repo.base, "head": head},
            "GIT_FAILURE",
        )
    setup = (
        "original=m._git_command\n"
        "def inject(root,args,**kwargs):\n"
        "    if " + condition + ": return m.GitResult(0," + replacement + ")\n"
        "    return original(root,args,**kwargs)\n"
        "m._git_command=inject\n"
    )
    _input_expected_error(_repair_scan(repo, setup, mode, **selectors), error)


@pytest.mark.parametrize("tag", ["X", "M", "?", "!"])
def test_review_repair_unknown_raw_index_tag_rejected(repo: Repository, tag: str):
    setup = (
        "original=m._git_command\n"
        "def inject(root,args,**kwargs):\n"
        "    r=original(root,args,**kwargs)\n"
        "    if 'ls-files' in args: return m.GitResult(0,"
        + repr(tag.encode())
        + "+r.stdout[1:])\n"
        "    return r\n"
        "m._git_command=inject\n"
    )
    _input_expected_error(_repair_scan(repo, setup, "index"), "UNSUPPORTED_ENTRY")


@pytest.mark.parametrize("bad", ["mismatch", "zero", "late", "missing-tree"])
def test_review_repair_raw_parent_crosscheck_is_wired(repo: Repository, bad: str):
    base, head = _repair_intermediate(repo)
    setup = (
        "original=m._git_command\n"
        "def inject(root,args,**kwargs):\n"
        "    r=original(root,args,**kwargs)\n"
        "    if 'cat-file' in args and 'commit' in args and args[-1]=="
        + repr(head)
        + ":\n"
        + (
            "        raw=r.stdout.replace(b'parent ',b'parent '+b'0'*40+b'\\nparent ',1)\n"
            if bad == "zero"
            else "        raw=b'author synthetic\\n\\nmessage\\n'\n"
            if bad == "missing-tree"
            else "        raw=r.stdout.replace(b'\\n\\n',b'\\nparent '+"
            + repr(base.encode())
            + "+b'\\n\\n',1)\n"
            if bad == "late"
            else "        raw=b'\\n'.join(line for line in r.stdout.split(b'\\n') if not line.startswith(b'parent '))\n"
        )
        + "        return m.GitResult(0,raw)\n"
        "    return r\n"
        "m._git_command=inject\n"
    )
    _input_expected_error(
        _repair_scan(repo, setup, "range", base=base, head=head), "INVALID_RANGE"
    )


@pytest.mark.parametrize("kind", ["tag", "tree", "blob"])
@pytest.mark.parametrize(
    "selector",
    [
        "policy-candidate",
        "policy-index",
        "policy-tree",
        "policy-range",
        "ref",
        "base",
        "head",
    ],
)
def test_review_repair_noncommit_ids_rejected_at_every_selector(
    repo: Repository, kind: str, selector: str
):
    if kind == "tag":
        repo.git("tag", "-a", "synthetic-tag", "-m", "synthetic tag")
        object_id = repo.git("rev-parse", "synthetic-tag^{tag}")
    elif kind == "tree":
        object_id = repo.git("rev-parse", "HEAD^{tree}")
    else:
        object_id = repo.git("rev-parse", "HEAD:" + BASELINE_PATH)
    _input_expected_error(_input_select(repo, selector, object_id), "INVALID_REF")


@pytest.mark.parametrize(
    "probe,error",
    [
        ("format-failure", "INVALID_REPOSITORY"),
        ("commit-failure", "INVALID_REF"),
        ("shallow-failure", "INVALID_RANGE"),
        ("graft-failure", "INVALID_RANGE"),
        ("shallow-unknown", "INVALID_RANGE"),
        ("graft-relative", "INVALID_RANGE"),
        ("graft-empty", "INVALID_RANGE"),
        ("graft-nul", "INVALID_RANGE"),
        ("graft-unterminated", "INVALID_RANGE"),
    ],
)
def test_review_repair_git_metadata_error_branches(
    repo: Repository, probe: str, error: str
):
    condition = (
        "any(a.startswith('--show-object-format') for a in args)"
        if probe.startswith("format")
        else "'--verify' in args"
        if probe.startswith("commit")
        else "'--is-shallow-repository' in args"
        if probe.startswith("shallow")
        else "'--git-common-dir' in args"
    )
    raw = (
        b"unknown\n"
        if probe == "shallow-unknown"
        else b"relative\n"
        if probe == "graft-relative"
        else b"\n"
        if probe == "graft-empty"
        else b"/tmp/synthetic\0\n"
        if probe == "graft-nul"
        else b"/tmp/synthetic"
    )
    effect = (
        "raise m.ScanFailure('GIT_FAILURE')"
        if probe.endswith("failure")
        else "return m.GitResult(0," + repr(raw) + ")"
    )
    setup = (
        "original=m._git_command\n"
        "def inject(root,args,**kwargs):\n"
        "    if " + condition + ": " + effect + "\n"
        "    return original(root,args,**kwargs)\n"
        "m._git_command=inject\n"
    )
    _input_expected_error(
        _repair_scan(repo, setup, "range", base=repo.base, head=repo.base), error
    )


def test_review_repair_leaf_notimplemented_branch_and_inner_guard(repo: Repository):
    repo.put("root.txt", "ordinary text\n")
    repo.commit()
    repo.git("rm", "--cached", BASELINE_PATH)
    setup = (
        "real_open=os.open\n"
        "def leaf_unsupported(*args,**kwargs):\n"
        "    if 'dir_fd' in kwargs and args[0]=='root.txt': raise NotImplementedError('synthetic')\n"
        "    return real_open(*args,**kwargs)\n"
        "os.open=leaf_unsupported;os.supports_dir_fd=set(os.supports_dir_fd)|{leaf_unsupported}\n"
    )
    _input_expected_error(_repair_scan(repo, setup), "UNSUPPORTED_ENTRY")
    direct = (
        "del os.O_NOFOLLOW\n"
        "try: m._read_candidate_file(pathlib.Path(sys.argv[3]),'root.txt')\n"
        "except m.ScanFailure as e:\n"
        "    assert e.code=='UNSUPPORTED_ENTRY'\n"
        "    m._emit(m._report((),e.code));raise SystemExit(2)\n"
        "raise AssertionError('inner platform guard was bypassed')\n"
    )
    _input_expected_error(_repair_scan(repo, direct), "UNSUPPORTED_ENTRY")
    outer = (
        "del os.O_NOFOLLOW\n"
        "def forbidden(*args,**kwargs): raise AssertionError('tracked opener reached without outer guard')\n"
        "m._read_candidate_file=forbidden\n"
    )
    _input_expected_error(_repair_scan(repo, outer), "UNSUPPORTED_ENTRY")


def test_review_repair_git_deadline_survives_pipe_eof(repo: Repository, tmp_path: Path):
    import signal

    real_git = shutil.which("git")
    assert real_git is not None
    directory = tmp_path / "timeout-bin"
    directory.mkdir()
    wrapper = directory / "git"
    marker = directory / "probe-reached"
    wrapper.write_text(
        "#!" + sys.executable + "\nimport os,sys,time,pathlib\n"
        "if any(a.startswith('--show-object-format') for a in sys.argv[1:]):\n"
        "    pathlib.Path(" + repr(str(marker)) + ").write_text('reached')\n"
        "    os.close(1);os.close(2);time.sleep(30);sys.exit(0)\n"
        "os.execv(" + repr(real_git) + ",['git',*sys.argv[1:]])\n"
    )
    wrapper.chmod(0o700)
    script = (
        "import importlib.util,pathlib,sys\nsys.dont_write_bytecode=True\n"
        "s=importlib.util.spec_from_file_location('synthetic_timeout',sys.argv[1])\n"
        "m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m)\n"
        "m.GIT_TIMEOUT_SECONDS=1.5\n"
        "try: m._repository_object_id_length(pathlib.Path(sys.argv[2]))\n"
        "except m.ScanFailure as error:\n"
        "    m._emit(m._report((),error.code));raise SystemExit(2)\n"
        "raise SystemExit(0)\n"
    )
    env = dict(os.environ, PATH=str(directory) + os.pathsep + os.environ["PATH"])
    child = subprocess.Popen(
        [sys.executable, "-I", "-c", script, str(SCANNER), str(repo.path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        start_new_session=True,
    )
    timed_out = False
    try:
        out, err = child.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        timed_out = True
        os.killpg(child.pid, signal.SIGTERM)
        try:
            out, err = child.communicate(timeout=3)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            out, err = child.communicate(timeout=3)
    finally:
        if child.poll() is None:
            os.killpg(child.pid, signal.SIGKILL)
            child.wait(timeout=3)
    assert marker.read_text() == "reached", "timeout setup failed before intended probe"
    assert (
        not timed_out
    ), "Git child escaped deadline after EOF; owned group terminated/reaped"
    assert not err and child.returncode == 2
    assert json.loads(out) == {
        "status": "error",
        "findings": [],
        "errors": ["INVALID_REPOSITORY"],
    }


# S01-ALL-GAPS-1: original tests above are an immutable byte-for-byte prefix.
def _all_gaps_module():
    import importlib.util

    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("synthetic_all_gaps", SCANNER)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _all_gaps_mutation(function: str, target: str, replacement: str) -> str:
    """Change one named defense in memory, never production source bytes."""
    return (
        "import inspect,textwrap\n"
        f"source=textwrap.dedent(inspect.getsource(m.{function}))\n"
        f"target={target!r}\nassert source.count(target)==1,'mutation target drift'\n"
        f"exec(source.replace(target,{replacement!r},1),m.__dict__)\n"
    )


def _all_gaps_linked(repo: Repository, tmp_path: Path):
    repo.put("config.txt", 'password="' + CANARY + '"\n')
    head = repo.commit()
    linked, alternate = tmp_path / "linked", tmp_path / "alternate"
    repo.git("worktree", "add", "-q", "-b", "original-route", str(linked), head)
    repo.git(
        "worktree", "add", "-q", "-b", "alternate-route", str(alternate), repo.base
    )
    from types import SimpleNamespace

    return SimpleNamespace(path=linked, policy=repo.policy), alternate


@pytest.mark.parametrize("replacement", [False, True], ids=["in-place", "replace"])
def test_all_gaps_linked_gitdir_aba(
    repo: Repository, tmp_path: Path, replacement: bool
):
    linked, alternate = _all_gaps_linked(repo, tmp_path)
    initial = (linked.path / ".git").read_bytes()
    other = (alternate / ".git").read_bytes()
    assert invoke(linked.path, linked.policy, "candidate")[0] == 1
    marker = tmp_path / "reached"
    marker.write_text("0")
    action = (
        "        p.rename(root/'saved-carrier')\n" "        p.write_bytes(other)\n"
        if replacement
        else "        with p.open('r+b') as f: f.write(other);f.truncate()\n"
    )
    restore = (
        "        p.unlink();(root/'saved-carrier').rename(p)\n"
        if replacement
        else "        with p.open('r+b') as f: f.write(saved);f.truncate()\n"
    )
    setup = (
        "original=m._git_command\ncount=0\n"
        f"other={other!r}\n"
        "def interleave(root,args,**kwargs):\n"
        "    global count\n"
        "    if 'ls-files' not in args: return original(root,args,**kwargs)\n"
        "    count+=1;p=root/'.git';saved=p.read_bytes()\n"
        "    try:\n" + action + "        return original(root,args,**kwargs)\n"
        "    finally:\n"
        + restore
        + f"        pathlib.Path({str(marker)!r}).write_text(str(count))\n"
        "m._git_command=interleave\n"
    )
    result = _repair_scan(linked, setup)
    assert int(marker.read_text()) >= 1, "no real listing/swap/restore completed"
    assert (linked.path / ".git").read_bytes() == initial
    _input_expected_error(result, "UNSUPPORTED_ENTRY")


@pytest.mark.parametrize("carrier", ["gitfile", "commondir"])
def test_all_gaps_carrier_discovery_aba(repo: Repository, tmp_path: Path, carrier: str):
    linked, _ = _all_gaps_linked(repo, tmp_path)
    git_dir = Path(repo.git("-C", str(linked.path), "rev-parse", "--absolute-git-dir"))
    target = linked.path / ".git" if carrier == "gitfile" else git_dir / "commondir"
    original_bytes = target.read_bytes()
    marker = tmp_path / "carrier-reached"
    marker.write_text("not-reached")
    setup = (
        "read=m._read_fd_limited\nchanged=False\n"
        f"target=pathlib.Path({str(target)!r})\n"
        "identity=(target.stat().st_dev,target.stat().st_ino)\n"
        "def interleave(fd):\n"
        "    global changed\n"
        "    value=os.fstat(fd)\n"
        "    if not changed and (value.st_dev,value.st_ino)==identity:\n"
        "        changed=True;saved=target.read_bytes()\n"
        "        with target.open('r+b') as f: f.write(saved+b'\\n');f.truncate()\n"
        "        with target.open('r+b') as f: f.write(saved);f.truncate()\n"
        f"        pathlib.Path({str(marker)!r}).write_text('changed-restored')\n"
        "    return read(fd)\n"
        "m._read_fd_limited=interleave\n"
    )
    result = _repair_scan(linked, setup)
    assert marker.read_text() == "changed-restored", "carrier was not descriptor-read"
    assert target.read_bytes() == original_bytes
    _input_expected_error(result, "UNSUPPORTED_ENTRY")


@pytest.mark.parametrize("carrier", ["commondir", "index"])
def test_all_gaps_parent_before_absence_detects_create_remove_aba(
    repo: Repository, tmp_path: Path, carrier: str
):
    target = repo.path / ".git" / carrier
    if carrier == "index":
        target.unlink()
    assert not target.exists()
    marker = tmp_path / "absence-reached"
    marker.write_text("not-reached")
    setup = (
        "real_open=os.open\nchanged=False\n"
        "def interleave(path,*args,**kwargs):\n"
        "    global changed\n"
        "    try: return real_open(path,*args,**kwargs)\n"
        "    except FileNotFoundError:\n"
        f"        if not changed and pathlib.Path(path).name=={carrier!r}:\n"
        "            changed=True\n"
        f"            p=pathlib.Path({str(target)!r});p.write_bytes(b'');p.unlink()\n"
        f"            pathlib.Path({str(marker)!r}).write_text('created-removed')\n"
        "        raise\n"
        "os.open=interleave;os.supports_dir_fd=set(os.supports_dir_fd)|{interleave}\n"
    )
    result = _repair_scan(repo, setup)
    assert marker.read_text() == "created-removed", "absence acquisition not reached"
    _input_expected_error(result, "UNSUPPORTED_ENTRY")


def test_all_gaps_admin_ancestor_swap_aba(repo: Repository, tmp_path: Path):
    repo.put("config.txt", 'password="' + CANARY + '"\n')
    repo.commit()
    container = tmp_path / "original-container"
    container.mkdir()
    admin = container / "admin"
    (repo.path / ".git").rename(admin)
    (repo.path / ".git").write_text("gitdir: " + str(admin) + "\n")
    alternate = tmp_path / "alternate-container"
    shutil.copytree(container, alternate)
    repo.git("--git-dir=" + str(alternate / "admin"), "read-tree", repo.base)
    assert repo.scan()[0] == 1
    marker = tmp_path / "ancestor-reached"
    marker.write_text("0")
    setup = (
        "original=m._git_command\ncount=0\n"
        f"container=pathlib.Path({str(container)!r})\n"
        f"alternate=pathlib.Path({str(alternate)!r})\n"
        f"saved=pathlib.Path({str(tmp_path / 'saved-container')!r})\n"
        "def interleave(root,args,**kwargs):\n"
        "    global count\n"
        "    if 'ls-files' not in args: return original(root,args,**kwargs)\n"
        "    count+=1;container.rename(saved);alternate.rename(container)\n"
        "    try: return original(root,args,**kwargs)\n"
        "    finally:\n"
        "        container.rename(alternate);saved.rename(container)\n"
        f"        pathlib.Path({str(marker)!r}).write_text(str(count))\n"
        "m._git_command=interleave\n"
    )
    result = _repair_scan(repo, setup)
    assert int(marker.read_text()) >= 1
    assert admin.is_dir() and (alternate / "admin").is_dir()
    _input_expected_error(result, "UNSUPPORTED_ENTRY")


@pytest.mark.parametrize(
    "mutant", [False, True], ids=["bound-control", "unbound-mutant"]
)
def test_all_gaps_early_candidate_binding(
    repo: Repository, tmp_path: Path, mutant: bool
):
    repo.put("config.txt", 'password="' + CANARY + '"\n')
    repo.commit()
    marker = tmp_path / "binding-observations"
    marker.write_text("[]")
    setup = (
        "real_open=os.open;opened=[];observations=[]\n"
        "def observe_open(path,*args,**kwargs):\n"
        "    opened.append(pathlib.Path(path).name)\n"
        "    return real_open(path,*args,**kwargs)\n"
        "os.open=observe_open;os.supports_dir_fd=set(os.supports_dir_fd)|{observe_open}\n"
        "real_popen=m.subprocess.Popen\n"
        "def observe_popen(argv,*args,**kwargs):\n"
        "    env=kwargs['env'];root=pathlib.Path(sys.argv[3]).resolve();admin=root/'.git'\n"
        "    required=['--git-dir='+str(admin),'--work-tree='+str(root)]\n"
        "    observations.append({'argv_bound':all(x in argv for x in required),\n"
        "        'env_bound':env.get('GIT_COMMON_DIR')==str(admin) and env.get('GIT_INDEX_FILE')==str(admin/'index'),\n"
        "        'early_carriers':'.git' in opened and 'commondir' in opened,\n"
        "        'poison_stripped':'GIT_OBJECT_DIRECTORY' not in env,\n"
        "        'commit_graph':'core.commitGraph=false' in argv})\n"
        f"    pathlib.Path({str(marker)!r}).write_text(m.json.dumps(observations))\n"
        "    return real_popen(argv,*args,**kwargs)\n"
        "m.subprocess.Popen=observe_popen\n"
        "os.environ['GIT_DIR']='/nonexistent-poison';os.environ['GIT_COMMON_DIR']='/nonexistent-poison'\n"
        "os.environ['GIT_INDEX_FILE']='/nonexistent-poison';os.environ['GIT_OBJECT_DIRECTORY']='/nonexistent-poison'\n"
    )
    if mutant:
        setup += (
            "real_command=m._git_command\n"
            "def drop_binding(root,args,**kwargs):\n"
            "    kwargs.pop('candidate_binding',None)\n"
            "    return real_command(root,args,**kwargs)\n"
            "m._git_command=drop_binding\n"
        )
    result = _repair_scan(repo, setup)
    observations = json.loads(marker.read_text())
    assert observations and all(o["poison_stripped"] for o in observations)
    if mutant:
        assert any(not o["argv_bound"] or not o["env_bound"] for o in observations)
    else:
        assert all(all(o.values()) for o in observations), observations
        assert result[0] == 1 and has(result[1], "literal-assignment", "config.txt")


@pytest.mark.parametrize("flags", ["skip-worktree", "assume-unchanged"])
def test_all_gaps_late_flag_delete_restore_is_fully_reached(
    repo: Repository, tmp_path: Path, flags: str
):
    content = 'password="' + CANARY + '"\n'
    repo.put("config.txt", content)
    repo.commit()
    marker = tmp_path / "late-phases"
    marker.write_text("[]")
    setup = (
        "read=m._read_candidate_file\nphases=[]\n"
        "def interleave(root,path):\n"
        "    if path!='config.txt': return read(root,path)\n"
        f"    m._git_command(root,['update-index','--{flags}',path]);phases.append('flag')\n"
        "    (root/path).unlink();phases.append('delete')\n"
        "    data=read(root,path);assert data is None;phases.append('read-none')\n"
        f"    (root/path).write_text({content!r});phases.append('restore-file')\n"
        f"    m._git_command(root,['update-index','--no-{flags}',path]);phases.append('restore-flag')\n"
        f"    pathlib.Path({str(marker)!r}).write_text(m.json.dumps(phases))\n"
        "    return data\n"
        "m._read_candidate_file=interleave\n"
    )
    result = _repair_scan(repo, setup)
    assert json.loads(marker.read_text()) == [
        "flag",
        "delete",
        "read-none",
        "restore-file",
        "restore-flag",
    ]
    _input_expected_error(result, "UNSUPPORTED_ENTRY")


@pytest.mark.parametrize("mutant", [False, True], ids=["control", "comparison-mutant"])
def test_all_gaps_final_entries_comparison(
    repo: Repository, tmp_path: Path, mutant: bool
):
    repo.put("ordinary.txt", "ordinary text\n")
    repo.commit()
    marker = tmp_path / "final-entries"
    marker.write_text("0")
    setup = (
        "original=m._git_command\ncount=0\n"
        "def inject(root,args,**kwargs):\n"
        "    global count\n"
        "    result=original(root,args,**kwargs)\n"
        "    if 'ls-files' in args:\n"
        "        count+=1\n"
        "        if count==2:\n"
        "            rows=result.stdout.split(b'\\0');row=rows[0]\n"
        "            metadata,path=row.split(b'\\t',1);fields=metadata.split(b' ')\n"
        "            fields[2]=b'a'*len(fields[2]);rows[0]=b' '.join(fields)+b'\\t'+path\n"
        f"            pathlib.Path({str(marker)!r}).write_text('2')\n"
        "            return m.GitResult(0,b'\\0'.join(rows))\n"
        "    return result\n"
        "m._git_command=inject\n"
    )
    if mutant:
        setup += (
            "import ast,inspect,textwrap\n"
            "tree=ast.parse(textwrap.dedent(inspect.getsource(m._read_candidate_snapshot)))\n"
            "class RemoveComparison(ast.NodeTransformer):\n"
            "    count=0\n"
            "    def visit_Compare(self,node):\n"
            "        if isinstance(node.left,ast.Name) and node.left.id=='final_entries':\n"
            "            self.count+=1;return ast.copy_location(ast.Constant(False),node)\n"
            "        return self.generic_visit(node)\n"
            "change=RemoveComparison();tree=change.visit(tree);assert change.count==1\n"
            "exec(compile(ast.fix_missing_locations(tree),'<semantic-mutant>','exec'),m.__dict__)\n"
        )
    result = _repair_scan(repo, setup)
    assert marker.read_text() == "2"
    if mutant:
        assert result[0] == 0
    else:
        _input_expected_error(result, "UNSUPPORTED_ENTRY")


@pytest.mark.parametrize("mutant", [False, True], ids=["control", "identity-mutant"])
def test_all_gaps_final_binding_comparison(
    repo: Repository, tmp_path: Path, mutant: bool
):
    marker = tmp_path / "final-binding"
    marker.write_text("0")
    setup = (
        "original=m._git_command\nlistings=0\n"
        "def inject(root,args,**kwargs):\n"
        "    global listings\n"
        "    if 'ls-files' in args: listings+=1\n"
        "    if listings==2 and '--git-dir' in args:\n"
        f"        pathlib.Path({str(marker)!r}).write_text('reached')\n"
        "        return m.GitResult(0,os.fsencode(str(root/'different-admin'))+b'\\n')\n"
        "    return original(root,args,**kwargs)\n"
        "m._git_command=inject\n"
    )
    if mutant:
        setup += (
            "import ast,inspect,textwrap\n"
            "tree=ast.parse(textwrap.dedent(inspect.getsource(m._read_candidate_snapshot)))\n"
            "class RemoveIdentity(ast.NodeTransformer):\n"
            "    count=0\n"
            "    def visit_Compare(self,node):\n"
            "        left=node.left\n"
            "        if isinstance(left,ast.Call) and isinstance(left.func,ast.Name) and left.func.id=='_candidate_index_path':\n"
            "            self.count+=1;return ast.copy_location(ast.Constant(False),node)\n"
            "        return self.generic_visit(node)\n"
            "change=RemoveIdentity();tree=change.visit(tree);assert change.count==1\n"
            "exec(compile(ast.fix_missing_locations(tree),'<identity-mutant>','exec'),m.__dict__)\n"
        )
    result = _repair_scan(repo, setup)
    if mutant:
        assert result[0] == 0
    else:
        assert marker.read_text() == "reached"
        _input_expected_error(result, "UNSUPPORTED_ENTRY")


@pytest.mark.parametrize("read_error", [False, True], ids=["success", "read-error"])
@pytest.mark.parametrize("mutant", [False, True], ids=["control", "fstat-mutant"])
def test_all_gaps_reader_fstat_success_and_error(
    repo: Repository, read_error: bool, mutant: bool
):
    module = _all_gaps_module()
    repo.put("ordinary.txt", "ordinary text\n")
    read = module._read_fd_limited
    reached = []

    def interleave(fd):
        p = repo.path / "ordinary.txt"
        before = p.stat()
        p.write_bytes(b"x" * before.st_size)
        os.utime(p, ns=(before.st_atime_ns, before.st_mtime_ns))
        reached.append("modified-fixed-size-restored-mtime")
        if read_error:
            raise module.ScanFailure("INPUT_UNREADABLE")
        return read(fd)

    module._read_fd_limited = interleave
    if mutant:
        # Only remove the seven-field stability comparison; retain reads/errors.
        module._candidate_stat_state = lambda value: ()
    try:
        module._read_candidate_file(repo.path, "ordinary.txt")
        error = None
    except module.ScanFailure as failure:
        error = failure.code
    assert reached == ["modified-fixed-size-restored-mtime"]
    assert (
        error == ("INPUT_UNREADABLE" if read_error else None)
        if mutant
        else error == "UNSUPPORTED_ENTRY"
    )


@pytest.mark.parametrize("split", [False, True], ids=["ordinary", "split"])
def test_all_gaps_linked_index_pin_identity(
    repo: Repository, tmp_path: Path, split: bool
):
    linked, _ = _all_gaps_linked(repo, tmp_path)
    repo.git("read-tree", repo.base)
    if split:
        repo.git("-C", str(linked.path), "update-index", "--split-index")
    admin = Path(repo.git("-C", str(linked.path), "rev-parse", "--absolute-git-dir"))
    marker = tmp_path / "pin-identity"
    marker.write_text("[]")
    setup = (
        "original=m._pin_candidate_index\n"
        "def observe(path,*args,**kwargs):\n"
        "    pin=original(path,*args,**kwargs)\n"
        f"    expected=pathlib.Path({str(admin / 'index')!r}).stat()\n"
        "    actual=os.fstat(pin.descriptor)\n"
        f"    pathlib.Path({str(marker)!r}).write_text(m.json.dumps([str(path),actual.st_ino,expected.st_ino]))\n"
        "    return pin\n"
        "m._pin_candidate_index=observe\n"
    )
    result = _repair_scan(linked, setup)
    selected, actual_inode, expected_inode = json.loads(marker.read_text())
    assert Path(selected) == admin / "index" and actual_inode == expected_inode
    assert result[0] == 1 and has(result[1], "literal-assignment", "config.txt")
    changed = setup + (
        "listing=m._index_entries\n"
        "def replace(root,**kwargs):\n"
        "    entries=listing(root,**kwargs)\n"
        "    m._git_command(root,['update-index','--skip-worktree','config.txt'])\n"
        "    return entries\n"
        "m._index_entries=replace\n"
    )
    _input_expected_error(_repair_scan(linked, changed), "UNSUPPORTED_ENTRY")


@pytest.mark.parametrize(
    "kind", ["symlink", "dangling", "fifo", "directory", "missing"]
)
def test_all_gaps_index_pin_states(repo: Repository, tmp_path: Path, kind: str):
    path = repo.path / ".git/index"
    saved = tmp_path / "saved-index"
    shutil.copy2(path, saved)
    path.unlink()
    if kind == "symlink":
        path.symlink_to(saved)
    elif kind == "dangling":
        path.symlink_to(tmp_path / "absent")
    elif kind == "fifo":
        os.mkfifo(path)
    elif kind == "directory":
        path.mkdir()
    if kind == "missing":
        assert repo.scan() == (0, {"status": "clean", "findings": [], "errors": []})
    else:
        _input_expected_error(repo.scan(), "UNSUPPORTED_ENTRY")


def test_all_gaps_initial_index_eacces_is_unreadable(repo: Repository, tmp_path: Path):
    marker = tmp_path / "eacces-reached"
    marker.write_text("not-reached")
    setup = (
        "import errno\nreal_open=os.open\n"
        "def denied(path,*args,**kwargs):\n"
        "    if pathlib.Path(path).name=='index':\n"
        f"        pathlib.Path({str(marker)!r}).write_text('denied')\n"
        "        raise PermissionError(errno.EACCES,'synthetic')\n"
        "    return real_open(path,*args,**kwargs)\n"
        "os.open=denied;os.supports_dir_fd=set(os.supports_dir_fd)|{denied}\n"
    )
    _input_expected_error(_repair_scan(repo, setup), "INPUT_UNREADABLE")
    assert marker.read_text() == "denied"


@pytest.mark.parametrize("action", ["delete", "replace", "same-bytes", "symlink"])
def test_all_gaps_post_pin_index_changes_are_drift(
    repo: Repository, tmp_path: Path, action: str
):
    marker = tmp_path / "index-change"
    marker.write_text("not-reached")
    body = {
        "delete": "p.unlink()",
        "replace": "p.rename(root/'.git/saved-index');p.write_bytes(data)",
        "same-bytes": "p.write_bytes(data)",
        "symlink": "p.rename(root/'.git/saved-index');p.symlink_to(root/'.git/saved-index')",
    }[action]
    setup = (
        "original=m._index_entries\n"
        "def interleave(root,**kwargs):\n"
        "    entries=original(root,**kwargs);p=root/'.git/index';data=p.read_bytes()\n"
        f"    {body}\n"
        f"    pathlib.Path({str(marker)!r}).write_text('changed')\n"
        "    return entries\n"
        "m._index_entries=interleave\n"
    )
    result = _repair_scan(repo, setup)
    assert marker.read_text() == "changed"
    _input_expected_error(result, "UNSUPPORTED_ENTRY")


@pytest.mark.parametrize("object_format", ["sha1", "sha256"])
@pytest.mark.parametrize("linked", [False, True], ids=["gitfile", "commondir"])
@pytest.mark.parametrize("absolute", [False, True], ids=["relative", "absolute"])
@pytest.mark.parametrize("terminator", [b"\n", b"\r\n", b"", b"\n\n"])
def test_all_gaps_carrier_layout_controls(
    tmp_path: Path, object_format: str, linked: bool, absolute: bool, terminator: bytes
):
    repo = Repository(tmp_path / "repo", object_format=object_format)
    repo.put("config.txt", 'password="' + CANARY + '"\n')
    head = repo.commit()
    if linked:
        root = tmp_path / "linked space\nembedded"
        repo.git("worktree", "add", "-q", "-b", "layout", str(root), head)
        admin = Path(repo.git("-C", str(root), "rev-parse", "--absolute-git-dir"))
        carrier = admin / "commondir"
        target = repo.path / ".git"
        text = os.fsencode(str(target) if absolute else os.path.relpath(target, admin))
    else:
        root = repo.path
        admin = tmp_path / "admin space\nembedded"
        (root / ".git").rename(admin)
        carrier = root / ".git"
        text = b"gitdir: " + os.fsencode(
            str(admin) if absolute else os.path.relpath(admin, root)
        )
    carrier.write_bytes(text + terminator)
    code, report = invoke(root, repo.policy, "candidate")
    assert code == 1 and has(report, "literal-assignment", "config.txt")


@pytest.mark.parametrize("carrier", ["gitfile", "commondir"])
@pytest.mark.parametrize("bad", ["nul", "empty", "symlink", "fifo", "directory"])
def test_all_gaps_unsupported_carriers_are_controlled(
    repo: Repository, tmp_path: Path, carrier: str, bad: str
):
    linked, _ = _all_gaps_linked(repo, tmp_path)
    admin = Path(repo.git("-C", str(linked.path), "rev-parse", "--absolute-git-dir"))
    target = linked.path / ".git" if carrier == "gitfile" else admin / "commondir"
    original = target.read_bytes()
    target.unlink()
    if bad == "nul":
        target.write_bytes(original.rstrip(b"\n") + b"\0ignored\n")
    elif bad == "empty":
        target.write_bytes(b"gitdir: \n" if carrier == "gitfile" else b"\n")
    elif bad == "symlink":
        saved = tmp_path / "saved-carrier"
        saved.write_bytes(original)
        target.symlink_to(saved)
    elif bad == "fifo":
        os.mkfifo(target)
    else:
        target.mkdir()
    error = "INVALID_REPOSITORY" if bad in {"nul", "empty"} else "UNSUPPORTED_ENTRY"
    # A .git directory is a normal carrier type but this empty one is not a repo.
    if bad == "directory" and carrier == "gitfile":
        error = "INVALID_REPOSITORY"
    _input_expected_error(_repair_scan(linked, ""), error)


def test_all_gaps_gitfile_wrong_prefix_is_invalid(repo: Repository, tmp_path: Path):
    linked, _ = _all_gaps_linked(repo, tmp_path)
    (linked.path / ".git").write_text("gitdir:" + str(repo.path / ".git") + "\n")
    _input_expected_error(_repair_scan(linked, ""), "INVALID_REPOSITORY")


def test_all_gaps_canonical_alias_and_relative_root_controls(
    repo: Repository, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repo.put("config.txt", 'password="' + CANARY + '"\n')
    repo.commit()
    alias = tmp_path / "alias"
    alias.symlink_to(repo.path, target_is_directory=True)
    assert invoke(alias, repo.policy, "candidate")[0] == 1
    monkeypatch.chdir(tmp_path)
    assert invoke(Path("repo"), repo.policy, "candidate")[0] == 1


@pytest.mark.parametrize(
    "phase", ["success", "acquire", "verify", "policy-error", "unsupported"]
)
def test_all_gaps_routing_descriptors_are_closed(
    repo: Repository, tmp_path: Path, phase: str
):
    marker = tmp_path / "descriptors"
    marker.write_text("{}")
    if phase == "unsupported":
        index = repo.path / ".git/index"
        index.unlink()
        os.mkfifo(index)
    setup = (
        "real_open=os.open;real_close=os.close;active=set();opened_count=0;closing=[]\n"
        "def track_open(path,*args,**kwargs):\n"
        "    global opened_count\n"
        + (
            "    if pathlib.Path(path).name=='commondir': raise PermissionError('synthetic')\n"
            if phase == "acquire"
            else ""
        )
        + "    fd=real_open(path,*args,**kwargs);active.add(fd);opened_count+=1;return fd\n"
        "def track_close(fd):\n"
        "    active.discard(fd);closing.append(fd);return real_close(fd)\n"
        "os.open=track_open;os.close=track_close;os.supports_dir_fd=set(os.supports_dir_fd)|{track_open}\n"
    )
    if phase in {"verify", "policy-error"}:
        setup += (
            "original=m._load_policy\n"
            "def interleave(root,*args,**kwargs):\n"
            "    result=original(root,*args,**kwargs)\n"
            "    p=root/'.git/namespace-change';p.write_bytes(b'');p.unlink()\n"
            + (
                "    raise m.ScanFailure('INVALID_POLICY')\n"
                if phase == "policy-error"
                else "    return result\n"
            )
            + "m._load_policy=interleave\n"
        )
    setup += (
        "entry=m.main\n"
        "def observe(argv):\n"
        "    result=entry(argv)\n"
        f"    pathlib.Path({str(marker)!r}).write_text(m.json.dumps({{'active':sorted(active),'opened':opened_count,'closed':len(closing)}}))\n"
        "    return result\n"
        "m.main=observe\n"
    )
    result = _repair_scan(repo, setup)
    state = json.loads(marker.read_text())
    assert state["opened"] > 0 and state["active"] == []
    if phase in {"verify", "policy-error", "unsupported"}:
        _input_expected_error(result, "UNSUPPORTED_ENTRY")
    elif phase == "acquire":
        _input_expected_error(result, "INPUT_UNREADABLE")
    else:
        assert result[0] == 0


@pytest.mark.parametrize("mutant", ["none", "kill", "wait", "both"])
def test_all_gaps_git_timeout_kills_and_reaps_direct_child(
    repo: Repository, tmp_path: Path, mutant: str
):
    directory = tmp_path / "timeout-bin"
    directory.mkdir()
    marker = directory / "entered"
    marker.write_text("not-reached")
    wrapper = directory / "git"
    wrapper.write_text(
        "#!" + sys.executable + "\nimport os,pathlib,time\n"
        f"pathlib.Path({str(marker)!r}).write_text('reached')\n"
        "os.close(1);os.close(2);time.sleep(30)\n"
    )
    wrapper.chmod(0o700)
    mutation = ""
    if mutant != "none":
        mutation = (
            "import inspect,textwrap\n"
            "source=textwrap.dedent(inspect.getsource(m._git_command))\n"
        )
        if mutant in {"kill", "both"}:
            mutation += (
                "assert 'process.kill()' in source\n"
                "source=source.replace('process.kill()','None')\n"
            )
        if mutant in {"wait", "both"}:
            mutation += (
                "assert 'process.wait()' in source and 'process.wait(timeout=remaining)' in source\n"
                "source=source.replace('process.wait()','None').replace('process.wait(timeout=remaining)','None')\n"
            )
        mutation += "exec(source,m.__dict__)\n"
    script = (
        "import importlib.util,json,os,pathlib,sys,threading\n"
        "sys.dont_write_bytecode=True\n"
        "s=importlib.util.spec_from_file_location('timeout_oracle',sys.argv[1])\n"
        "m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m)\n"
        + mutation
        + "real=m.subprocess.Popen;children=[];events=[];watchdog=[]\n"
        "class Observed(real):\n"
        "    def __init__(self,*args,**kwargs):\n"
        "        super().__init__(*args,**kwargs);children.append(self)\n"
        "    def kill(self):\n"
        "        events.append('scanner-kill');return super().kill()\n"
        "    def wait(self,*args,**kwargs):\n"
        "        result=super().wait(*args,**kwargs);events.append('scanner-wait-completed');return result\n"
        "m.subprocess.Popen=Observed;m.GIT_TIMEOUT_SECONDS=1.5\n"
        "def emergency_cleanup():\n"
        "    watchdog.append('deadline-escape')\n"
        "    for child in children:\n"
        "        try: os.kill(child.pid,9)\n"
        "        except ProcessLookupError: pass\n"
        "timer=threading.Timer(4,emergency_cleanup);timer.start()\n"
        "try:\n"
        "    try: m._repository_object_id_length(pathlib.Path(sys.argv[2]));error=None\n"
        "    except m.ScanFailure as failure: error=failure.code\n"
        "    assert len(children)==1;child=children[0]\n"
        "    recorded_returncode=child.returncode\n"
        "    # No observer poll/wait before this decision. waitpid returning status is a failure.\n"
        "    try: waitpid_result=os.waitpid(child.pid,os.WNOHANG);already_reaped=False\n"
        "    except ChildProcessError: waitpid_result=None;already_reaped=True\n"
        "    observation={'error':error,'events':list(events),'returncode':recorded_returncode,\n"
        "        'already_reaped':already_reaped,'watchdog':list(watchdog)}\n"
        "    print(json.dumps(observation))\n"
        "finally:\n"
        "    timer.cancel();timer.join(timeout=1)\n"
        "    for child in children:\n"
        "        try: os.kill(child.pid,9)\n"
        "        except ProcessLookupError: pass\n"
        "        real.wait(child,timeout=2)\n"
    )
    environment = dict(
        os.environ, PATH=str(directory) + os.pathsep + os.environ["PATH"]
    )
    result = subprocess.run(
        [sys.executable, "-I", "-c", script, str(SCANNER), str(repo.path)],
        env=environment,
        capture_output=True,
        timeout=9,
    )
    assert not result.stderr and result.returncode == 0
    assert marker.read_text() == "reached"
    observation = json.loads(result.stdout)
    qualified = (
        observation["error"] == "INVALID_REPOSITORY"
        and observation["returncode"] == -9
        and observation["already_reaped"]
        and not observation["watchdog"]
        and "scanner-kill" in observation["events"]
        and "scanner-wait-completed" in observation["events"]
    )
    assert qualified == (mutant == "none"), observation


@pytest.mark.parametrize("object_format", ["sha1", "sha256"])
@pytest.mark.parametrize(
    "shape",
    [
        "listed-commit",
        "listed-parent",
        "raw-parent",
        "second-tree",
        "late-parent",
        "delimiter",
    ],
)
def test_all_gaps_range_guards_through_main(
    tmp_path: Path, object_format: str, shape: str
):
    repo = Repository(tmp_path / "repo", object_format=object_format)
    repo.put("ordinary.txt", "ordinary text\n")
    head = repo.commit()
    assert repo.scan("range", base=repo.base, head=head)[0] == 0
    setup = (
        "original=m._git_command\n"
        "def inject(root,args,**kwargs):\n"
        "    result=original(root,args,**kwargs)\n"
        + (
            "    if 'rev-list' in args: return m.GitResult(0,result.stdout+result.stdout)\n"
            if shape == "listed-commit"
            else "    if 'rev-list' in args:\n"
            "        row=result.stdout.rstrip(b'\\n');parent=row.split()[-1]\n"
            "        return m.GitResult(0,row+b' '+parent+b'\\n')\n"
            if shape == "listed-parent"
            else "    if 'cat-file' in args and 'commit' in args and args[-1]=="
            + repr(head)
            + ":\n"
            + (
                "        row=next(x for x in result.stdout.split(b'\\n') if x.startswith(b'parent '))\n"
                "        raw=result.stdout.replace(row,row+b'\\n'+row,1)\n"
                if shape == "raw-parent"
                else "        row=result.stdout.split(b'\\n')[0]\n"
                "        raw=result.stdout.replace(row,row+b'\\n'+row,1)\n"
                if shape == "second-tree"
                else "        rows=result.stdout.split(b'\\n');row=next(x for x in rows if x.startswith(b'parent '))\n"
                "        rows.remove(row);at=next(i for i,x in enumerate(rows) if x.startswith(b'author '))\n"
                "        rows.insert(at+1,row);raw=b'\\n'.join(rows)\n"
                if shape == "late-parent"
                else "        raw=result.stdout.replace(b'parent ',b'parent\\t',1)\n"
            )
            + "        return m.GitResult(0,raw)\n"
        )
        + "    return result\n"
        "m._git_command=inject\n"
    )
    _input_expected_error(
        _repair_scan(repo, setup, "range", base=repo.base, head=head), "INVALID_RANGE"
    )


@pytest.mark.parametrize("width", [40, 64])
@pytest.mark.parametrize(
    "guard",
    [
        "listed-commit",
        "listed-parent",
        "raw-parent",
        "second-tree",
        "late-parent",
        "delimiter",
    ],
)
def test_all_gaps_range_guard_isolated_mutations(width: int, guard: str):
    import inspect

    module = _all_gaps_module()
    commit, parent, tree = "a" * width, "b" * width, "c" * width
    if guard.startswith("listed"):
        raw = (
            f"{commit} {parent}\n{commit} {parent}\n"
            if guard == "listed-commit"
            else f"{commit} {parent} {parent}\n"
        ).encode()
        module._git_command = lambda *args, **kwargs: module.GitResult(0, raw)
        # Deliberately coordinate the counterpart so only the named listing guard acts.
        module._raw_commit_parents = lambda *args, **kwargs: (
            (parent,) if guard == "listed-commit" else (parent, parent)
        )
        function = module._range_commits
        source = inspect.getsource(function)
        target = (
            "commit in seen or "
            if guard == "listed-commit"
            else " or len(set(parents)) != len(parents)"
        )
        replacement = ""
        args = (Path("/synthetic"), parent, commit)
    else:
        raw = (
            f"tree {tree}\nparent {parent}\nparent {parent}\nauthor synthetic\n\nmessage\n"
            if guard == "raw-parent"
            else f"tree {tree}\ntree {tree}\nauthor synthetic\n\nmessage\n"
            if guard == "second-tree"
            else f"tree {tree}\nauthor synthetic\nparent {parent}\n\nmessage\n"
            if guard == "late-parent"
            else f"tree {tree}\nparent\t{parent}\nauthor synthetic\n\nmessage\n"
        ).encode()
        module._git_command = lambda *args, **kwargs: module.GitResult(0, raw)
        function = module._raw_commit_parents
        source = inspect.getsource(function)
        target, replacement = {
            "raw-parent": (" or parent in parents", ""),
            "second-tree": ("if is_tree:", "if False:"),
            "late-parent": ("not parent_section or ", ""),
            "delimiter": ('not line.startswith(b"parent ")', "False"),
        }[guard]
        args = (Path("/synthetic"), commit)
    with pytest.raises(module.ScanFailure) as failure:
        function(*args, object_id_length=width)
    assert failure.value.code == "INVALID_RANGE"
    assert source.count(target) == 1
    exec(source.replace(target, replacement, 1), module.__dict__)
    mutated = getattr(module, function.__name__)
    result = mutated(*args, object_id_length=width)
    expected = (
        [(commit, (parent,)), (commit, (parent,))]
        if guard == "listed-commit"
        else [(commit, (parent, parent))]
        if guard == "listed-parent"
        else (parent, parent)
        if guard == "raw-parent"
        else ()
        if guard == "second-tree"
        else (parent,)
    )
    assert (
        result == expected
    ), "named guard removal did not expose the crafted accepted input"


@pytest.mark.parametrize("mutant", [False, True], ids=["control", "override-mutant"])
def test_all_gaps_commit_graph_override_reaches_git(
    repo: Repository, tmp_path: Path, mutant: bool
):
    repo.put("ordinary.txt", "ordinary text\n")
    head = repo.commit()
    repo.git("commit-graph", "write", "--reachable")
    assert (repo.path / ".git/objects/info/commit-graph").is_file()
    marker = tmp_path / "graph-argv"
    marker.write_text("[]")
    setup = ""
    if mutant:
        setup += _all_gaps_mutation(
            "_git_command",
            '        "core.commitGraph=false",',
            '        "core.commitGraph=true",',
        )
    setup += (
        "real=m.subprocess.Popen\nobservations=[]\n"
        "def observe(argv,*args,**kwargs):\n"
        "    observations.append('core.commitGraph=false' in argv)\n"
        f"    pathlib.Path({str(marker)!r}).write_text(m.json.dumps(observations))\n"
        "    return real(argv,*args,**kwargs)\n"
        "m.subprocess.Popen=observe\n"
    )
    assert _repair_scan(repo, setup, "range", base=repo.base, head=head)[0] == 0
    observations = json.loads(marker.read_text())
    assert observations and all(observations) == (not mutant)


@pytest.mark.parametrize("which", ["inner", "outer", "leaf-notimplemented"])
def test_all_gaps_platform_and_final_leaf_guards_are_durable(
    repo: Repository, tmp_path: Path, which: str
):
    repo.put("ordinary.txt", "ordinary text\n")
    repo.commit()
    module = _all_gaps_module()
    if which == "outer":
        marker = tmp_path / "unexpected-git"
        marker.write_text("not-reached")
        setup = (
            "del os.O_NOFOLLOW\n"
            "def forbidden(*args,**kwargs): raise AssertionError('Git launched before outer guard')\n"
            "m._git_command=forbidden\n"
        )
        _input_expected_error(_repair_scan(repo, setup), "UNSUPPORTED_ENTRY")
    elif which == "inner":
        original = os.O_NOFOLLOW
        try:
            del os.O_NOFOLLOW
            with pytest.raises(module.ScanFailure) as failure:
                module._read_candidate_file(repo.path, "ordinary.txt")
            assert failure.value.code == "UNSUPPORTED_ENTRY"
        finally:
            os.O_NOFOLLOW = original
    else:
        setup = (
            "real=os.open\nreached=False\n"
            "def unsupported(path,*args,**kwargs):\n"
            "    global reached\n"
            "    if path=='ordinary.txt' and 'dir_fd' in kwargs:\n"
            "        reached=True;raise NotImplementedError('synthetic')\n"
            "    return real(path,*args,**kwargs)\n"
            "os.open=unsupported;os.supports_dir_fd=set(os.supports_dir_fd)|{unsupported}\n"
            "try: m._read_candidate_file(pathlib.Path(sys.argv[3]),'ordinary.txt')\n"
            "except m.ScanFailure as failure:\n"
            "    assert reached and failure.code=='UNSUPPORTED_ENTRY'\n"
            "    m._emit(m._report((),failure.code));raise SystemExit(2)\n"
            "raise AssertionError('leaf branch not reached')\n"
        )
        _input_expected_error(_repair_scan(repo, setup), "UNSUPPORTED_ENTRY")


def test_all_gaps_metadata_ancestor_symlink_is_unsupported(
    repo: Repository, tmp_path: Path
):
    actual = tmp_path / "actual-admin-parent"
    actual.mkdir()
    (repo.path / ".git").rename(actual / "admin")
    alias = tmp_path / "admin-alias"
    alias.symlink_to(actual, target_is_directory=True)
    (repo.path / ".git").write_text("gitdir: " + str(alias / "admin") + "\n")
    _input_expected_error(repo.scan(), "UNSUPPORTED_ENTRY")


def test_all_gaps_unrelated_watched_namespace_churn_fails_closed(repo: Repository):
    setup = (
        "original=m._load_policy\n"
        "def interleave(root,*args,**kwargs):\n"
        "    policy=original(root,*args,**kwargs)\n"
        "    p=root.parent/'unrelated-sibling';p.mkdir();p.rmdir()\n"
        "    return policy\n"
        "m._load_policy=interleave\n"
    )
    _input_expected_error(_repair_scan(repo, setup), "UNSUPPORTED_ENTRY")


@pytest.mark.parametrize(
    "mutant", [False, True], ids=["control", "route-witness-mutant"]
)
def test_all_gaps_carrier_witness_has_isolated_mutant(
    repo: Repository, tmp_path: Path, mutant: bool
):
    linked, alternate = _all_gaps_linked(repo, tmp_path)
    other = (alternate / ".git").read_bytes()
    setup = (
        "original=m._git_command\n"
        "def interleave(root,args,**kwargs):\n"
        "    if 'ls-files' not in args: return original(root,args,**kwargs)\n"
        "    p=root/'.git';saved=p.read_bytes()\n"
        f"    with p.open('r+b') as f: f.write({other!r});f.truncate()\n"
        "    try: return original(root,args,**kwargs)\n"
        "    finally:\n"
        "        with p.open('r+b') as f: f.write(saved);f.truncate()\n"
        "m._git_command=interleave\n"
    )
    if mutant:
        setup += "m._verify_candidate_routing=lambda *args,**kwargs: None\n"
    result = _repair_scan(linked, setup)
    if mutant:
        assert result[0] == 1, "explicit binding must still select original credential"
        assert has(result[1], "literal-assignment", "config.txt")
    else:
        _input_expected_error(result, "UNSUPPORTED_ENTRY")


def test_all_gaps_parent_namespace_survives_masked_index_leaf_ctime(
    repo: Repository, tmp_path: Path
):
    repo.put("ordinary.txt", "ordinary text\n")
    repo.commit()
    marker = tmp_path / "index-rename"
    marker.write_text("not-reached")
    setup = (
        "state=m._candidate_stat_state\n"
        "def mask_leaf(value):\n"
        "    result=state(value)\n"
        "    return result[:-1]+(0,) if m.stat.S_ISREG(value.st_mode) else result\n"
        "m._candidate_stat_state=mask_leaf\n"
        "read=m._read_candidate_file\nchanged=False\n"
        "def interleave(root,path):\n"
        "    global changed\n"
        "    result=read(root,path)\n"
        "    if not changed:\n"
        "        changed=True;p=root/'.git/index';saved=root/'.git/renamed-index'\n"
        "        p.rename(saved);saved.rename(p)\n"
        f"        pathlib.Path({str(marker)!r}).write_text('renamed-restored')\n"
        "    return result\n"
        "m._read_candidate_file=interleave\n"
    )
    result = _repair_scan(repo, setup)
    assert marker.read_text() == "renamed-restored"
    _input_expected_error(result, "UNSUPPORTED_ENTRY")


def test_all_gaps_wrong_common_index_pin_is_detected_directly(
    repo: Repository, tmp_path: Path
):
    linked, _ = _all_gaps_linked(repo, tmp_path)
    repo.git("read-tree", repo.base)
    linked_admin = Path(
        repo.git("-C", str(linked.path), "rev-parse", "--absolute-git-dir")
    )
    marker = tmp_path / "wrong-pin"
    marker.write_text("{}")
    setup = (
        "original=m._pin_candidate_index\n"
        "def wrong_pin(path,*args,**kwargs):\n"
        f"    wrong=pathlib.Path({str(repo.path / '.git/index')!r})\n"
        "    pin=original(wrong)\n"
        f"    expected=pathlib.Path({str(linked_admin / 'index')!r}).stat()\n"
        "    actual=os.fstat(pin.descriptor)\n"
        f"    pathlib.Path({str(marker)!r}).write_text(m.json.dumps({{'correct':actual.st_ino==expected.st_ino and actual.st_dev==expected.st_dev}}))\n"
        "    return pin\n"
        "m._pin_candidate_index=wrong_pin\n"
    )
    _repair_scan(linked, setup)
    assert json.loads(marker.read_text()) == {"correct": False}


# S01-R4-1: preserve the entire R3 test prefix; add bounded review regressions.
@pytest.mark.parametrize("object_format", ["sha1", "sha256"])
@pytest.mark.parametrize("configuration", ["core.worktree", "core.bare"])
def test_r4_configured_top_level_cannot_be_overridden_by_binding(
    tmp_path: Path, object_format: str, configuration: str
):
    repo = Repository(tmp_path / "repo", object_format=object_format)
    repo.put("config.txt", 'password="' + CANARY + '"\n')
    repo.commit()
    assert repo.scan()[0] == 1
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (repo.path / "config.txt").rename(elsewhere / "config.txt")
    repo.git(
        "config",
        configuration,
        str(elsewhere) if configuration == "core.worktree" else "true",
    )
    _input_expected_error(repo.scan("index"), "INVALID_REPOSITORY")
    _input_expected_error(repo.scan(), "INVALID_REPOSITORY")


@pytest.mark.parametrize("object_format", ["sha1", "sha256"])
@pytest.mark.parametrize(
    "case",
    [
        "main-absolute",
        "main-relative",
        "main-bare-false",
        "main-alias",
        "linked-ignored-worktree",
        "linked-ignored-bare",
        "linked-extension-wrong",
        "linked-extension-correct",
        "linked-extension-bare",
    ],
)
def test_r4_configured_worktree_semantics_match_native_git(
    tmp_path: Path, object_format: str, case: str
):
    repo = Repository(tmp_path / "repo", object_format=object_format)
    repo.put("config.txt", 'password="' + CANARY + '"\n')
    repo.commit()
    root = repo.path
    if case.startswith("linked"):
        root = tmp_path / "linked"
        repo.git("worktree", "add", "-q", "-b", "r4-linked", str(root))
    if case == "main-absolute":
        repo.git("config", "core.worktree", str(root))
    elif case == "main-relative":
        repo.git("config", "core.worktree", "..")
    elif case == "main-bare-false":
        repo.git("config", "core.bare", "false")
    elif case == "main-alias":
        alias = tmp_path / "root-alias"
        alias.symlink_to(root, target_is_directory=True)
        repo.git("config", "core.worktree", str(alias))
    elif case in {"linked-ignored-bare", "linked-extension-bare"}:
        repo.git("config", "core.bare", "true")
    else:
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        repo.git("config", "core.worktree", str(elsewhere))
    if case.startswith("linked-extension"):
        repo.git("config", "extensions.worktreeConfig", "true")
        if case == "linked-extension-correct":
            repo.git(
                "-C", str(root), "config", "--worktree", "core.worktree", str(root)
            )
    environment = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    environment.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
    native = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
        capture_output=True,
        env=environment,
        timeout=10,
    )
    result = invoke(root, repo.policy, "candidate")
    if case in {"linked-extension-wrong", "linked-extension-bare"}:
        assert (
            native.returncode != 0
            or Path(os.fsdecode(native.stdout).rstrip("\n")) != root
        )
        _input_expected_error(result, "INVALID_REPOSITORY")
    else:
        assert (
            native.returncode == 0
            and Path(os.fsdecode(native.stdout).rstrip("\n")) == root
        )
        assert result[0] == 1 and has(result[1], "literal-assignment", "config.txt")


@pytest.mark.parametrize(
    "shape", ["no-terminator", "double-terminator", "unknown-bool", "nonzero"]
)
def test_r4_bound_configuration_probe_is_wired_and_errors_are_controlled(
    repo: Repository, tmp_path: Path, shape: str
):
    marker = tmp_path / "config-probe"
    marker.write_text("not-reached")
    raw = {
        "no-terminator": b"false",
        "double-terminator": b"false\0\0",
        "unknown-bool": b"maybe\0",
        "nonzero": b"",
    }[shape]
    setup = (
        "original=m._git_command\n"
        "def inject(root,args,**kwargs):\n"
        "    if args[0]=='config' and 'core.bare' in args:\n"
        f"        pathlib.Path({str(marker)!r}).write_text('reached')\n"
        + (
            "        raise m.ScanFailure('GIT_FAILURE')\n"
            if shape == "nonzero"
            else f"        return m.GitResult(0,{raw!r})\n"
        )
        + "    return original(root,args,**kwargs)\n"
        "m._git_command=inject\n"
    )
    result = _repair_scan(repo, setup)
    _input_expected_error(result, "INVALID_REPOSITORY")
    assert marker.read_text() == "reached"


@pytest.mark.parametrize(
    "mutant", [False, True], ids=["control", "swallow-close-mutant"]
)
def test_r4_final_close_failure_is_not_success_and_cleanup_continues(
    repo: Repository, tmp_path: Path, mutant: bool
):
    marker = tmp_path / "close-state"
    marker.write_text("{}")
    setup = (
        "real_open=os.open;real_close=os.close;context_close=m._CandidateRoutingContext.close\n"
        "active=set();cleanup=False;injected=False;after_failure=0\n"
        "def track_open(*args,**kwargs):\n"
        "    fd=real_open(*args,**kwargs);active.add(fd);return fd\n"
        "os.open=track_open;os.supports_dir_fd=set(os.supports_dir_fd)|{track_open}\n"
        "def close_context(self):\n"
        "    global cleanup\n"
        "    cleanup=True\n"
        "    try: return context_close(self)\n"
        "    finally: cleanup=False\n"
        "m._CandidateRoutingContext.close=close_context\n"
        "def close_fault(fd):\n"
        "    global injected,after_failure\n"
        "    result=real_close(fd);active.discard(fd)\n"
        "    if cleanup and injected: after_failure+=1\n"
        "    if cleanup and not injected:\n"
        "        injected=True;raise OSError('synthetic post-close failure')\n"
        "    return result\n"
        "os.close=close_fault\n"
        "entry=m.main\n"
        "def observe(argv):\n"
        "    result=entry(argv)\n"
        f"    pathlib.Path({str(marker)!r}).write_text(m.json.dumps({{'active':sorted(active),'injected':injected,'after_failure':after_failure}}))\n"
        "    return result\n"
        "m.main=observe\n"
    )
    if mutant:
        setup = (
            _all_gaps_mutation(
                "_close_candidate_descriptors", "if failed:", "if False:"
            )
            + setup
        )
    result = _repair_scan(repo, setup)
    state = json.loads(marker.read_text())
    assert state["injected"] and state["after_failure"] > 0 and state["active"] == []
    if mutant:
        assert result == (0, {"status": "clean", "findings": [], "errors": []})
    else:
        _input_expected_error(result, "UNSUPPORTED_ENTRY")


@pytest.mark.parametrize("component", ["..", "./.."])
@pytest.mark.parametrize("mutant", [False, True], ids=["control", "normpath-mutant"])
def test_r4_middle_metadata_component_cannot_be_lexically_collapsed(
    repo: Repository, tmp_path: Path, component: str, mutant: bool
):
    repo.put("config.txt", 'password="' + CANARY + '"\n')
    repo.commit()
    (repo.path / ".git").rename(tmp_path / "admin")
    (tmp_path / "anchor").symlink_to(tmp_path, target_is_directory=True)
    (repo.path / ".git").write_text("gitdir: ../anchor/" + component + "/admin\n")
    setup = ""
    if mutant:
        setup = (
            "original=m._candidate_walk_directory\n"
            "def normalize(context,start,start_path,target):\n"
            "    return original(context,start,start_path,os.path.normpath(target))\n"
            "m._candidate_walk_directory=normalize\n"
        )
    result = _repair_scan(repo, setup)
    if mutant:
        assert result[0] == 1 and has(result[1], "literal-assignment", "config.txt")
    else:
        _input_expected_error(result, "UNSUPPORTED_ENTRY")


@pytest.mark.parametrize(
    "mutant", [False, True], ids=["control", "content-only-mutant"]
)
def test_r4_carrier_content_guard_is_independently_meaningful(
    repo: Repository, tmp_path: Path, mutant: bool
):
    linked, _ = _all_gaps_linked(repo, tmp_path)
    original = (linked.path / ".git").read_bytes()
    setup = (
        "state=m._candidate_stat_state\n"
        "def mask(value):\n"
        "    result=state(value)\n"
        "    return result[:-1]+(0,) if m.stat.S_ISREG(value.st_mode) else result\n"
        "m._candidate_stat_state=mask\nlisting=m._index_entries\n"
        "def interleave(root,**kwargs):\n"
        "    entries=listing(root,**kwargs);p=root/'.git';before=p.stat();data=p.read_bytes()\n"
        "    replacement=data[:-2]+(b'z' if data[-2:-1]!=b'z' else b'y')+data[-1:]\n"
        "    assert len(replacement)==len(data) and replacement!=data\n"
        "    with p.open('r+b') as f: f.write(replacement);f.truncate()\n"
        "    os.utime(p,ns=(before.st_atime_ns,before.st_mtime_ns))\n"
        "    return entries\n"
        "m._index_entries=interleave\n"
    )
    if mutant:
        setup = (
            _all_gaps_mutation(
                "_verify_candidate_routing",
                "if carrier.content is not None:",
                "if False:",
            )
            + setup
        )
    try:
        result = _repair_scan(linked, setup)
        if mutant:
            assert result[0] == 1 and has(result[1], "literal-assignment", "config.txt")
        else:
            _input_expected_error(result, "UNSUPPORTED_ENTRY")
    finally:
        (linked.path / ".git").write_bytes(original)


def test_r4_wrong_common_index_mutant_also_asserts_controlled_rejection(
    repo: Repository, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    original = _repair_scan
    observations = []

    def observe(*args, **kwargs):
        result = original(*args, **kwargs)
        observations.append(result)
        return result

    monkeypatch.setitem(globals(), "_repair_scan", observe)
    test_all_gaps_wrong_common_index_pin_is_detected_directly(repo, tmp_path)
    assert len(observations) == 1
    _input_expected_error(observations[0], "UNSUPPORTED_ENTRY")


@pytest.mark.parametrize(
    "mutant", [False, True], ids=["control", "comparison-only-mutant"]
)
def test_r4_final_identity_mutant_preserves_probe_side_effect(
    repo: Repository, tmp_path: Path, mutant: bool
):
    marker = tmp_path / "identity-probe"
    marker.write_text("not-reached")
    setup = (
        "original=m._git_command\nlistings=0\n"
        "def inject(root,args,**kwargs):\n"
        "    global listings\n"
        "    if 'ls-files' in args: listings+=1\n"
        "    if listings==2 and '--git-dir' in args:\n"
        f"        pathlib.Path({str(marker)!r}).write_text('reached')\n"
        "        return m.GitResult(0,os.fsencode(str(root/'different-admin'))+b'\\n')\n"
        "    return original(root,args,**kwargs)\n"
        "m._git_command=inject\n"
    )
    if mutant:
        setup += (
            "import ast,inspect,textwrap\n"
            "tree=ast.parse(textwrap.dedent(inspect.getsource(m._read_candidate_snapshot)))\n"
            "class InvertIdentity(ast.NodeTransformer):\n"
            "    count=0\n"
            "    def visit_Compare(self,node):\n"
            "        left=node.left\n"
            "        if isinstance(left,ast.Call) and isinstance(left.func,ast.Name) and left.func.id=='_candidate_index_path':\n"
            "            assert len(node.ops)==1 and isinstance(node.ops[0],ast.NotEq)\n"
            "            node.ops=[ast.Eq()];self.count+=1\n"
            "        return self.generic_visit(node)\n"
            "change=InvertIdentity();tree=change.visit(tree);assert change.count==1\n"
            "exec(compile(ast.fix_missing_locations(tree),'<comparison-mutant>','exec'),m.__dict__)\n"
        )
    result = _repair_scan(repo, setup)
    assert marker.read_text() == "reached"
    if mutant:
        assert result == (0, {"status": "clean", "findings": [], "errors": []})
    else:
        _input_expected_error(result, "UNSUPPORTED_ENTRY")


# S01-CONFIG-COHERENCE-1: R4 findings, native Git setup semantics and config pins.
@pytest.mark.parametrize("object_format", ["sha1", "sha256"])
@pytest.mark.parametrize("key", ["core.worktree", "core.bare"])
@pytest.mark.parametrize(
    "mask_direct",
    [False, True],
    ids=["ignored-include-control", "include-masks-invalid"],
)
def test_config_coherence_native_setup_ignores_included_core_settings(
    tmp_path: Path, object_format: str, key: str, mask_direct: bool
):
    repo = Repository(tmp_path / "repo", object_format=object_format)
    repo.put("config.txt", 'password="' + CANARY + '"\n')
    repo.commit()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    if mask_direct:
        (repo.path / "config.txt").rename(elsewhere / "config.txt")
        repo.git("config", key, str(elsewhere) if key == "core.worktree" else "true")
    included = tmp_path / "mask.inc"
    value = (
        str(repo.path if mask_direct else elsewhere)
        if key == "core.worktree"
        else ("false" if mask_direct else "true")
    )
    included.write_text("[core]\n\t" + key.split(".")[1] + " = " + value + "\n")
    repo.git("config", "include.path", str(included))
    if mask_direct:
        _input_expected_error(repo.scan("index"), "INVALID_REPOSITORY")
        _input_expected_error(repo.scan(), "INVALID_REPOSITORY")
    else:
        assert repo.scan("index")[0] == 1
        code, report = repo.scan()
        assert code == 1 and has(report, "literal-assignment", "config.txt")


@pytest.mark.parametrize("object_format", ["sha1", "sha256"])
def test_config_coherence_local_extension_value_cannot_mask_common_activation(
    tmp_path: Path, object_format: str
):
    repo = Repository(tmp_path / "repo", object_format=object_format)
    repo.put("config.txt", 'password="' + CANARY + '"\n')
    repo.commit()
    linked = tmp_path / "linked"
    repo.git("worktree", "add", "-q", "-b", "linked", str(linked))
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (linked / "config.txt").rename(elsewhere / "config.txt")
    repo.git("config", "extensions.worktreeConfig", "true")
    repo.git("-C", str(linked), "config", "--worktree", "core.worktree", str(elsewhere))
    repo.git(
        "-C", str(linked), "config", "--worktree", "extensions.worktreeConfig", "false"
    )
    _input_expected_error(invoke(linked, repo.policy, "index"), "INVALID_REPOSITORY")
    _input_expected_error(
        invoke(linked, repo.policy, "candidate"), "INVALID_REPOSITORY"
    )


@pytest.mark.parametrize("object_format", ["sha1", "sha256"])
@pytest.mark.parametrize(
    "local", [False, True], ids=["common-config", "worktree-config"]
)
def test_config_coherence_probes_cannot_combine_two_invalid_states(
    tmp_path: Path, object_format: str, local: bool
):
    from types import SimpleNamespace

    repo = Repository(tmp_path / "repo", object_format=object_format)
    repo.put("config.txt", 'password="' + CANARY + '"\n')
    repo.commit()
    root = repo.path
    if local:
        root = tmp_path / "linked"
        repo.git("worktree", "add", "-q", "-b", "linked", str(root))
        repo.git("config", "extensions.worktreeConfig", "true")
        repo.git("-C", str(root), "config", "--worktree", "core.worktree", str(root))
        repo.git("-C", str(root), "config", "--worktree", "core.bare", "false")
        admin = Path(repo.git("-C", str(root), "rev-parse", "--absolute-git-dir"))
        target = admin / "config.worktree"
    else:
        repo.git("config", "core.worktree", str(root))
        target = root / ".git/config"
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (root / "config.txt").rename(elsewhere / "config.txt")
    base = target.read_bytes()
    bare_state = base.replace(b"bare = false", b"bare = true")
    elsewhere_state = base.replace(os.fsencode(str(root)), os.fsencode(str(elsewhere)))
    assert (
        bare_state != base and elsewhere_state != base and bare_state != elsewhere_state
    )
    for data in (bare_state, elsewhere_state):
        target.write_bytes(data)
        _input_expected_error(invoke(root, repo.policy, "index"), "INVALID_REPOSITORY")
    target.write_bytes(bare_state)
    marker = tmp_path / "mixed-config-phases"
    marker.write_text("[]")
    setup = (
        "read=m._candidate_config_value\nphases=[]\n"
        f"target=pathlib.Path({str(target)!r})\n"
        "def interleave(root,binding,key,**kwargs):\n"
        "    selected=kwargs.get('config_path',target)\n"
        "    if pathlib.Path(selected)==target and key in {'core.bare','core.worktree'}:\n"
        f"        data={elsewhere_state!r} if key=='core.bare' else {bare_state!r}\n"
        "        with target.open('r+b') as f: f.write(data);f.truncate()\n"
        "        phases.append(key)\n"
        f"        pathlib.Path({str(marker)!r}).write_text(m.json.dumps(phases))\n"
        "    return read(root,binding,key,**kwargs)\n"
        "m._candidate_config_value=interleave\n"
    )
    result = _repair_scan(SimpleNamespace(path=root, policy=repo.policy), setup)
    assert json.loads(marker.read_text())[0] == "core.bare"
    _input_expected_error(result, "UNSUPPORTED_ENTRY")


@pytest.mark.parametrize("object_format", ["sha1", "sha256"])
def test_config_coherence_worktree_path_does_not_expand_tilde(
    tmp_path: Path, object_format: str
):
    repo = Repository(tmp_path / "repo", object_format=object_format)
    repo.put("config.txt", 'password="' + CANARY + '"\n')
    repo.commit()
    repo.git("config", "core.worktree", "~/" + os.path.relpath(repo.path, Path.home()))
    _input_expected_error(repo.scan("index"), "INVALID_REPOSITORY")
    _input_expected_error(repo.scan(), "INVALID_REPOSITORY")


@pytest.mark.parametrize("mutant", [False, True], ids=["control", "strip-mutant"])
def test_config_coherence_trailing_worktree_whitespace_is_not_stripped(
    repo: Repository, tmp_path: Path, mutant: bool
):
    repo.put("config.txt", 'password="' + CANARY + '"\n')
    repo.commit()
    elsewhere = Path(str(repo.path) + " ")
    elsewhere.mkdir()
    (repo.path / "config.txt").rename(elsewhere / "config.txt")
    repo.git("config", "core.worktree", str(elsewhere))
    environment = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    environment.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
    native = subprocess.run(
        ["git", "-C", str(repo.path), "rev-parse", "--show-toplevel"],
        capture_output=True,
        env=environment,
        timeout=10,
    )
    assert (
        native.returncode == 0 and native.stdout == os.fsencode(str(elsewhere)) + b"\n"
    )
    assert Path(os.fsdecode(native.stdout[:-1])) != repo.path
    setup = (
        _all_gaps_mutation(
            "_candidate_config_value",
            "value = result.stdout[:-1]",
            "value = result.stdout[:-1].strip()",
        )
        if mutant
        else ""
    )
    result = _repair_scan(repo, setup)
    if mutant:
        assert result[0] == 0
    else:
        _input_expected_error(result, "INVALID_REPOSITORY")


@pytest.mark.parametrize("mutant", [False, True], ids=["control", "truthiness-mutant"])
def test_config_coherence_empty_worktree_is_not_unset(repo: Repository, mutant: bool):
    repo.git("config", "core.worktree", "")
    setup = (
        _all_gaps_mutation(
            "_validate_candidate_repository_config",
            "if worktree is not None:",
            "if worktree:",
        )
        if mutant
        else ""
    )
    result = _repair_scan(repo, setup)
    if mutant:
        assert result[0] == 0
    else:
        _input_expected_error(result, "INVALID_REPOSITORY")


@pytest.mark.parametrize("shape", ["unterminated-path", "unset-with-stdout"])
@pytest.mark.parametrize("mutant", [False, True], ids=["control", "framing-mutant"])
def test_config_coherence_path_framing_guards_have_unique_oracles(
    repo: Repository, shape: str, mutant: bool
):
    raw = os.fsencode(str(repo.path)) + (
        b"X" if shape == "unterminated-path" else b"\0"
    )
    code = 0 if shape == "unterminated-path" else 1
    setup = (
        "original=m._git_command\n"
        "def inject(root,args,**kwargs):\n"
        "    if args[0]=='config' and 'core.worktree' in args:\n"
        f"        return m.GitResult({code},{raw!r})\n"
        "    return original(root,args,**kwargs)\n"
        "m._git_command=inject\n"
    )
    if mutant:
        if shape == "unterminated-path":
            setup = (
                _all_gaps_mutation(
                    "_candidate_config_value",
                    '        or not result.stdout.endswith(b"\\0")\n',
                    "",
                )
                + setup
            )
        else:
            setup = (
                _all_gaps_mutation(
                    "_candidate_config_value",
                    "if result.returncode == 1 and not result.stdout:",
                    "if result.returncode == 1:",
                )
                + setup
            )
    result = _repair_scan(repo, setup)
    if mutant:
        assert result[0] == 0
    else:
        _input_expected_error(result, "INVALID_REPOSITORY")


@pytest.mark.parametrize("object_format", ["sha1", "sha256"])
def test_config_coherence_linked_relative_worktree_uses_private_gitdir(
    tmp_path: Path, object_format: str
):
    repo = Repository(tmp_path / "repo", object_format=object_format)
    repo.put("config.txt", 'password="' + CANARY + '"\n')
    repo.commit()
    linked = tmp_path / "linked"
    repo.git("worktree", "add", "-q", "-b", "linked", str(linked))
    admin = Path(repo.git("-C", str(linked), "rev-parse", "--absolute-git-dir"))
    repo.git("config", "extensions.worktreeConfig", "true")
    repo.git(
        "-C",
        str(linked),
        "config",
        "--worktree",
        "core.worktree",
        os.path.relpath(linked, admin),
    )
    assert invoke(linked, repo.policy, "index")[0] == 1
    assert invoke(linked, repo.policy, "candidate")[0] == 1


@pytest.mark.parametrize("name", ["config", "config.worktree"])
@pytest.mark.parametrize("kind", ["symlink", "fifo", "directory"])
def test_config_coherence_config_carriers_are_nofollow_regular_files(
    repo: Repository, tmp_path: Path, name: str, kind: str
):
    path = repo.path / ".git" / name
    if path.exists():
        original = path.read_bytes()
        path.unlink()
    else:
        original = b"[core]\n\tbare = false\n"
    if kind == "symlink":
        target = tmp_path / "config-target"
        target.write_bytes(original)
        path.symlink_to(target)
    elif kind == "fifo":
        os.mkfifo(path)
    else:
        path.mkdir()
    _input_expected_error(repo.scan(), "UNSUPPORTED_ENTRY")


# S01-R5: distinguish the two local bare overlays and pre-Git config custody.
@pytest.mark.parametrize("object_format", ["sha1", "sha256"])
@pytest.mark.parametrize("common_bare,local_bare", [(True, False), (False, True)])
@pytest.mark.parametrize(
    "mutant", [False, True], ids=["control", "ignore-local-mutant"]
)
def test_config_coherence_local_bare_overlay_both_directions(
    tmp_path: Path,
    object_format: str,
    common_bare: bool,
    local_bare: bool,
    mutant: bool,
):
    from types import SimpleNamespace

    repo = Repository(tmp_path / "repo", object_format=object_format)
    repo.put("config.txt", 'password="' + CANARY + '"\n')
    repo.commit()
    linked = tmp_path / "linked"
    repo.git("worktree", "add", "-q", "-b", "linked", str(linked))
    admin = Path(repo.git("-C", str(linked), "rev-parse", "--absolute-git-dir"))
    repo.git("config", "extensions.worktreeConfig", "true")
    repo.git(
        "config",
        "--file",
        str(repo.path / ".git/config"),
        "core.bare",
        str(common_bare).lower(),
    )
    repo.git(
        "config",
        "--file",
        str(admin / "config.worktree"),
        "core.bare",
        str(local_bare).lower(),
    )

    environment = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    environment.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
    native = subprocess.run(
        ["git", "-C", str(linked), "rev-parse", "--show-toplevel"],
        capture_output=True,
        env=environment,
        timeout=10,
    )
    assert (native.returncode == 0) == (not local_bare)
    if not local_bare:
        assert Path(os.fsdecode(native.stdout).rstrip("\n")) == linked

    setup = (
        _all_gaps_mutation(
            "_validate_candidate_repository_config",
            "bare = local_bare",
            "bare = bare",
        )
        if mutant
        else ""
    )
    result = _repair_scan(SimpleNamespace(path=linked, policy=repo.policy), setup)
    if not mutant:
        for mode in ("candidate", "index"):
            direct = invoke(linked, repo.policy, mode)
            if local_bare:
                _input_expected_error(direct, "INVALID_REPOSITORY")
            else:
                assert direct[0] == 1 and has(
                    direct[1], "literal-assignment", "config.txt"
                )
    if mutant:
        if common_bare:
            _input_expected_error(result, "INVALID_REPOSITORY")
        else:
            assert result[0] == 1 and has(
                result[1], "literal-assignment", "config.txt"
            ), result[1]["errors"]
    elif local_bare:
        _input_expected_error(result, "INVALID_REPOSITORY")
    else:
        assert result[0] == 1 and has(result[1], "literal-assignment", "config.txt")


def _config_pin_first_git_setup(
    marker: Path,
    removed_carrier: str | None = None,
    *,
    wrong_private_parent: bool = False,
) -> str:
    setup = (
        _all_gaps_mutation(
            "_pin_candidate_routing",
            f'        _candidate_open_carrier(context, {"common_directory" if removed_carrier == "config" else "git_directory"}, "{removed_carrier}")',
            "",
        )
        if removed_carrier is not None
        else ""
    )
    if wrong_private_parent:
        setup += _all_gaps_mutation(
            "_pin_candidate_routing",
            '        _candidate_open_carrier(context, git_directory, "config.worktree")',
            '        _candidate_open_carrier(context, common_directory, "config.worktree")',
        )
    return setup + (
        "real_pin=m._pin_candidate_routing;context=None\n"
        "def capture_pin(repository):\n"
        "    global context\n"
        "    context=real_pin(repository);return context\n"
        "m._pin_candidate_routing=capture_pin\n"
        "real_popen=m.subprocess.Popen;observed=False\n"
        "def capture_first(argv,*args,**kwargs):\n"
        "    global observed\n"
        "    if not observed:\n"
        "        observed=True\n"
        "        data={}\n"
        "        for name in ('config','config.worktree'):\n"
        "            expected=context.binding.common_dir if name=='config' else context.binding.git_dir\n"
        "            expected_stat=os.stat(expected,follow_symlinks=False)\n"
        "            def right_parent(parent):\n"
        "                value=os.fstat(parent.descriptor)\n"
        "                return (value.st_dev,value.st_ino)==(expected_stat.st_dev,expected_stat.st_ino)\n"
        "            edges=[e for e in context.edges.values() if e.name==name and right_parent(e.parent)]\n"
        "            held=len(edges)==1 and right_parent(edges[0].parent) and edges[0].descriptor in context.descriptors and m._candidate_stat_state(os.fstat(edges[0].descriptor))==edges[0].state\n"
        "            absences=[parent for parent,n in context.absences if n==name and right_parent(parent)]\n"
        "            observations=[(parent,state) for parent,n,state in context.observations if n==name and right_parent(parent)]\n"
        "            absent=len(absences)==1 and len(observations)==1 and observations[0][1] is None and absences[0].descriptor==observations[0][0].descriptor and right_parent(absences[0])\n"
        "            data[name]={'held':bool(held),'absent':bool(absent)}\n"
        f"        pathlib.Path({str(marker)!r}).write_text(m.json.dumps(data))\n"
        "    return real_popen(argv,*args,**kwargs)\n"
        "m.subprocess.Popen=capture_first\n"
    )


@pytest.mark.parametrize("layout", ["main", "linked"])
@pytest.mark.parametrize(
    "local_present", [False, True], ids=["local-absent", "local-present"]
)
def test_config_coherence_first_git_has_both_carriers_pinned(
    tmp_path: Path, layout: str, local_present: bool
):
    from types import SimpleNamespace

    repo = Repository(tmp_path / "repo")
    repo.put("config.txt", 'password="' + CANARY + '"\n')
    repo.commit()
    root = repo.path
    if layout == "linked":
        root = tmp_path / "linked"
        repo.git("worktree", "add", "-q", "-b", "linked", str(root))
    admin = Path(repo.git("-C", str(root), "rev-parse", "--absolute-git-dir"))
    if local_present:
        (admin / "config.worktree").write_text("[core]\n\tbare = false\n")
    marker = tmp_path / "first-git-pins.json"
    marker.write_text("{}")
    result = _repair_scan(
        SimpleNamespace(path=root, policy=repo.policy),
        _config_pin_first_git_setup(marker),
    )
    assert result[0] == 1 and has(result[1], "literal-assignment", "config.txt")
    assert json.loads(marker.read_text()) == {
        "config": {"held": True, "absent": False},
        "config.worktree": {"held": local_present, "absent": not local_present},
    }


@pytest.mark.parametrize("layout", ["main", "linked"])
@pytest.mark.parametrize("removed_carrier", ["config", "config.worktree"])
def test_config_coherence_first_git_pin_mutation_is_detected(
    repo: Repository, tmp_path: Path, removed_carrier: str, layout: str
):
    from types import SimpleNamespace

    repo.put("config.txt", 'password="' + CANARY + '"\n')
    repo.commit()
    root = repo.path
    if layout == "linked":
        root = tmp_path / "linked"
        repo.git("worktree", "add", "-q", "-b", "linked", str(root))
    marker = tmp_path / "first-git-mutant.json"
    marker.write_text("{}")
    result = _repair_scan(
        SimpleNamespace(path=root, policy=repo.policy),
        _config_pin_first_git_setup(marker, removed_carrier),
    )
    assert result[0] == 1 and has(result[1], "literal-assignment", "config.txt")
    observed = json.loads(marker.read_text())
    assert observed[removed_carrier] == {"held": False, "absent": False}
    other = "config.worktree" if removed_carrier == "config" else "config"
    assert observed[other] == (
        {"held": True, "absent": False}
        if other == "config"
        else {"held": False, "absent": True}
    )


def test_first_git_linked_absence_uses_private_config_parent(
    repo: Repository, tmp_path: Path
):
    from types import SimpleNamespace

    repo.put("config.txt", 'password="' + CANARY + '"\n')
    repo.commit()
    linked = tmp_path / "linked"
    repo.git("worktree", "add", "-q", "-b", "linked", str(linked))
    selected = SimpleNamespace(path=linked, policy=repo.policy)
    marker = tmp_path / "wrong-parent.json"
    marker.write_text("{}")
    control = _repair_scan(selected, _config_pin_first_git_setup(marker))
    assert control[0] == 1 and has(control[1], "literal-assignment", "config.txt")
    assert json.loads(marker.read_text())["config.worktree"] == {
        "held": False,
        "absent": True,
    }
    marker.write_text("{}")
    mutant = _repair_scan(
        selected, _config_pin_first_git_setup(marker, wrong_private_parent=True)
    )
    assert mutant[0] == 1 and has(mutant[1], "literal-assignment", "config.txt")
    assert json.loads(marker.read_text())["config.worktree"] == {
        "held": False,
        "absent": False,
    }


def test_first_git_pin_ignores_same_named_ancestor(tmp_path: Path):
    parent = tmp_path / "config"
    parent.mkdir()
    repo = Repository(parent / "repo")
    repo.put("config.txt", 'password="' + CANARY + '"\n')
    repo.commit()
    marker = tmp_path / "same-name.json"
    marker.write_text("{}")
    result = _repair_scan(repo, _config_pin_first_git_setup(marker))
    assert result[0] == 1 and has(result[1], "literal-assignment", "config.txt")
    assert json.loads(marker.read_text())["config"] == {
        "held": True,
        "absent": False,
    }


def test_candidate_configured_worktree_alias_aba_rejects_wrong_native_root(
    repo: Repository, tmp_path: Path
):
    import tempfile

    repo.put("config.txt", 'password="' + CANARY + '"\n')
    repo.commit()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (repo.path / "config.txt").rename(elsewhere / "config.txt")
    root = repo.path.resolve()
    bases = [Path(tempfile.gettempdir()), Path.home(), Path("/var/tmp")]
    disjoint = next(
        (
            base.resolve()
            for base in bases
            if base.is_dir()
            and not root.is_relative_to(base.resolve())
            and not base.resolve().is_relative_to(root)
        ),
        None,
    )
    assert disjoint is not None, "no disjoint alias fixture parent"
    with tempfile.TemporaryDirectory(prefix="s01-config-alias-", dir=disjoint) as area:
        alias = Path(area) / "configured-root"
        alias.symlink_to(elsewhere, target_is_directory=True)
        repo.git("config", "core.worktree", str(alias))

        def native_root() -> Path:
            environment = {
                key: value
                for key, value in os.environ.items()
                if not key.startswith("GIT_")
            }
            environment.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
            native = subprocess.run(
                ["git", "-C", str(repo.path), "rev-parse", "--show-toplevel"],
                capture_output=True,
                env=environment,
                timeout=10,
            )
            assert native.returncode == 0
            return Path(os.fsdecode(native.stdout).rstrip("\n"))

        assert native_root() == elsewhere
        _input_expected_error(repo.scan(), "INVALID_REPOSITORY")
        marker = tmp_path / "configured-alias-phases.json"
        marker.write_text("[]")
        setup = (
            "real_readlink=os.readlink\n"
            f"alias=pathlib.Path({str(alias)!r})\n"
            f"selected=pathlib.Path({str(repo.path)!r})\n"
            f"elsewhere=pathlib.Path({str(elsewhere)!r})\n"
            "phases=[]\n"
            "def alias_interleave(path,*args,**kwargs):\n"
            "    if pathlib.Path(os.fsdecode(path)).name!=alias.name: return real_readlink(path,*args,**kwargs)\n"
            "    parent_fd=kwargs.get('dir_fd')\n"
            "    if parent_fd is None and pathlib.Path(os.fsdecode(path))!=alias: return real_readlink(path,*args,**kwargs)\n"
            "    if parent_fd is not None:\n"
            "        a=os.fstat(parent_fd);b=alias.parent.stat()\n"
            "        if (a.st_dev,a.st_ino)!=(b.st_dev,b.st_ino): return real_readlink(path,*args,**kwargs)\n"
            "    alias.unlink();alias.symlink_to(selected,target_is_directory=True)\n"
            "    phases.append('flipped')\n"
            f"    pathlib.Path({str(marker)!r}).write_text(m.json.dumps(phases))\n"
            "    try: return real_readlink(path,*args,**kwargs)\n"
            "    finally:\n"
            "        alias.unlink();alias.symlink_to(elsewhere,target_is_directory=True)\n"
            "        phases.append('restored')\n"
            f"        pathlib.Path({str(marker)!r}).write_text(m.json.dumps(phases))\n"
            "os.readlink=alias_interleave\n"
        )
        result = _repair_scan(repo, setup)
        assert json.loads(marker.read_text()) == ["flipped", "restored"]
        assert alias.readlink() == elsewhere
        assert native_root() == elsewhere
        _input_expected_error(result, "UNSUPPORTED_ENTRY")


@pytest.mark.parametrize("object_format", ["sha1", "sha256"])
@pytest.mark.parametrize("case", ["absolute", "nested", "linked-relative"])
def test_candidate_configured_worktree_stable_aliases_remain_supported(
    tmp_path: Path, object_format: str, case: str
):
    repo = Repository(tmp_path / "repo", object_format=object_format)
    repo.put("config.txt", 'password="' + CANARY + '"\n')
    repo.commit()
    root = repo.path
    if case == "linked-relative":
        root = tmp_path / "linked"
        repo.git("worktree", "add", "-q", "-b", "linked", str(root))
        admin = Path(repo.git("-C", str(root), "rev-parse", "--absolute-git-dir"))
        alias = admin / "configured-root"
        alias.symlink_to(root, target_is_directory=True)
        repo.git("config", "extensions.worktreeConfig", "true")
        repo.git("-C", str(root), "config", "--worktree", "core.worktree", alias.name)
    else:
        alias = tmp_path / "configured-root"
        if case == "nested":
            second = tmp_path / "second-alias"
            second.symlink_to(root, target_is_directory=True)
            alias.symlink_to(second, target_is_directory=True)
        else:
            alias.symlink_to(root, target_is_directory=True)
        repo.git("config", "core.worktree", str(alias))

    environment = {
        key: value for key, value in os.environ.items() if not key.startswith("GIT_")
    }
    environment.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
    native = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
        capture_output=True,
        env=environment,
        timeout=10,
    )
    assert native.returncode == 0
    assert Path(os.fsdecode(native.stdout).rstrip("\n")).resolve() == root.resolve()
    for mode in ("candidate", "index"):
        code, report = invoke(root, repo.policy, mode)
        assert code == 1 and has(report, "literal-assignment", "config.txt"), report[
            "errors"
        ]


def test_candidate_configured_worktree_symlink_loop_is_controlled(
    repo: Repository, tmp_path: Path
):
    alias = tmp_path / "configured-loop"
    alias.symlink_to(alias, target_is_directory=True)
    repo.git("config", "core.worktree", str(alias))
    _input_expected_error(repo.scan(), "INVALID_REPOSITORY")


def test_candidate_configured_alias_witness_precedes_semantic_git(
    repo: Repository, tmp_path: Path
):
    repo.put("config.txt", 'password="' + CANARY + '"\n')
    repo.commit()
    alias = tmp_path / "configured-root"
    alias.symlink_to(repo.path, target_is_directory=True)
    repo.git("config", "core.worktree", str(alias))
    marker = tmp_path / "witness-before-git.json"
    marker.write_text("{}")
    setup = (
        "original_pin=m._pin_candidate_routing;context=None\n"
        "def capture_pin(repository):\n"
        "    global context\n"
        "    context=original_pin(repository);return context\n"
        "m._pin_candidate_routing=capture_pin\n"
        "original_git=m._git_command\n"
        "def observe_git(root,args,**kwargs):\n"
        "    if args[:2]==['rev-parse','--show-toplevel']:\n"
        "        witnesses=context.symlinks\n"
        "        held=len(witnesses)==1 and witnesses[0].parent.descriptor in context.descriptors\n"
        f"        pathlib.Path({str(marker)!r}).write_text(m.json.dumps({{'held':held,'target':witnesses[0].target==os.fsencode({str(repo.path)!r}) if held else False}}))\n"
        "    return original_git(root,args,**kwargs)\n"
        "m._git_command=observe_git\n"
    )
    code, report = _repair_scan(repo, setup)
    assert code == 1 and has(report, "literal-assignment", "config.txt")
    assert json.loads(marker.read_text()) == {"held": True, "target": True}


@pytest.mark.parametrize(
    "mutant",
    ["control", "skip-target-guard", "length-only-guard"],
)
def test_candidate_configured_alias_target_recheck_has_unique_oracle(
    repo: Repository, tmp_path: Path, mutant: str
):
    repo.put("config.txt", 'password="' + CANARY + '"\n')
    repo.commit()
    alias = tmp_path / "configured-root"
    alias.symlink_to(repo.path, target_is_directory=True)
    repo.git("config", "core.worktree", str(alias))
    elsewhere = tmp_path / "away"
    elsewhere.mkdir()
    assert len(os.fsencode(str(elsewhere))) == len(os.fsencode(str(repo.path)))
    marker = tmp_path / "target-drift.json"
    marker.write_text("false")
    setup = (
        "original_state=m._candidate_stat_state\n"
        "def mask_metadata(value):\n"
        "    state=original_state(value)\n"
        "    if m.stat.S_ISDIR(value.st_mode): return state[:4]+(0,0,0)\n"
        "    if m.stat.S_ISLNK(value.st_mode): return (state[0],0,state[2],state[3],0,0,0)\n"
        "    return state\n"
        "m._candidate_stat_state=mask_metadata\n"
        "original_read=m._read_candidate_file;changed=False\n"
        "def change_after_read(root,path):\n"
        "    global changed\n"
        "    result=original_read(root,path)\n"
        "    if not changed:\n"
        "        changed=True\n"
        f"        alias=pathlib.Path({str(alias)!r})\n"
        f"        alias.unlink();alias.symlink_to(pathlib.Path({str(elsewhere)!r}),target_is_directory=True)\n"
        f"        pathlib.Path({str(marker)!r}).write_text('true')\n"
        "    return result\n"
        "m._read_candidate_file=change_after_read\n"
    )
    if mutant == "skip-target-guard":
        setup += (
            "original_verify=m._verify_candidate_routing\n"
            "def skip_symlink_target(context):\n"
            "    symlinks=context.symlinks;context.symlinks=[]\n"
            "    try: return original_verify(context)\n"
            "    finally: context.symlinks=symlinks\n"
            "m._verify_candidate_routing=skip_symlink_target\n"
        )
    elif mutant == "length-only-guard":
        setup += _all_gaps_mutation(
            "_verify_candidate_routing",
            "_candidate_readlink(symlink.parent, symlink.name, symlink.state)\n                != symlink.target",
            "len(_candidate_readlink(symlink.parent, symlink.name, symlink.state))\n                != len(symlink.target)",
        )
    result = _repair_scan(repo, setup)
    assert json.loads(marker.read_text()) is True
    if mutant != "control":
        assert result[0] == 1 and has(result[1], "literal-assignment", "config.txt")
    else:
        _input_expected_error(result, "UNSUPPORTED_ENTRY")
