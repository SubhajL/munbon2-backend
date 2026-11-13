"""Offline documentation/ignore contracts for the approved P01 candidate."""

import ast
import copy
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "docs/development/DEVELOPMENT_COMPLETION_REGISTER.md"
INDEX = ROOT / "docs/development/PLAN_SUPERSESSION_INDEX.md"
BACKEND = "2a53090c608331b282e331502ae1ec5851ae9c15"
ACCEPTED_BACKEND = "a26c0fd000b0b6da443135ffeadb992eded8fb5b"
FRONTEND = "067b3e22401854f8c6d6db42dc0c5c1872fca6f8"
WORK_IDS = {
    "P01",
    "S01",
    "P02",
    "P02-D",
    "P03",
    "P04",
    "P05",
    "P06-L",
    "P06-S",
    "P06-H",
    "P07",
    "P08-draft",
    "P08-final",
    "F-01",
    "F-04",
    "F-02",
    "F-05",
    "F-06",
    "F-09",
    "F-07-data",
    "F-07-security",
    "F-08-boot",
    "F-08-ingest",
    "E1",
    "E2",
    "O-SEC",
    "O-HIST",
    "O-PROT-1",
    "O-PROT-2",
    "O-CI",
    "SEN-GATE",
    "SEN-ACK",
    "LEGACY-SF",
    "CP-SOURCE",
    "FE-SOURCE",
    "LOCAL-FE-CI-1",
    "LOCAL-FE-CI-2",
    "LOCAL-RC-1",
    "HIST-CAMPAIGN",
    "C-FIELD",
    "C-PROD",
    "C-W4",
    "C-OPT",
}
PLAN_IDS = {
    "V2",
    "OCT31",
    "AUG22",
    "AUG01",
    "JUL22",
    "JUL23",
    "FLOW-PROGRAM",
    "FLOW-WAVES",
    "FLOW-MASTER",
    "FLOW-REVIEW",
    "FLOW-HANDOFF",
    "PHASES",
    "TASKS",
    "LOCAL-ACCEPTANCE",
    "CAMPAIGN",
    "DARK-DEPLOYMENT",
}
CURRENT_GUIDES = (
    "AGENTS.md",
    "CONTEXT.md",
    "README.md",
    "PR_PHASE_PLAN.md",
    "docs/TASK_STATUS_TRACKING.md",
    "services/flow-monitoring/CLAUDE.md",
    "services/daily-chart-notifier/CLAUDE.md",
    "services/flow-monitoring/docs/remediation/REMEDIATION_MASTER.md",
    "services/flow-monitoring/docs/remediation/PR_REVIEW_GUIDE.md",
    "services/flow-monitoring/docs/remediation/HANDOFF.md",
)
RECORD_COLUMNS = (
    "ID",
    "Owner",
    "Source",
    "Local",
    "Runtime",
    "Production",
    "Family",
    "Evidence",
    "Disposition",
)
GATE_COLUMNS = ("ID", "Next gate", "Authorization", "Done criterion")
EVIDENCE_COLUMNS = ("ID", "Source refs", "Date", "Origin", "Candidate", "Family")
SOURCE_STATES = {
    "planned",
    "source-partial",
    "source-complete",
    "deferred-by-design",
    "not-applicable",
}
LOCAL_STATES = {"pending", "historical-pass", "local-gates-passed", "not-applicable"}
RUNTIME_STATES = {"not-reverified", "historical-accepted", "not-applicable"}
NEW_PATHS = (
    "docs/development/DEVELOPMENT_COMPLETION_REGISTER.md",
    "docs/development/PLAN_SUPERSESSION_INDEX.md",
    "tests/planning/test_completion_register.py",
)


def parse_table(body: str, heading: str, columns: tuple[str, ...]) -> dict:
    marker = f"## {heading}\n"
    if body.count(marker) != 1:
        raise ValueError(f"missing or duplicate heading: {heading}")
    section = body.split(marker, 1)[1].split("\n## ", 1)[0]
    lines = [line.strip() for line in section.splitlines() if line.startswith("|")]
    cells = [[cell.strip() for cell in line.strip("|").split("|")] for line in lines]
    if len(cells) < 3 or tuple(cells[0]) != columns:
        raise ValueError(f"missing or invalid columns: {heading}")
    if not all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells[1]):
        raise ValueError("invalid table separator")
    records = {}
    for values in cells[2:]:
        if len(values) != len(columns) or not all(values):
            raise ValueError("missing record field")
        record = dict(zip(columns, values, strict=True))
        if record["ID"] in records:
            raise ValueError("duplicate record ID")
        records[record["ID"]] = record
    return records


def load_completion_register(body: str | None = None) -> dict:
    if body is None:
        assert REGISTER.is_file(), "P01 authoritative register is missing"
        body = REGISTER.read_text(encoding="utf-8")
    records = parse_table(body, "Completion register", RECORD_COLUMNS)
    gates = parse_table(body, "Remaining gates", GATE_COLUMNS)
    evidence = parse_table(body, "Evidence catalogue", EVIDENCE_COLUMNS)
    if records.keys() != gates.keys():
        raise ValueError("register/gate ID mismatch")
    for record_id, record in records.items():
        if record["Evidence"] not in evidence:
            raise ValueError("missing evidence identity")
        if record["Source"] not in SOURCE_STATES:
            raise ValueError("invalid source state")
        if (
            record["Local"] not in LOCAL_STATES
            or record["Runtime"] not in RUNTIME_STATES
        ):
            raise ValueError("invalid local/runtime state")
        if record["Production"] not in {"unaccepted", "not-applicable"}:
            raise ValueError("P01 cannot grant production acceptance or activation")
        record.update(gates[record_id])
        record["evidence_record"] = evidence[record["Evidence"]]
    return records


def validate_evidence_references(records: dict, root: Path = ROOT) -> None:
    for record in records.values():
        evidence = record["evidence_record"]
        refs = re.findall(
            r"`(repo|frontend|local|external):([^`]+)`", evidence["Source refs"]
        )
        if not refs or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", evidence["Date"]):
            raise ValueError("missing typed evidence reference/date")
        if evidence["Family"] != record["Family"]:
            raise ValueError("evidence family mismatch")
        for kind, location in refs:
            if kind == "repo":
                path = Path(location)
                if (
                    path.is_absolute()
                    or ".." in path.parts
                    or not (root / path).is_file()
                ):
                    raise ValueError("missing or unsafe repository source reference")
        if record["Source"] == "source-complete" and not any(
            kind in {"repo", "frontend"} for kind, _ in refs
        ):
            raise ValueError("source-complete needs source evidence")
        if record["Runtime"] == "historical-accepted":
            if record["Family"] != "local-rc" or evidence["Candidate"] != (
                f"backend={ACCEPTED_BACKEND}; frontend={FRONTEND}"
            ):
                raise ValueError("runtime acceptance cannot transfer candidate/family")
        if record["Local"] == "historical-pass" and evidence["Origin"] not in {
            "retained-V2-audit",
            "retained-acceptance",
            "retained-campaign",
        }:
            raise ValueError("historical pass needs retained evidence origin")


def test_register_has_one_disposition_per_reconciled_plan():
    records = load_completion_register()
    assert set(records) == WORK_IDS
    validate_evidence_references(records)
    assert INDEX.is_file(), "P01 supersession index is missing"
    plans = parse_table(
        INDEX.read_text(encoding="utf-8"),
        "Plan supersession",
        ("ID", "Artifact", "Storage", "Disposition", "Current authority"),
    )
    assert set(plans) == PLAN_IDS
    for record in plans.values():
        assert record["Current authority"] == "DEVELOPMENT_COMPLETION_REGISTER.md"
        if record["Storage"] == "tracked":
            assert (ROOT / record["Artifact"].strip("`")).is_file()
        else:
            assert record["Storage"] == "retained-local"
            assert (
                "](" not in record["Artifact"]
            ), "local-only artifact is not a repository link"
    assert (
        plans["OCT31"]["Disposition"]
        == "Superseded prospectively by V2; preserve unchanged"
    )


def test_source_and_activation_states_are_distinct():
    records = load_completion_register()
    for record_id in ("CP-SOURCE", "FE-SOURCE", "LOCAL-FE-CI-1", "LOCAL-FE-CI-2"):
        assert records[record_id]["Source"] == "source-complete"
        assert records[record_id]["Production"] == "unaccepted"
        assert records[record_id]["Runtime"] == "not-reverified"
    assert all(record["Production"] != "activated" for record in records.values())


def test_completed_control_plan_items_reference_existing_wiring():
    records = load_completion_register()
    assert records["CP-SOURCE"]["Family"] == "source"
    tree = ast.parse((ROOT / "services/bff-water-planning/src/main.py").read_text())
    registered = {
        ast.unparse(call.args[0])
        for call in ast.walk(tree)
        if isinstance(call, ast.Call)
        and isinstance(call.func, ast.Attribute)
        and call.func.attr == "include_router"
        and call.args
    }
    assert {
        "control_plans.router",
        "planning_depth_roster.router",
        "planning_depths.router",
        "planning_depths_v2.router",
    } <= registered
    pm2 = (ROOT / "infra/pm2/build-irrigation-config.ts").read_text()
    assert "name: 'scheduler-control-dispatch'" in pm2
    assert "args: '-m jobs.shadow_dispatch_once'" in pm2
    suite = ast.parse(
        (ROOT / "ops/control-plan-read-local/run-stage-suite.py").read_text()
    )
    stage_order = next(
        ast.literal_eval(node.value)
        for node in suite.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "STAGE_ORDER"
            for target in node.targets
        )
    )
    assert stage_order == (
        "LOCAL-BASE-0",
        "LOCAL-RTA-1",
        "LOCAL-AC-1",
        "LOCAL-READ-ACT-1",
        "LOCAL-EVIDENCE-1",
        "LOCAL-GO-READ-1",
        "LOCAL-WRITE-FOUNDATION-1",
        "LOCAL-WRITE-UI-1",
        "LOCAL-PERSIST-ONLY-1",
        "LOCAL-WRITE-ACT-1",
    )
    baselines = [
        keyword.value
        for node in ast.walk(
            ast.parse(
                (
                    ROOT / "services/scheduler/src/jobs/shadow_dispatch_once.py"
                ).read_text()
            )
        )
        if isinstance(node, ast.Call)
        for keyword in node.keywords
        if keyword.arg == "baselines"
    ]
    assert any(isinstance(value, ast.Dict) and not value.keys for value in baselines)


def test_historical_campaign_and_rc_remain_separate():
    records = load_completion_register()
    assert records["LOCAL-RC-1"]["Family"] == "local-rc"
    assert records["LOCAL-RC-1"]["Runtime"] == "historical-accepted"
    assert records["HIST-CAMPAIGN"]["Family"] == "frozen-campaign"
    body = REGISTER.read_text()
    for token in (
        "campaign_ledger_eligible=false",
        "2026-08-20-nine-stage-orbstack-7f032c4c-attempt-1",
        "11 passed",
        "9 passed",
        BACKEND,
        ACCEPTED_BACKEND,
        FRONTEND,
    ):
        assert token in body
    assert "No runtime acceptance transfers" in body


def test_deferred_w4_is_not_counted_as_missing_mvp():
    records = load_completion_register()
    for record_id in ("C-W4", "C-OPT"):
        assert records[record_id]["Source"] == "deferred-by-design"
        assert (
            records[record_id]["Disposition"] == "Excluded from the named dark release"
        )
    assert "persist-only" in records["C-W4"]["Next gate"]


def test_all_six_reviewed_remediation_ids_have_dispositions():
    records = load_completion_register()
    assert records["F-02"]["Source"] == "source-complete"
    assert records["F-05"]["Production"] == "unaccepted"
    for record_id in ("F-06", "F-09"):
        assert records[record_id]["Source"] == "source-partial"
        assert "legacy" in records[record_id]["Disposition"].lower()
    assert records["F-07-data"]["Source"] == "source-complete"
    assert (
        records["F-07-security"]["Disposition"]
        == "Security-open; source scan cannot prove rotation"
    )
    assert records["F-08-boot"]["Source"] == "source-complete"
    assert records["F-08-ingest"]["Source"] == "source-partial"
    assert "logging scaffold" in records["F-08-ingest"]["Disposition"]


def test_security_and_main_protection_are_required_release_rows():
    records = load_completion_register()
    for record_id in ("E1", "E2", "O-SEC", "O-HIST", "O-PROT-1"):
        assert records[record_id]["Owner"] == "Project owner (user)"
        assert records[record_id]["Production"] == "unaccepted"
    for record_id in ("S01", "O-SEC", "O-HIST", "O-CI", "O-PROT-1", "O-PROT-2"):
        assert record_id in records["P08-final"]["Next gate"]
    assert "documented-executed" in records["E2"]["Disposition"]
    assert "not freshly queried" in REGISTER.read_text()


def test_documentation_points_to_one_current_status_owner():
    for relative in CURRENT_GUIDES:
        body = (ROOT / relative).read_text()
        assert re.search(
            r"\[[^\]]+\]\(([^)]+DEVELOPMENT_COMPLETION_REGISTER\.md)\)", body
        ), f"missing current-status link: {relative}"
        link = re.search(r"\]\(([^)]+DEVELOPMENT_COMPLETION_REGISTER\.md)\)", body)[1]
        assert ((ROOT / relative).parent / link).resolve() == REGISTER
    agents = (ROOT / "AGENTS.md").read_text()
    assert "CLAUDE.md" in agents and "turbo typecheck" not in agents
    context = (ROOT / "CONTEXT.md").read_text()
    assert "no root workspace" in context
    assert "Sensor Data Service (Go)" not in context
    assert "smartfarm-water-control" in context and "Irrigation Canal" in context
    flow = (ROOT / "services/flow-monitoring/CLAUDE.md").read_text()
    assert "the wired gate flow law is inverted" not in flow
    assert "`_get_canal_capacity` returns a hardcoded `15.0`" not in flow
    notifier = (ROOT / "services/daily-chart-notifier/CLAUDE.md").read_text()
    assert "ignored local" in notifier and "committed `dist/`" not in notifier
    readme = (ROOT / "README.md").read_text()
    assert "Delete their local copies" not in readme
    assert "rotation" in readme and "history" in readme


def test_sensor_data_is_qualified_or_explicitly_blocked():
    records = load_completion_register()
    for record_id in ("SEN-GATE", "SEN-ACK", "P06-S"):
        assert records[record_id]["Source"] in {"planned", "source-partial"}
        assert records[record_id]["Local"] == "pending"
        assert "P06" in records[record_id]["Next gate"]
    assert "DeleteMessage" in records["SEN-ACK"]["Disposition"]


@pytest.mark.parametrize(
    "mutation", ["duplicate", "missing-field", "unknown-state", "activation"]
)
def test_register_parser_rejects_incomplete_or_ambiguous_records(mutation):
    row = "| SAMPLE | Project owner (user) | planned | pending | not-reverified | unaccepted | source | EV | Planned |"
    body = (
        "## Completion register\n| "
        + " | ".join(RECORD_COLUMNS)
        + " |\n| "
        + " | ".join("---" for _ in RECORD_COLUMNS)
        + " |\n"
        + row
        + "\n"
        "## Remaining gates\n| ID | Next gate | Authorization | Done criterion |\n"
        "| --- | --- | --- | --- |\n| SAMPLE | Gate | Approval | Proof |\n"
        "## Evidence catalogue\n| ID | Source refs | Date | Origin | Candidate | Family |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
        "| EV | `repo:README.md` | 2026-11-02 | source-inspected | baseline | source |\n"
    )
    if mutation == "duplicate":
        body = body.replace(row, row + "\n" + row)
    elif mutation == "missing-field":
        body = body.replace("| Planned |", "|  |")
    elif mutation == "unknown-state":
        body = body.replace("| planned |", "| complete |")
    else:
        body = body.replace("| unaccepted |", "| activated |")
    with pytest.raises(ValueError):
        load_completion_register(body)


@pytest.mark.parametrize(
    "mutation", ["no-evidence", "missing-source", "wrong-sha", "wrong-family"]
)
def test_completed_claims_reject_missing_evidence_or_candidate_transfer(mutation):
    records = copy.deepcopy(load_completion_register())
    evidence = records["LOCAL-RC-1"]["evidence_record"]
    if mutation == "no-evidence":
        evidence["Source refs"] = "none"
    elif mutation == "missing-source":
        evidence["Source refs"] = "`repo:nonexistent/source.py`"
    elif mutation == "wrong-sha":
        evidence["Candidate"] = f"backend={BACKEND}; frontend={FRONTEND}"
    else:
        evidence["Family"] = "frozen-campaign"
    with pytest.raises(ValueError):
        validate_evidence_references(records)


@pytest.fixture
def ignore_sandbox(tmp_path):
    subprocess.run(["git", "init", "--quiet", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_text((ROOT / ".gitignore").read_text())
    return tmp_path


def is_ignored(root: Path, path: str) -> bool:
    result = subprocess.run(
        [
            "git",
            "-c",
            "core.excludesFile=/dev/null",
            "-c",
            "core.ignoreCase=false",
            "check-ignore",
            "--no-index",
            "-q",
            "--",
            path,
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode in (0, 1), result.stderr
    return result.returncode == 0


@pytest.mark.parametrize("path", NEW_PATHS)
def test_p01_paths_are_trackable_without_force_add(ignore_sandbox, path):
    assert not is_ignored(ignore_sandbox, path), f"approved P01 path is ignored: {path}"


@pytest.mark.parametrize(
    "path",
    [
        "docs/unrelated.md",
        "docs/development/UNAPPROVED.md",
        "tests/unrelated.py",
        "tests/planning/test_unapproved.py",
        "nested/docs/development/DEVELOPMENT_COMPLETION_REGISTER.md",
        "nested/tests/planning/test_completion_register.py",
        "docs/development/.env",
        "tests/planning/.env.local",
        "docs/development/operator.pem",
        "tests/planning/operator.key",
        "docs/development/credentials.json",
        "tests/planning/snapshot.sql",
        "tests/planning/__pycache__/test_completion_register.pyc",
        "services/scheduler/tests/private.key",
        "services/scheduler/tests/.env",
    ],
)
def test_p01_allowlist_preserves_unrelated_and_secret_guards(ignore_sandbox, path):
    assert is_ignored(ignore_sandbox, path), f"unapproved path became trackable: {path}"


@pytest.mark.parametrize(
    "path",
    [
        "ops/control-plan-read-local/tests/test_local_artifacts.py",
        "services/scheduler/tests/unit/test_control_plan_campaign_identity.py",
        "services/flow-monitoring/docs/remediation/HANDOFF.md",
        "services/bff-water-planning/migrations/009_crop_registry.sql",
    ],
)
def test_p01_allowlist_preserves_existing_scoped_exceptions(ignore_sandbox, path):
    assert not is_ignored(ignore_sandbox, path)
