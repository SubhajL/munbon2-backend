"""Fail-closed local scanning of selected Git-tracked bytes."""

from __future__ import annotations

import errno
import json
import os
from pathlib import Path
import re
import selectors
import stat
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Iterable


MAX_BLOB_SIZE = 16 * 1024 * 1024
MAX_GIT_OUTPUT = 64 * 1024 * 1024
GIT_TIMEOUT_SECONDS = 20.0
POLICY_PATH = ".github/workflows/secret-scan.yml"
BASELINE_PATH = ".security/full-tree-baseline.txt"
VALID_MODES = {"100644", "100755"}
REF_PATTERN = re.compile(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})\Z")
SECRET_NAME_SUFFIX = (
    r"(?:password|passwd|pwd|secret|token|api[_-]?key|apikey|access[_-]?key)"
)
SECRET_SUFFIX_PATTERN = re.compile(SECRET_NAME_SUFFIX + r"\Z", re.IGNORECASE)
IDENTIFIER_PATTERN = r"[A-Za-z_][A-Za-z0-9_-]*"
KEY_END_PATTERN = r"(?(key_quote)(?P=key_quote))\s*\]?\s*(?:=|:)\s*"
KEY_START_PATTERN = (
    r"(?<![A-Za-z0-9_-])(?P<key_quote>[\"'])?(?P<key>"
    + IDENTIFIER_PATTERN
    + r")"
    + KEY_END_PATTERN
)
QUOTED_CONTENT_PATTERN = r"(?:\\.|(?!(?P=quote))[^\\])*"
QUOTED_VALUE_PATTERN = (
    r'(?P<quote>["\'])(?P<value>' + QUOTED_CONTENT_PATTERN + r")(?P=quote)"
)
ASSIGNMENT_VALUE_PATTERN = (
    r'(?P<quote>["\'])(?P<quoted>' + QUOTED_CONTENT_PATTERN + r")(?P=quote)"
)
ASSIGNMENT_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_-])(?P<key_quote>[\"'])?"
    r"(?P<key>(?:[A-Za-z_][A-Za-z0-9_-]*)?"
    + SECRET_NAME_SUFFIX
    + r")"
    + KEY_END_PATTERN
    + r"(?:"
    + ASSIGNMENT_VALUE_PATTERN
    + r"|(?P<bare>\$\{[A-Za-z_][A-Za-z0-9_]*\}(?=$|[\s,;}])|[^\s,;}]+))",
    re.IGNORECASE,
)
DEFAULT_VALUE_PATTERN = (
    r"(?:"
    + QUOTED_VALUE_PATTERN
    + r"|(?P<variable>[A-Za-z_][A-Za-z0-9_]*)(?![A-Za-z0-9_]|\s*[:=]))"
)
PYTHON_FALLBACK_PATTERN = re.compile(
    KEY_START_PATTERN + r"os\.(?:getenv|environ\.get)\(\s*"
    r'(?P<env_quote>["\'])(?P<env>[A-Za-z_][A-Za-z0-9_]*)'
    r"(?P=env_quote)\s*,\s*" + DEFAULT_VALUE_PATTERN + r"\s*\)"
)
PYTHON_OR_FALLBACK_PATTERN = re.compile(
    KEY_START_PATTERN + r"os\.(?:(?P<call>getenv|environ\.get)\(\s*|environ\[\s*)"
    r'(?P<env_quote>["\'])(?P<env>[A-Za-z_][A-Za-z0-9_]*)'
    r"(?P=env_quote)\s*(?(call)\)|\])\s*or\b\s*" + DEFAULT_VALUE_PATTERN
)
JAVASCRIPT_FALLBACK_PATTERN = re.compile(
    KEY_START_PATTERN + r"process\.env\.(?P<env>[A-Za-z_][A-Za-z0-9_]*)\s*"
    r"(?:\|\||\?\?)\s*" + DEFAULT_VALUE_PATTERN
)
JAVASCRIPT_TERMINATOR_PATTERN = re.compile(r"\s*(?:[,;}]|\Z)")
_CERTIFICATE_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_CERTIFICATE_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*")
_CERTIFICATE_HORIZONTAL = re.compile(r"[ \t]*")
_CERTIFICATE_VISIBLE = re.compile(r"[\t\x20-\x7e]*")
_CERTIFICATE_VALUE = re.compile(r"[A-Za-z0-9_.@<>\[\]-]*")
_CERTIFICATE_OPTION = re.compile(r"[A-Za-z0-9_-]+")
SHELL_FALLBACK_PATTERN = re.compile(
    KEY_START_PATTERN + r'(?P<outer_quote>["\'])?'
    r"\$\{(?P<env>[A-Za-z_][A-Za-z0-9_]*)(?P<operator>:-|-)"
    r"(?P<value>[^}\r\n]*)\}(?(outer_quote)(?P=outer_quote))"
)
SQL_PASSWORD_PATTERN = re.compile(
    r"\b" + SECRET_NAME_SUFFIX + r"\s+" + QUOTED_VALUE_PATTERN, re.IGNORECASE
)
CLI_SECRET_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_-])(?:(?i:--" + SECRET_NAME_SUFFIX + r")|-P)"
    r"(?:=|\s+)(?:" + ASSIGNMENT_VALUE_PATTERN + r"|(?P<bare>[^\s,;]+))"
)
URL_PATTERN = re.compile(
    r"(?<![A-Za-z0-9+._-])[a-z][a-z0-9+.-]*://"
    r"(?P<user>[^:/@\s]*):(?P<password>[^/@\s]+)@",
    re.IGNORECASE,
)
FILENAME_ASSIGNMENT_PATTERN = re.compile(
    r"(?:^|/)[^/]*" + SECRET_NAME_SUFFIX + r"[\"']?\s*\]?\s*[:=]", re.IGNORECASE
)
LITERAL_CONTINUATION_PATTERN = re.compile(
    r"\s*(?:\+|\*|%|\.|\[|\(|\?|&&|\|\||\b(?:or|and|if|else)\b|[\"'])"
)
AWS_PATTERN = re.compile(r"AKIA[0-9A-Z]{16}")
PRIVATE_KEY_PATTERN = re.compile(r"BEGIN [A-Z ]*PRIVATE KEY")
SENTINELS = {"REDACTED", "__REDACTED__", "[REDACTED]", "<REDACTED>"}
PLACEHOLDERS = {
    "password",
    "postgres",
    "test",
    "test-password",
    "dummy",
    "example",
    "changeme",
}


class ScanFailure(Exception):
    """An internal failure represented by a controlled public error code."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class GitResult:
    """The bounded result of one local Git command."""

    returncode: int
    stdout: bytes


@dataclass(frozen=True)
class Entry:
    """One raw Git index or tree entry."""

    mode: str
    object_id: str
    kind: str
    supported: bool


@dataclass(frozen=True)
class Policy:
    """The private literal policy and approved baseline paths."""

    legacy_password: str
    legacy_host: str
    approved_baseline: frozenset[str]


@dataclass(frozen=True, order=True)
class Finding:
    """A safe, deterministic finding without source content."""

    file: str
    line: int
    rule: str
    classification: str
    status: str


@dataclass(frozen=True)
class ParsedArguments:
    """Validated command-line shape before repository-dependent validation."""

    repo: str
    policy_ref: str
    mode: str
    ref: str | None
    base: str | None
    head: str | None


def _git_environment() -> dict[str, str]:
    """Return a Git environment without inherited Git override variables."""

    environment = {
        key: value for key, value in os.environ.items() if not key.startswith("GIT_")
    }
    environment.update(
        {
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_SYSTEM": os.devnull,
            "GIT_NO_LAZY_FETCH": "1",
            "GIT_NO_REPLACE_OBJECTS": "1",
            "GIT_PAGER": "cat",
            "GIT_TERMINAL_PROMPT": "0",
            "LC_ALL": "C",
            "LANG": "C",
        }
    )
    return environment


def _git_command(
    root: Path,
    arguments: list[str],
    *,
    max_stdout: int = MAX_GIT_OUTPUT,
    allowed_returncodes: tuple[int, ...] = (0,),
) -> GitResult:
    """Run one bounded, non-shell Git command and hide its diagnostics."""

    command = [
        "git",
        "--no-replace-objects",
        "-c",
        "core.fsmonitor=false",
        "-c",
        "diff.external=",
        "-c",
        "diff.renames=false",
        "-C",
        str(root),
        *arguments,
    ]
    try:
        process = subprocess.Popen(
            command,
            cwd=str(root),
            env=_git_environment(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as exc:
        raise ScanFailure("GIT_FAILURE") from exc

    assert process.stdout is not None
    assert process.stderr is not None
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ, "stdout")
    selector.register(process.stderr, selectors.EVENT_READ, "stderr")
    stdout = bytearray()
    deadline = time.monotonic() + GIT_TIMEOUT_SECONDS

    try:
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                process.kill()
                process.wait()
                raise ScanFailure("GIT_FAILURE")
            events = selector.select(remaining)
            if not events:
                process.kill()
                process.wait()
                raise ScanFailure("GIT_FAILURE")
            for key, _ in events:
                stream = key.fileobj
                try:
                    chunk = os.read(stream.fileno(), 65536)
                except OSError as exc:
                    process.kill()
                    process.wait()
                    raise ScanFailure("GIT_FAILURE") from exc
                if not chunk:
                    selector.unregister(stream)
                    continue
                if key.data == "stdout":
                    if len(stdout) + len(chunk) > max_stdout:
                        process.kill()
                        process.wait()
                        raise ScanFailure("INPUT_TOO_LARGE")
                    stdout.extend(chunk)
        process.wait()
    finally:
        selector.close()
        if process.poll() is None:
            process.kill()
            process.wait()
        process.stdout.close()
        process.stderr.close()

    if process.returncode not in allowed_returncodes:
        raise ScanFailure("GIT_FAILURE")
    return GitResult(process.returncode, bytes(stdout))


def _parse_arguments(argv: list[str] | None) -> ParsedArguments | None:
    """Parse the exact public CLI without exposing parser diagnostics."""

    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments == ["--help"]:
        sys.stdout.write(
            "usage: scan_tracked_secrets.py --repo ROOT --policy-ref COMMIT "
            "--mode {candidate,index,tree,range} "
            "[--ref COMMIT | --base COMMIT --head COMMIT]\n"
        )
        return None

    option_names = {"--repo", "--policy-ref", "--mode", "--ref", "--base", "--head"}
    values: dict[str, str] = {}
    index = 0
    while index < len(arguments):
        option = arguments[index]
        if option not in option_names or index + 1 >= len(arguments):
            raise ScanFailure("INVALID_ARGUMENT")
        value = arguments[index + 1]
        if value.startswith("-") or option in values:
            raise ScanFailure("INVALID_ARGUMENT")
        values[option] = value
        index += 2

    required = {"--repo", "--policy-ref", "--mode"}
    if required - set(values):
        raise ScanFailure("INVALID_ARGUMENT")
    mode = values["--mode"]
    if mode not in {"candidate", "index", "tree", "range"}:
        raise ScanFailure("INVALID_ARGUMENT")

    selectors = set(values) - required
    if mode == "tree":
        if selectors != {"--ref"}:
            raise ScanFailure("INVALID_ARGUMENT")
    elif mode == "range":
        if selectors != {"--base", "--head"}:
            raise ScanFailure("INVALID_ARGUMENT")
    elif selectors:
        raise ScanFailure("INVALID_ARGUMENT")

    return ParsedArguments(
        repo=values["--repo"],
        policy_ref=values["--policy-ref"],
        mode=mode,
        ref=values.get("--ref"),
        base=values.get("--base"),
        head=values.get("--head"),
    )


def _validate_repository(repository: str) -> Path:
    """Require the supplied path to be the exact Git top-level directory."""

    try:
        root = Path(repository).resolve()
    except OSError as exc:
        raise ScanFailure("INVALID_REPOSITORY") from exc
    if not root.is_dir():
        raise ScanFailure("INVALID_REPOSITORY")

    result = _git_command(
        root,
        ["rev-parse", "--show-toplevel"],
        max_stdout=4096,
        allowed_returncodes=(0, 1, 128),
    )
    if result.returncode != 0:
        raise ScanFailure("INVALID_REPOSITORY")
    try:
        git_root = Path(result.stdout.decode("utf-8").strip()).resolve()
    except (OSError, UnicodeDecodeError) as exc:
        raise ScanFailure("INVALID_REPOSITORY") from exc
    if git_root != root:
        raise ScanFailure("INVALID_REPOSITORY")
    return root


def _validate_commit(root: Path, object_id: str) -> str:
    """Require a full, nonzero commit object ID."""

    if not REF_PATTERN.fullmatch(object_id) or set(object_id) == {"0"}:
        raise ScanFailure("INVALID_REF")
    result = _git_command(
        root,
        ["cat-file", "-t", object_id],
        max_stdout=128,
        allowed_returncodes=(0, 1, 128),
    )
    if result.returncode != 0 or result.stdout.strip() != b"commit":
        raise ScanFailure("INVALID_REF")
    return object_id


def _parse_tree_entries(raw: bytes, *, strict: bool) -> dict[str, Entry]:
    """Parse NUL-delimited raw recursive tree output."""

    entries: dict[str, Entry] = {}
    for record in raw.split(b"\0"):
        if not record:
            continue
        try:
            metadata, path_bytes = record.split(b"\t", 1)
            mode_bytes, kind_bytes, object_id_bytes = metadata.split(b" ", 2)
            path = path_bytes.decode("utf-8")
            mode = mode_bytes.decode("ascii")
            kind = kind_bytes.decode("ascii")
            object_id = object_id_bytes.decode("ascii")
        except (ValueError, UnicodeDecodeError) as exc:
            raise ScanFailure("UNSUPPORTED_ENTRY") from exc
        if (
            not path
            or path.startswith("/")
            or "\x00" in path
            or any(part in {"", ".", ".."} for part in path.split("/"))
            or not REF_PATTERN.fullmatch(object_id)
        ):
            raise ScanFailure("UNSUPPORTED_ENTRY")
        supported = kind == "blob" and mode in VALID_MODES
        if strict and not supported:
            raise ScanFailure("UNSUPPORTED_ENTRY")
        if path in entries:
            raise ScanFailure("UNSUPPORTED_ENTRY")
        entries[path] = Entry(mode, object_id, kind, supported)
    return entries


def _tree_entries(root: Path, commit: str, *, strict: bool) -> dict[str, Entry]:
    """Return raw leaf entries from a commit tree."""

    result = _git_command(
        root,
        ["ls-tree", "-r", "-z", "--full-tree", commit],
        max_stdout=MAX_GIT_OUTPUT,
    )
    return _parse_tree_entries(result.stdout, strict=strict)


def _parse_index_entries(raw: bytes) -> dict[str, Entry]:
    """Parse every index stage and reject unmerged or unsupported entries."""

    entries: dict[str, Entry] = {}
    for record in raw.split(b"\0"):
        if not record:
            continue
        try:
            metadata, path_bytes = record.split(b"\t", 1)
            mode_bytes, object_id_bytes, stage_bytes = metadata.split(b" ", 2)
            path = path_bytes.decode("utf-8")
            mode = mode_bytes.decode("ascii")
            object_id = object_id_bytes.decode("ascii")
            stage = int(stage_bytes)
        except (ValueError, UnicodeDecodeError) as exc:
            raise ScanFailure("UNSUPPORTED_ENTRY") from exc
        if (
            not path
            or path.startswith("/")
            or "\x00" in path
            or any(part in {"", ".", ".."} for part in path.split("/"))
            or not REF_PATTERN.fullmatch(object_id)
            or stage != 0
            or mode not in VALID_MODES
        ):
            raise ScanFailure("UNSUPPORTED_ENTRY")
        if path in entries:
            raise ScanFailure("UNSUPPORTED_ENTRY")
        entries[path] = Entry(mode, object_id, "blob", True)
    return entries


def _index_entries(root: Path) -> dict[str, Entry]:
    """Return all stage-zero index entries after fail-closed validation."""

    result = _git_command(root, ["ls-files", "--stage", "--full-name", "-z"])
    return _parse_index_entries(result.stdout)


def _read_blob(root: Path, object_id: str) -> bytes:
    """Read one raw Git blob with the contract's size bound."""

    result = _git_command(
        root, ["cat-file", "blob", object_id], max_stdout=MAX_BLOB_SIZE
    )
    return result.stdout


def _decode_scan_bytes(data: bytes) -> str:
    """Decode one scan input as strict UTF-8, retaining NUL characters."""

    if len(data) > MAX_BLOB_SIZE:
        raise ScanFailure("INPUT_TOO_LARGE")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ScanFailure("UNSUPPORTED_ENCODING") from exc
    if text.startswith("\ufeff"):
        text = text[1:]
    return text


def _decode_policy_bytes(data: bytes) -> str:
    """Decode policy material without allowing scanner input fallbacks."""

    if len(data) > MAX_BLOB_SIZE:
        raise ScanFailure("INVALID_POLICY")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ScanFailure("INVALID_POLICY") from exc
    if text.startswith("\ufeff"):
        text = text[1:]
    if "\x00" in text:
        raise ScanFailure("INVALID_POLICY")
    return text


def _parse_quoted_assignment(line: str, name: str) -> str:
    """Join inert adjacent single-quoted assignment segments, never evaluate."""

    match = re.fullmatch(re.escape(name) + r"=((?:'[^'\r\n]*')+)", line)
    if match is None:
        raise ScanFailure("INVALID_POLICY")
    value = "".join(re.findall(r"'([^'\r\n]*)'", match.group(1)))
    if not value:
        raise ScanFailure("INVALID_POLICY")
    return value


def _parse_policy(text: str) -> tuple[str, str]:
    """Parse the approved inert legacy grammar and nothing else."""

    passwords: list[str] = []
    hosts: list[str] = []
    hard_lines: list[str] = []
    for raw_line in text.split("\n"):
        line = raw_line.rstrip("\r").strip()
        if "pw=" in line:
            passwords.append(_parse_quoted_assignment(line, "pw"))
        if "ip=" in line:
            hosts.append(_parse_quoted_assignment(line, "ip"))
        if "hard=" in line:
            hard_lines.append(line)

    expected_hard = 'hard="($pw|$ip|AKIA[0-9A-Z]{16}|BEGIN [A-Z ]*PRIVATE KEY)"'
    if (
        len(passwords) != 2
        or len(set(passwords)) != 1
        or len(hosts) != 2
        or not hosts[1]
        or hosts[0] != re.escape(hosts[1])
        or len(hard_lines) != 1
        or hard_lines[0] != expected_hard
    ):
        raise ScanFailure("INVALID_POLICY")
    return passwords[0], hosts[1]


def _parse_baseline(data: bytes) -> frozenset[str]:
    """Parse exact safe relative baseline paths."""

    text = _decode_policy_bytes(data)
    paths: set[str] = set()
    for raw_line in text.split("\n"):
        line = raw_line.rstrip("\r")
        if not line or line.startswith("#"):
            continue
        if (
            line.startswith("/")
            or "\\" in line
            or "\x00" in line
            or any(part in {"", ".", ".."} for part in line.split("/"))
        ):
            raise ScanFailure("INVALID_POLICY")
        if line in paths:
            raise ScanFailure("INVALID_POLICY")
        paths.add(line)
    return frozenset(paths)


def _baseline_from_entries(root: Path, entries: dict[str, Entry]) -> frozenset[str]:
    """Load a selected baseline, treating a missing carrier as empty."""

    entry = entries.get(BASELINE_PATH)
    if entry is None:
        return frozenset()
    if not entry.supported:
        raise ScanFailure("INVALID_POLICY")
    try:
        data = _read_blob(root, entry.object_id)
    except ScanFailure as exc:
        raise ScanFailure("INVALID_POLICY") from exc
    return _parse_baseline(data)


def _load_policy(root: Path, policy_ref: str) -> Policy:
    """Load policy and approved baseline only from the immutable policy commit."""

    entries = _tree_entries(root, policy_ref, strict=False)
    policy_entry = entries.get(POLICY_PATH)
    baseline_entry = entries.get(BASELINE_PATH)
    if (
        policy_entry is None
        or not policy_entry.supported
        or baseline_entry is None
        or not baseline_entry.supported
    ):
        raise ScanFailure("INVALID_POLICY")
    try:
        policy_bytes = _read_blob(root, policy_entry.object_id)
        baseline_bytes = _read_blob(root, baseline_entry.object_id)
    except ScanFailure as exc:
        raise ScanFailure("INVALID_POLICY") from exc
    legacy_password, legacy_host = _parse_policy(_decode_policy_bytes(policy_bytes))
    approved = _parse_baseline(baseline_bytes)
    return Policy(legacy_password, legacy_host, approved)


def _read_fd_limited(file_descriptor: int) -> bytes:
    """Read a regular file descriptor without crossing the blob limit."""

    chunks: list[bytes] = []
    total = 0
    try:
        while True:
            chunk = os.read(file_descriptor, min(65536, MAX_BLOB_SIZE + 1 - total))
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_BLOB_SIZE:
                raise ScanFailure("INPUT_TOO_LARGE")
            chunks.append(chunk)
    except ScanFailure:
        raise
    except OSError as exc:
        raise ScanFailure("INPUT_UNREADABLE") from exc
    return b"".join(chunks)


def _read_candidate_file(root: Path, path: str) -> bytes | None:
    """Read a tracked worktree path without following any component symlink."""

    parts = path.split("/")
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise ScanFailure("UNSUPPORTED_ENTRY")
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    directory_flag = getattr(os, "O_DIRECTORY", 0)
    descriptors: list[int] = []
    try:
        try:
            current = os.open(root, os.O_RDONLY | directory_flag | nofollow)
        except FileNotFoundError:
            raise ScanFailure("INVALID_REPOSITORY")
        except OSError as exc:
            raise ScanFailure("INPUT_UNREADABLE") from exc
        descriptors.append(current)
        for component in parts[:-1]:
            try:
                current = os.open(
                    component,
                    os.O_RDONLY | directory_flag | nofollow,
                    dir_fd=current,
                )
            except FileNotFoundError:
                return None
            except OSError as exc:
                if exc.errno in {errno.ELOOP, errno.ENOTDIR}:
                    raise ScanFailure("UNSUPPORTED_ENTRY") from exc
                if exc.errno in {errno.EACCES, errno.EPERM}:
                    raise ScanFailure("INPUT_UNREADABLE") from exc
                raise ScanFailure("INPUT_UNREADABLE") from exc
            descriptors.append(current)
        try:
            final_descriptor = os.open(
                parts[-1], os.O_RDONLY | nofollow | os.O_NONBLOCK, dir_fd=current
            )
        except FileNotFoundError:
            return None
        except OSError as exc:
            if exc.errno in {errno.ELOOP, errno.ENOTDIR}:
                raise ScanFailure("UNSUPPORTED_ENTRY") from exc
            if exc.errno in {errno.EACCES, errno.EPERM}:
                raise ScanFailure("INPUT_UNREADABLE") from exc
            raise ScanFailure("INPUT_UNREADABLE") from exc
        descriptors.append(final_descriptor)
        try:
            file_stat = os.fstat(final_descriptor)
        except OSError as exc:
            raise ScanFailure("INPUT_UNREADABLE") from exc
        if not stat.S_ISREG(file_stat.st_mode):
            raise ScanFailure("UNSUPPORTED_ENTRY")
        if file_stat.st_size > MAX_BLOB_SIZE:
            raise ScanFailure("INPUT_TOO_LARGE")
        return _read_fd_limited(final_descriptor)
    finally:
        for descriptor in reversed(descriptors):
            try:
                os.close(descriptor)
            except OSError:
                pass


def _read_index_snapshot(root: Path) -> dict[str, bytes]:
    """Read stage-zero tracked index blobs."""

    entries = _index_entries(root)
    return {
        path: _read_blob(root, entry.object_id)
        for path, entry in sorted(entries.items())
    }


def _read_tree_snapshot(root: Path, ref: str) -> dict[str, bytes]:
    """Read every regular blob in one commit tree."""

    entries = _tree_entries(root, ref, strict=True)
    return {
        path: _read_blob(root, entry.object_id)
        for path, entry in sorted(entries.items())
    }


def _read_candidate_snapshot(root: Path) -> dict[str, bytes]:
    """Read current bytes only for stage-zero tracked regular paths."""

    entries = _index_entries(root)
    snapshot: dict[str, bytes] = {}
    for path in sorted(entries):
        data = _read_candidate_file(root, path)
        if data is not None:
            snapshot[path] = data
    return snapshot


def _is_secret_identifier(identifier: str) -> bool:
    """Return whether a key ends in one of the credential suffixes."""

    return bool(SECRET_SUFFIX_PATTERN.search(identifier.strip("\"'")))


def _is_test_file(path: str) -> bool:
    """Return whether the exact test-placeholder allowance applies."""

    if "tests" not in path.split("/"):
        return False
    name = path.rsplit("/", 1)[-1]
    return (name.startswith("test_") and name.endswith(".py")) or bool(
        re.fullmatch(r".*\.(?:test|spec)\.(?:js|ts)", name)
    )


def _value_disposition(path: str, value: str) -> tuple[str, str]:
    """Map a detected literal to its safe classification and status."""

    if value in SENTINELS:
        return "redaction-sentinel", "allowed"
    if value in PLACEHOLDERS and _is_test_file(path):
        return "test-placeholder", "allowed"
    return "credential-candidate", "blocked"


def _is_environment_only(value: str) -> bool:
    """Recognize values that contain only an environment lookup."""

    candidate = value.strip()
    return bool(
        re.fullmatch(
            r"(?:\$[A-Za-z_][A-Za-z0-9_]*|\$\{[A-Za-z_][A-Za-z0-9_]*\})", candidate
        )
        or re.fullmatch(r'os\.environ\[\s*["\'][^"\']+["\']\s*\]', candidate)
        or re.fullmatch(r'os\.getenv\(\s*["\'][^"\']+["\']\s*\)', candidate)
        or re.fullmatch(r'os\.environ\.get\(\s*["\'][^"\']+["\']\s*\)', candidate)
        or re.fullmatch(r"process\.env\.[A-Za-z_][A-Za-z0-9_]*", candidate)
    )


def _assignment_value(match: re.Match[str]) -> str:
    """Return the quoted or bare value from an assignment match."""

    value = match.group("quoted")
    if value is None:
        value = match.group("bare")
    return value or ""


def _literal_views(line: str) -> tuple[str, ...]:
    """Inspect raw text and one quote-unescaped view without erasing raw evidence."""

    normalized = line.replace(r"\"", '"').replace(r"\'", "'")
    return (line,) if normalized == line else (line, normalized)


def _has_literal_continuation(line: str, end: int) -> bool:
    """Adjacent token characters and composition operators are not standalone values."""

    if end < len(line) and not line[end].isspace() and line[end] not in ",;})]":
        return True
    return bool(LITERAL_CONTINUATION_PATTERN.match(line, end))


def _literal_disposition(path: str, value: str, line: str, end: int) -> tuple[str, str]:
    """Only standalone exact markers may be allowed as literal values."""

    if _has_literal_continuation(line, end):
        return "credential-candidate", "blocked"
    return _value_disposition(path, value)


def _fallback_matches(line: str) -> list[tuple[str | None, int, int, bool]]:
    """Return recognized defaults, view spans, and JavaScript origin."""

    matches: list[tuple[str | None, int, int, bool]] = []
    for pattern in (
        PYTHON_FALLBACK_PATTERN,
        PYTHON_OR_FALLBACK_PATTERN,
        JAVASCRIPT_FALLBACK_PATTERN,
        SHELL_FALLBACK_PATTERN,
    ):
        for match in pattern.finditer(line):
            if not (
                _is_secret_identifier(match.group("key"))
                or _is_secret_identifier(match.group("env"))
            ):
                continue
            matches.append(
                (
                    match.group("value"),
                    match.start(),
                    match.end(),
                    pattern is JAVASCRIPT_FALLBACK_PATTERN,
                )
            )
    return matches


def _certificate_horizontal_end(line: str, start: int) -> int:
    return _CERTIFICATE_HORIZONTAL.match(line, start).end()


def _certificate_quote_end(line: str, start: int) -> int | None:
    if start >= len(line) or line[start] not in "\"'":
        return None
    end = _CERTIFICATE_VALUE.match(line, start + 1).end()
    if end >= len(line) or line[end] != line[start]:
        return None
    return end + 1


def _certificate_call(line: str, start: int) -> tuple[int, tuple[int, int]] | None:
    name = _CERTIFICATE_NAME.match(line, start)
    if name is None:
        return None
    opening = _certificate_horizontal_end(line, name.end())
    if opening >= len(line) or line[opening] != "(":
        return None
    body = _certificate_horizontal_end(line, opening + 1)
    key = _CERTIFICATE_IDENTIFIER.match(line, body)
    if key is None:
        return None
    separator = _certificate_horizontal_end(line, key.end())
    if separator >= len(line) or line[separator] != "=":
        return None
    env_start = _certificate_horizontal_end(line, separator + 1)
    prefix = "process.env."
    if not line.startswith(prefix, env_start):
        return None
    env = _CERTIFICATE_IDENTIFIER.match(line, env_start + len(prefix))
    if env is None:
        return None
    operator = _certificate_horizontal_end(line, env.end())
    if line[operator : operator + 2] not in ("||", "??"):
        return None
    value_start = _certificate_horizontal_end(line, operator + 2)
    if value_start < len(line) and line[value_start] in "\"'":
        value_end = _certificate_quote_end(line, value_start)
    else:
        variable = _CERTIFICATE_IDENTIFIER.match(line, value_start)
        value_end = variable.end() if variable is not None else None
    if value_end is None:
        return None
    closing = _certificate_horizontal_end(line, value_end)
    if closing >= len(line) or line[closing] != ")":
        return None
    fallback = JAVASCRIPT_FALLBACK_PATTERN.match(line, body)
    if (
        fallback is None
        or fallback.group("key_quote") is not None
        or fallback.span("key") != key.span()
        or fallback.span("env") != env.span()
        or fallback.end() != value_end
        or not (
            _is_secret_identifier(fallback.group("key"))
            or _is_secret_identifier(fallback.group("env"))
        )
    ):
        return None
    return closing + 1, fallback.span()


def _certificate_assignment(line: str, start: int, *, declaration: bool) -> int | None:
    key = _CERTIFICATE_IDENTIFIER.match(line, start)
    if key is None:
        return None
    if declaration and key.group() in {"const", "let", "var"}:
        next_start = _certificate_horizontal_end(line, key.end())
        if next_start == key.end():
            return None
        key = _CERTIFICATE_IDENTIFIER.match(line, next_start)
        if key is None:
            return None
    if not _is_secret_identifier(key.group()):
        return None
    equals = _certificate_horizontal_end(line, key.end())
    if equals >= len(line) or line[equals] != "=":
        return None
    quote = _certificate_horizontal_end(line, equals + 1)
    end = _certificate_quote_end(line, quote)
    if end is None:
        return None
    owner = ASSIGNMENT_PATTERN.match(line, key.start())
    if (
        owner is None
        or owner.span("key") != key.span()
        or owner.end() != end
        or owner.span("quoted") != (quote + 1, end - 1)
    ):
        return None
    return end


def _certificate_other(line: str, start: int) -> int | None:
    assignment_end = _certificate_assignment(line, start, declaration=False)
    if assignment_end is not None:
        return assignment_end

    word = _CERTIFICATE_IDENTIFIER.match(line, start)
    if word is None:
        return None
    word_count = 1
    while True:
        next_start = _certificate_horizontal_end(line, word.end())
        if next_start == word.end() or next_start >= len(line):
            return None
        if line[next_start] == "-":
            option = _CERTIFICATE_OPTION.match(line, next_start)
            if option is None:
                return None
            separator = option.end()
            if separator < len(line) and line[separator] == "=":
                quote = separator + 1
            else:
                quote = _certificate_horizontal_end(line, separator)
                if quote == separator:
                    return None
            end = _certificate_quote_end(line, quote)
            if end is None:
                return None
            owner = CLI_SECRET_PATTERN.match(line, next_start)
            value_group = "quoted"
            break
        if line[next_start] in "\"'":
            if word_count < 2:
                return None
            quote = next_start
            end = _certificate_quote_end(line, quote)
            if end is None:
                return None
            owner = SQL_PASSWORD_PATTERN.match(line, word.start())
            value_group = "value"
            break
        word = _CERTIFICATE_IDENTIFIER.match(line, next_start)
        if word is None:
            return None
        word_count += 1

    if owner is None or owner.start("quote") != quote:
        return None
    if owner.end() != end or owner.span(value_group) != (quote + 1, end - 1):
        return None
    return end


def _certificate_single_line(line: str) -> tuple[int, int] | None:
    start = _certificate_horizontal_end(line, 0)
    call = _certificate_call(line, start)
    if call is None:
        other_end = _certificate_other(line, start)
        if other_end is None:
            return None
        separator = _certificate_horizontal_end(line, other_end)
        if separator >= len(line) or line[separator] != ";":
            return None
        call = _certificate_call(line, _certificate_horizontal_end(line, separator + 1))
        if call is None:
            return None
        call_end, span = call
        separator = _certificate_horizontal_end(line, call_end)
        if separator >= len(line) or line[separator] != ";":
            return None
        return (
            span
            if _certificate_horizontal_end(line, separator + 1) == len(line)
            else None
        )

    call_end, span = call
    tail = _certificate_horizontal_end(line, call_end)
    if tail == len(line):
        return span
    if line[tail] == ";":
        other_start = _certificate_horizontal_end(line, tail + 1)
        if other_start == len(line):
            return span
        other_end = _certificate_other(line, other_start)
        if other_end is None:
            return None
        tail = _certificate_horizontal_end(line, other_end)
        if tail < len(line) and line[tail] == ";":
            tail = _certificate_horizontal_end(line, tail + 1)
        return span if tail == len(line) else None
    if tail != call_end:
        return None
    if line[tail] == ",":
        identifier = _CERTIFICATE_IDENTIFIER.match(
            line, _certificate_horizontal_end(line, tail + 1)
        )
        if identifier is not None and _certificate_horizontal_end(
            line, identifier.end()
        ) == len(line):
            return span
    elif line[tail] == "}":
        tail = _certificate_horizontal_end(line, tail + 1)
        if tail < len(line) and line[tail] == ";":
            tail = _certificate_horizontal_end(line, tail + 1)
        if tail == len(line):
            return span
    return None


def _certificate_multiline_line(line: str) -> tuple[tuple[int, int], ...] | None:
    start = _certificate_horizontal_end(line, 0)
    call = _certificate_call(line, start)
    if call is None:
        end = _certificate_assignment(line, start, declaration=True)
        spans: tuple[tuple[int, int], ...] = ()
    else:
        end, span = call
        spans = (span,)
    if end is None:
        return None
    end = _certificate_horizontal_end(line, end)
    if end >= len(line) or line[end] != ";":
        return None
    return spans if _certificate_horizontal_end(line, end + 1) == len(line) else None


def _javascript_duplicate_contexts(text: str) -> dict[int, frozenset[tuple[int, int]]]:
    """Certify only the closed whole-blob grammar for raw JavaScript spans."""

    proofs: dict[int, frozenset[tuple[int, int]]] = {}
    content_count = 0
    first_line = 0
    single_span: tuple[int, int] | None = None
    multiline_valid = True
    start = 0
    line_number = 1
    while True:
        newline = text.find("\n", start)
        raw_line = text[start:] if newline < 0 else text[start:newline]
        line = raw_line[:-1] if raw_line.endswith("\r") else raw_line
        if _CERTIFICATE_VISIBLE.fullmatch(line) is None:
            return {}
        if line.strip(" \t"):
            content_count += 1
            if content_count == 1:
                first_line = line_number
                single_span = _certificate_single_line(line)
            elif not multiline_valid:
                return {}
            spans = _certificate_multiline_line(line)
            if spans is None:
                multiline_valid = False
                if content_count > 1 or single_span is None:
                    return {}
            elif spans:
                proofs[line_number] = frozenset(spans)
        if newline < 0:
            break
        start = newline + 1
        line_number += 1

    if content_count == 1:
        return (
            {first_line: frozenset((single_span,))} if single_span is not None else {}
        )
    return proofs if multiline_valid else {}


def _filename_is_sensitive(path: str, legacy_password: str) -> bool:
    """Redact every recognizable credential shape before serializing its path."""

    if legacy_password and legacy_password in path:
        return True
    for view in _literal_views(path):
        if _fallback_matches(view) or any(
            pattern.search(view)
            for pattern in (
                FILENAME_ASSIGNMENT_PATTERN,
                ASSIGNMENT_PATTERN,
                URL_PATTERN,
                SQL_PASSWORD_PATTERN,
                CLI_SECRET_PATTERN,
                AWS_PATTERN,
                PRIVATE_KEY_PATTERN,
            )
        ):
            return True
    return False


def _finding(
    path: str,
    line_number: int,
    rule: str,
    classification: str,
    status: str,
    legacy_password: str,
) -> Finding:
    """Construct one finding with filename redaction applied."""

    report_path = (
        "[redacted-path]" if _filename_is_sensitive(path, legacy_password) else path
    )
    return Finding(report_path, line_number, rule, classification, status)


def _uncovered_matches(
    pattern: re.Pattern[str], line: str, spans: list[tuple[int, int]]
) -> Iterable[re.Match[str]]:
    """Skip only matches fully inside a sorted fallback span, without erasing text."""

    cursor = 0
    covered_end = -1
    for match in pattern.finditer(line):
        while cursor < len(spans) and spans[cursor][0] <= match.start():
            covered_end = max(covered_end, spans[cursor][1])
            cursor += 1
        if match.end() > covered_end:
            yield match


def _classify_literal_view(
    path: str,
    line: str,
    line_number: int,
    policy: Policy,
    *,
    certified_spans: frozenset[tuple[int, int]],
) -> set[Finding]:
    """Classify original text, deduplicating only fully covered fallback matches."""

    findings: set[Finding] = set()
    fallbacks = _fallback_matches(line)
    spans = sorted((start, end) for _, start, end, _ in fallbacks)
    javascript_spans = {
        (start, end) for _, start, end, javascript in fallbacks if javascript
    }
    for value, start, end, _ in fallbacks:
        if value or _has_literal_continuation(line, end):
            classification, status = _literal_disposition(path, value or "", line, end)
            findings.add(
                _finding(
                    path,
                    line_number,
                    "environment-fallback",
                    classification,
                    status,
                    policy.legacy_password,
                )
            )

    for assignment in _uncovered_matches(ASSIGNMENT_PATTERN, line, spans):
        if (
            assignment.group("bare") is not None
            and (assignment.start(), assignment.end() - 1) in javascript_spans
            and (assignment.start(), assignment.end() - 1) in certified_spans
            and line[assignment.end() - 1] == ")"
            and JAVASCRIPT_TERMINATOR_PATTERN.match(line, assignment.end())
        ):
            continue
        value = _assignment_value(assignment)
        if not value and not _has_literal_continuation(line, assignment.end()):
            continue
        rule = "literal-assignment"
        if _is_environment_only(value):
            if not _has_literal_continuation(line, assignment.end()):
                continue
            rule = "environment-fallback"
        classification, status = _literal_disposition(
            path, value, line, assignment.end()
        )
        findings.add(
            _finding(
                path, line_number, rule, classification, status, policy.legacy_password
            )
        )

    for pattern in (SQL_PASSWORD_PATTERN, CLI_SECRET_PATTERN):
        for match in _uncovered_matches(pattern, line, spans):
            value = (
                match.group("value")
                if pattern is SQL_PASSWORD_PATTERN
                else _assignment_value(match)
            )
            if (
                not value or _is_environment_only(value)
            ) and not _has_literal_continuation(line, match.end()):
                continue
            classification, status = _literal_disposition(
                path, value, line, match.end()
            )
            findings.add(
                _finding(
                    path,
                    line_number,
                    "literal-assignment",
                    classification,
                    status,
                    policy.legacy_password,
                )
            )
    return findings


def _classify_blob(
    path: str,
    data: bytes,
    policy: Policy,
    selected_baseline: frozenset[str],
) -> set[Finding]:
    """Apply the single classifier to one raw blob."""

    text = _decode_scan_bytes(data)
    certified_contexts = _javascript_duplicate_contexts(text)
    findings: set[Finding] = set()
    for line_number, raw_line in enumerate(text.split("\n"), 1):
        line = raw_line[:-1] if raw_line.endswith("\r") else raw_line
        if policy.legacy_password and policy.legacy_password in line:
            findings.add(
                _finding(
                    path,
                    line_number,
                    "legacy-password",
                    "credential-candidate",
                    "blocked",
                    policy.legacy_password,
                )
            )
        if policy.legacy_host and policy.legacy_host in line:
            findings.add(
                _finding(
                    path,
                    line_number,
                    "legacy-host",
                    "legacy-host",
                    "allowed" if path in selected_baseline else "blocked",
                    policy.legacy_password,
                )
            )
        if AWS_PATTERN.search(line):
            findings.add(
                _finding(
                    path,
                    line_number,
                    "aws-access-key",
                    "credential-candidate",
                    "blocked",
                    policy.legacy_password,
                )
            )
        if PRIVATE_KEY_PATTERN.search(line):
            findings.add(
                _finding(
                    path,
                    line_number,
                    "private-key",
                    "credential-candidate",
                    "blocked",
                    policy.legacy_password,
                )
            )

        for url_match in URL_PATTERN.finditer(line):
            value = url_match.group("password")
            if _is_environment_only(value):
                continue
            classification, status = _value_disposition(path, value)
            findings.add(
                _finding(
                    path,
                    line_number,
                    "credential-url",
                    classification,
                    status,
                    policy.legacy_password,
                )
            )

        for view in _literal_views(line):
            findings.update(
                _classify_literal_view(
                    path,
                    view,
                    line_number,
                    policy,
                    certified_spans=(
                        certified_contexts.get(line_number, frozenset())
                        if view == line
                        else frozenset()
                    ),
                )
            )
    return findings


def _scan_snapshot(
    snapshot: dict[str, bytes], policy: Policy, selected_baseline: frozenset[str]
) -> set[Finding]:
    """Classify a deterministic path-to-bytes snapshot."""

    findings: set[Finding] = set()
    for path in sorted(snapshot):
        findings.update(_classify_blob(path, snapshot[path], policy, selected_baseline))
    return findings


def _ensure_baseline_subset(selected: frozenset[str], policy: Policy) -> None:
    """Enforce the shrink-only baseline invariant."""

    if not selected.issubset(policy.approved_baseline):
        raise ScanFailure("BASELINE_EXPANSION")


def _entry_changed(old: Entry | None, new: Entry | None) -> bool:
    """Compare raw postimage identity without rename or copy heuristics."""

    if old is None or new is None:
        return old is not new
    return (
        old.mode != new.mode or old.object_id != new.object_id or old.kind != new.kind
    )


def _changed_postimages(
    old_entries: dict[str, Entry], new_entries: dict[str, Entry]
) -> list[tuple[str, Entry]]:
    """Return changed regular postimages, rejecting selected unsupported entries."""

    changed: list[tuple[str, Entry]] = []
    for path in sorted(set(old_entries) | set(new_entries)):
        old = old_entries.get(path)
        new = new_entries.get(path)
        if new is None or not _entry_changed(old, new):
            continue
        if not new.supported:
            raise ScanFailure("UNSUPPORTED_ENTRY")
        changed.append((path, new))
    return changed


def _range_commits(
    root: Path, base: str, head: str
) -> list[tuple[str, tuple[str, ...]]]:
    """List every reachable post-base commit and all of its parents."""

    result = _git_command(
        root,
        ["rev-list", "--reverse", "--topo-order", "--parents", head, "--not", base],
        max_stdout=MAX_GIT_OUTPUT,
    )
    commits: list[tuple[str, tuple[str, ...]]] = []
    for line in result.stdout.splitlines():
        parts = line.split()
        if not parts:
            continue
        try:
            commit = parts[0].decode("ascii")
            parents = tuple(part.decode("ascii") for part in parts[1:])
        except UnicodeDecodeError as exc:
            raise ScanFailure("GIT_FAILURE") from exc
        if not REF_PATTERN.fullmatch(commit) or any(
            not REF_PATTERN.fullmatch(parent) for parent in parents
        ):
            raise ScanFailure("GIT_FAILURE")
        commits.append((commit, parents))
    return commits


def _scan_range(root: Path, base: str, head: str, policy: Policy) -> set[Finding]:
    """Scan endpoint and all-parent intermediate postimages in a range."""

    ancestor = _git_command(
        root,
        ["merge-base", "--is-ancestor", base, head],
        max_stdout=128,
        allowed_returncodes=(0, 1, 128),
    )
    if ancestor.returncode == 1:
        raise ScanFailure("INVALID_RANGE")
    if ancestor.returncode != 0:
        raise ScanFailure("GIT_FAILURE")

    tree_cache: dict[str, dict[str, Entry]] = {}

    def entries_for(commit: str) -> dict[str, Entry]:
        if commit not in tree_cache:
            tree_cache[commit] = _tree_entries(root, commit, strict=False)
        return tree_cache[commit]

    base_entries = entries_for(base)
    head_entries = entries_for(head)
    head_baseline = _baseline_from_entries(root, head_entries)
    _ensure_baseline_subset(head_baseline, policy)
    commits = _range_commits(root, base, head)

    baselines: dict[str, frozenset[str]] = {}
    for commit, _ in commits:
        selected = _baseline_from_entries(root, entries_for(commit))
        _ensure_baseline_subset(selected, policy)
        baselines[commit] = selected

    blob_cache: dict[str, bytes] = {}
    findings: set[Finding] = set()

    def scan_postimages(
        changed: Iterable[tuple[str, Entry]], selected: frozenset[str]
    ) -> None:
        for path, entry in changed:
            if entry.object_id not in blob_cache:
                blob_cache[entry.object_id] = _read_blob(root, entry.object_id)
            findings.update(
                _classify_blob(path, blob_cache[entry.object_id], policy, selected)
            )

    scan_postimages(_changed_postimages(base_entries, head_entries), head_baseline)
    for commit, parents in commits:
        commit_entries = entries_for(commit)
        if not parents:
            parent_entries_list = [dict[str, Entry]()]
        else:
            parent_entries_list = [entries_for(parent) for parent in parents]
        for parent_entries in parent_entries_list:
            scan_postimages(
                _changed_postimages(parent_entries, commit_entries), baselines[commit]
            )
    return findings


def _report(findings: Iterable[Finding], error: str | None = None) -> dict[str, object]:
    """Build the exact public report shape."""

    ordered = sorted(set(findings))
    finding_records = [
        {
            "file": finding.file,
            "line": finding.line,
            "rule": finding.rule,
            "classification": finding.classification,
            "status": finding.status,
        }
        for finding in ordered
    ]
    if error is not None:
        return {"status": "error", "findings": finding_records, "errors": [error]}
    blocked = any(finding.status == "blocked" for finding in ordered)
    return {
        "status": "blocked" if blocked else "clean",
        "findings": finding_records,
        "errors": [],
    }


def _emit(report: dict[str, object]) -> None:
    """Emit one ASCII-safe JSON object and no diagnostics."""

    sys.stdout.write(json.dumps(report, ensure_ascii=True, separators=(",", ":")))
    sys.stdout.write("\n")


def main(argv: list[str] | None = None) -> int:
    """Run the local scanner and return 0 clean, 1 blocked, or 2 error."""

    try:
        parsed = _parse_arguments(argv)
        if parsed is None:
            return 0
        root = _validate_repository(parsed.repo)
        policy_ref = _validate_commit(root, parsed.policy_ref)
        policy = _load_policy(root, policy_ref)

        if parsed.mode == "candidate":
            snapshot = _read_candidate_snapshot(root)
            selected_baseline = (
                _parse_baseline(snapshot[BASELINE_PATH])
                if BASELINE_PATH in snapshot
                else frozenset()
            )
            _ensure_baseline_subset(selected_baseline, policy)
            findings = _scan_snapshot(snapshot, policy, selected_baseline)
        elif parsed.mode == "index":
            snapshot = _read_index_snapshot(root)
            selected_baseline = (
                _parse_baseline(snapshot[BASELINE_PATH])
                if BASELINE_PATH in snapshot
                else frozenset()
            )
            _ensure_baseline_subset(selected_baseline, policy)
            findings = _scan_snapshot(snapshot, policy, selected_baseline)
        elif parsed.mode == "tree":
            assert parsed.ref is not None
            ref = _validate_commit(root, parsed.ref)
            snapshot = _read_tree_snapshot(root, ref)
            selected_baseline = (
                _parse_baseline(snapshot[BASELINE_PATH])
                if BASELINE_PATH in snapshot
                else frozenset()
            )
            _ensure_baseline_subset(selected_baseline, policy)
            findings = _scan_snapshot(snapshot, policy, selected_baseline)
        else:
            assert parsed.base is not None and parsed.head is not None
            base = _validate_commit(root, parsed.base)
            head = _validate_commit(root, parsed.head)
            findings = _scan_range(root, base, head, policy)
        report = _report(findings)
    except ScanFailure as failure:
        report = _report((), failure.code)
    except Exception:
        report = _report((), "GIT_FAILURE")

    _emit(report)
    return {"clean": 0, "blocked": 1, "error": 2}[str(report["status"])]


if __name__ == "__main__":
    raise SystemExit(main())
