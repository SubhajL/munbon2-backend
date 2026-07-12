"""
Wave 1.8 dead-code purge lock: the import-graph-verified deletions stay deleted,
the canonical configs stay present, and the provenance keepers live in scripts/.
Pure/stdlib; run isolated:
    PYTHONPATH=src pytest --noconftest -o addopts="" tests/unit/test_dead_code_manifest.py
"""
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[2]
SRC = SERVICE_ROOT / "src"

PURGED_SRC = [
    # stale topology/demo/result JSONs (canonical set lives in src/config/)
    "canal_geometry_template.json",
    "daily_flow_report.json",
    "demo_network.json",
    "hydraulic_profile_data.json",
    "irrigation_schedule.json",
    "munbon_network_complete.json",
    "munbon_network_final.json",
    "munbon_network_structure.json",
    "munbon_network_updated.json",
    "network_simple.json",
    "network_structure_updated.json",
    "path_based_results.json",
    "real_geometry_test_results.json",
    "scada_analysis.json",
    "temporal_demo_network.json",
    "travel_time_results.json",
    # dead analysis/visualization/extraction scripts
    "analyze_network_changes.py",
    "analyze_scada_structure.py",
    "build_network_graph.py",
    "canal_geometry_impact.py",
    "extract_network_from_scada.py",
    "extract_network_structure.py",
    "flow_monitoring_integration.py",
    "hydraulic_network_model.py",
    "network_graph_text.py",
    "shared_path_coordinator.py",
    "simple_gate_control_example.py",
    "temporal_irrigation_scheduler.py",
    "test_with_real_geometry.py",
    "update_network_graph.py",
    "visualize_gate_curves_detailed.py",
    "visualize_gate_hydraulics.py",
    "visualize_hydraulic_profile.py",
    "visualize_network_final.py",
    "visualize_network_graph.py",
    "visualize_travel_times.py",
    "visualize_travel_times_corrected.py",
    # dead modules
    "core/gate_properties_enhanced.py",
    "core/job_order_system.py",
    "core/scada_health_monitor.py",
    "services/gate_controller_integration.py",
    "utils/gate_id_standardizer.py",
    # dead-except-their-broken-tests modules (Wave 1.9)
    "core/gate_registry.py",
    "core/gradual_transition_controller.py",
    "core/state_preservation.py",
]

KEEPER_SCRIPTS = [
    # provenance/generator lineage for the Wave-2.1 config pipeline
    "analyze_scada_excel.py",
    "build_final_network.py",
    "network_from_gate_names.py",
    # the live generator (workbook -> network/geometry/coverage/calibration artifacts)
    "build_scada_config.py",
]

PURGED_SCRIPTS = [
    # replaced by build_scada_config.py (Wave 2.1b): its Sheet1 ระยะทาง column
    # holds KILOMETRES and was written straight into length_m (the 1000x bug),
    # and missing survey columns silently became invented defaults.
    "excel_to_canal_sections.py",
    "extract_gate_calibrations.py",
    "excel_to_calibration_json.py",
]

CANONICAL_CONFIGS = [
    "config/network.json",
    "config/canal_geometry.json",
    "config/gate_calibrations.json",
    "config/gate_configuration.json",
    "config/geometry_coverage.json",
]


def test_purged_files_stay_deleted():
    resurrected = [rel for rel in PURGED_SRC if (SRC / rel).exists()]
    assert not resurrected, (
        f"import-graph-dead files re-added under src/ (Wave 1.8): {resurrected}"
    )


def test_canonical_configs_stay_present():
    missing = [rel for rel in CANONICAL_CONFIGS if not (SRC / rel).exists()]
    assert not missing, f"canonical configs missing: {missing}"
    # the template the strict-null regression drives lives at the SERVICE root
    assert (SERVICE_ROOT / "canal_geometry_template.json").exists()


def test_keeper_scripts_moved_not_deleted():
    for name in KEEPER_SCRIPTS:
        assert (SERVICE_ROOT / "scripts" / name).exists(), f"keeper missing: {name}"
        assert not (SRC / name).exists(), f"keeper duplicated in src/: {name}"


def test_purged_scripts_stay_deleted():
    resurrected = [
        name for name in PURGED_SCRIPTS
        if (SERVICE_ROOT / "scripts" / name).exists() or (SRC / name).exists()
    ]
    assert not resurrected, (
        f"replaced generator scripts re-added (Wave 2.1b): {resurrected}"
    )


def test_no_code_reference_to_purged_files_repo_wide():
    # A filename can outlive its file in defaults/env wiring (the purge found a
    # machine-absolute munbon_network_final.json fallback in TWO other services).
    # Scan live code trees, ignoring comment lines, for the most dangerous names.
    dangerous = (
        "munbon_network_final.json", "munbon_network_updated.json",
        # module spellings of the Wave-1.9 deletions ("core.gate_registry" is
        # qualified so the LIVE services/gate_registry never false-positives)
        "core.gate_registry", "gradual_transition_controller", "state_preservation",
    )
    # scripts/ is exempt: the provenance keepers legitimately name their own
    # historical outputs; network_topology's docstring records the F-11 lineage.
    allowlisted = {SRC / "core" / "network_topology.py"}
    roots = [
        SERVICE_ROOT / "src",
        SERVICE_ROOT.parent / "bff-water-planning" / "src",
        SERVICE_ROOT.parent / "ros-gis-integration" / "src",
        SERVICE_ROOT.parent / "scheduler" / "src",
    ]
    offenders = []
    for root in roots:
        for path in root.rglob("*.py"):
            if "__pycache__" in path.parts or path in allowlisted:
                continue
            for lineno, line in enumerate(
                path.read_text(encoding="utf-8", errors="replace").splitlines(), 1
            ):
                code = line.split("#", 1)[0]
                if any(name in code for name in dangerous):
                    offenders.append(f"{path}:{lineno}")
    assert not offenders, f"purged-file references in live code: {offenders}"


def test_scheduler_client_dropped_the_deleted_model_facades():
    client = (
        SERVICE_ROOT.parent / "scheduler" / "src" / "services" / "clients"
        / "flow_monitoring_client.py"
    ).read_text(encoding="utf-8")
    assert "get_hydraulic_model" not in client
    assert "get_water_propagation" not in client
    assert "get_gate_positions" in client  # live surface survives
