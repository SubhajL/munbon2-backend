"""Typed hydraulic-routing topology derivation locks (PR 2.1a).

The canonical SCADA graph (58 gates / 58 edges) is the source of truth for
gate identity and order. The derived routing topology re-expresses it as
typed routing elements — boundary, transport, branch structure, withdrawal
structure — with exactly one virtual non-gate junction J(LMC,0+170) that
splits the composite M(0,0)->M(0,2) span and re-parents Waste Way after
the 170 m outlet flume. Derivation is pure, deterministic, and fail-closed
against workbook drift.
"""

import copy
import json
from pathlib import Path

import pytest

from core.routing_topology import (
    RoutingRole,
    RoutingTopology,
    RoutingTopologyError,
    derive_routing_topology,
)

SERVICE_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = SERVICE_ROOT / "src" / "config"

VIRTUAL_JUNCTION = "J(LMC,0+170)"
COMPOSITE_EDGE = ("M(0,0)", "M(0,2)")
WASTE_WAY = "M(0,0;1,0)"
RMC_HEAD = "M(0,0;2,0)"
FLUME_REACH_ID = "C_M(0,0)_J(LMC,0+170)"
LMC_REMAINDER_REACH_ID = "C_J(LMC,0+170)_M(0,2)"


@pytest.fixture(scope="module")
def network() -> dict:
    return json.loads((CONFIG_DIR / "network.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def geometry_coverage() -> dict:
    return json.loads(
        (CONFIG_DIR / "geometry_coverage.json").read_text(encoding="utf-8")
    )


@pytest.fixture(scope="module")
def canal_geometry() -> dict:
    return json.loads(
        (CONFIG_DIR / "canal_geometry.json").read_text(encoding="utf-8")
    )


@pytest.fixture(scope="module")
def topology(network, geometry_coverage, canal_geometry) -> RoutingTopology:
    return derive_routing_topology(network, geometry_coverage, canal_geometry)


def test_routing_topology_has_59_elements_and_forms_a_rooted_tree(topology):
    assert len(topology.elements) == 59

    child_nodes = [element.downstream_node_id for element in topology.elements]
    assert len(child_nodes) == len(set(child_nodes)), "each node has one parent"
    assert "S" not in child_nodes

    nodes = {"S"} | set(child_nodes)
    assert len(nodes) == 60

    parent_of = {
        element.downstream_node_id: element.upstream_node_id
        for element in topology.elements
    }
    for node in nodes - {"S"}:
        seen = set()
        cursor = node
        while cursor != "S":
            assert cursor not in seen, f"cycle reaching {node}"
            seen.add(cursor)
            cursor = parent_of[cursor]


def test_routing_topology_classifies_1_boundary_42_transport_13_branch_3_withdrawal(
    topology,
):
    by_role = {}
    for element in topology.elements:
        by_role.setdefault(element.role, []).append(element)

    assert len(by_role[RoutingRole.BOUNDARY]) == 1
    assert len(by_role[RoutingRole.TRANSPORT]) == 42
    assert len(by_role[RoutingRole.BRANCH_STRUCTURE]) == 13
    assert len(by_role[RoutingRole.WITHDRAWAL_STRUCTURE]) == 3

    boundary = by_role[RoutingRole.BOUNDARY][0]
    assert (boundary.upstream_node_id, boundary.downstream_node_id) == ("S", "M(0,0)")


def test_routing_topology_inserts_only_lmc_0_170_virtual_junction(
    topology, network
):
    canonical_nodes = {"S"} | set(network["gates"])
    derived_nodes = {"S"} | {
        element.downstream_node_id for element in topology.elements
    }

    assert derived_nodes - canonical_nodes == {VIRTUAL_JUNCTION}


def test_waste_way_withdrawal_origin_is_j_lmc_0_170(topology):
    waste_way = next(
        element
        for element in topology.elements
        if element.downstream_node_id == WASTE_WAY
    )

    assert waste_way.role is RoutingRole.WITHDRAWAL_STRUCTURE
    assert waste_way.upstream_node_id == VIRTUAL_JUNCTION
    assert waste_way.canonical_edges == (("M(0,0)", WASTE_WAY),)


def test_rmc_branch_origin_remains_m_0_0(topology):
    rmc_head = next(
        element
        for element in topology.elements
        if element.downstream_node_id == RMC_HEAD
    )

    assert rmc_head.role is RoutingRole.BRANCH_STRUCTURE
    assert rmc_head.upstream_node_id == "M(0,0)"


def test_routing_topology_preserves_all_58_canonical_gate_edges_as_lineage(
    topology, network
):
    canonical_edges = {tuple(edge) for edge in network["edges"]}
    lineage = [
        edge for element in topology.elements for edge in element.canonical_edges
    ]

    assert set(lineage) == canonical_edges
    assert lineage.count(COMPOSITE_EDGE) == 2
    for edge in canonical_edges - {COMPOSITE_EDGE}:
        assert lineage.count(edge) == 1
    first_occurrence_order = list(dict.fromkeys(lineage))
    assert first_occurrence_order == [tuple(edge) for edge in network["edges"]]


def test_split_transport_elements_carry_flume_and_surveyed_lengths(topology):
    by_id = {element.element_id: element for element in topology.elements}
    flume = by_id[FLUME_REACH_ID]
    remainder = by_id[LMC_REMAINDER_REACH_ID]

    assert flume.role is RoutingRole.TRANSPORT
    assert flume.span_m == 170
    assert flume.canonical_edges == (COMPOSITE_EDGE,)
    assert remainder.role is RoutingRole.TRANSPORT
    assert remainder.span_m == 1450
    assert remainder.canonical_edges == (COMPOSITE_EDGE,)


def test_geometry_status_marks_flume_unavailable_and_survey_complete_transports(
    topology,
):
    by_status = {}
    for element in topology.elements:
        by_status.setdefault(element.geometry_status, []).append(element)

    assert [e.element_id for e in by_status["unavailable"]] == [FLUME_REACH_ID]
    assert len(by_status["surveyed"]) == 41
    assert all(
        e.role is RoutingRole.TRANSPORT for e in by_status["surveyed"]
    )
    assert len(by_status["not_applicable"]) == 17
    assert all(
        e.role is not RoutingRole.TRANSPORT for e in by_status["not_applicable"]
    )


def test_withdrawal_structures_carry_their_surveyed_chainage(topology):
    withdrawals = {
        element.downstream_node_id: element
        for element in topology.elements
        if element.role is RoutingRole.WITHDRAWAL_STRUCTURE
    }

    assert withdrawals[WASTE_WAY].located_at_km == "0+170"
    assert withdrawals["M(0,0;2,0;1,0)"].located_at_km == "2+450"
    assert withdrawals["M(0,0;2,1;1,2;1,0)"].located_at_km == "2+333"
    non_withdrawals = [
        element
        for element in topology.elements
        if element.role is not RoutingRole.WITHDRAWAL_STRUCTURE
    ]
    assert all(element.located_at_km is None for element in non_withdrawals)


def test_transport_reach_ids_returns_42_release_coverage_keys(topology):
    reach_ids = topology.transport_reach_ids()

    assert len(reach_ids) == 42
    assert len(set(reach_ids)) == 42
    assert all(reach_id.startswith("C_") for reach_id in reach_ids)
    assert FLUME_REACH_ID in reach_ids
    assert LMC_REMAINDER_REACH_ID in reach_ids
    assert "C_M(0,0)_M(0,2)" not in reach_ids


def test_element_ids_are_unique_and_role_prefixed(topology):
    ids = [element.element_id for element in topology.elements]
    assert len(ids) == len(set(ids))

    prefix_by_role = {
        RoutingRole.BOUNDARY: "B_",
        RoutingRole.TRANSPORT: "C_",
        RoutingRole.BRANCH_STRUCTURE: "BR_",
        RoutingRole.WITHDRAWAL_STRUCTURE: "WD_",
    }
    for element in topology.elements:
        assert element.element_id.startswith(prefix_by_role[element.role])
        assert element.element_id.endswith(
            f"{element.upstream_node_id}_{element.downstream_node_id}"
        )


def test_structural_constructor_rejects_empty_or_mislabeled_elements():
    from core.routing_topology import (
        RoutingElement,
        RoutingGeometryStatus,
        build_routing_topology,
    )

    with pytest.raises(RoutingTopologyError, match="empty"):
        build_routing_topology(())

    mislabeled = RoutingElement(
        element_id="C_WRONG_ID",
        upstream_node_id="S",
        downstream_node_id="A",
        role=RoutingRole.TRANSPORT,
        canonical_edges=(("S", "A"),),
        canal=None,
        span_m=100.0,
        geometry_status=RoutingGeometryStatus.SURVEYED,
        located_at_km=None,
    )
    with pytest.raises(RoutingTopologyError, match="element_id"):
        build_routing_topology((mislabeled,))


def test_gate_node_ids_exclude_the_virtual_junction(topology, network):
    gate_nodes = topology.canonical_gate_node_ids()

    assert len(gate_nodes) == 58
    assert VIRTUAL_JUNCTION not in gate_nodes
    assert set(gate_nodes) == set(network["gates"])


def test_routing_edges_cover_all_59_elements_in_order(topology):
    edges = topology.routing_edges()

    assert len(edges) == 59
    assert edges == tuple(
        (element.upstream_node_id, element.downstream_node_id)
        for element in topology.elements
    )


def test_derivation_is_deterministic(network, geometry_coverage, canal_geometry):
    first = derive_routing_topology(network, geometry_coverage, canal_geometry)
    second = derive_routing_topology(network, geometry_coverage, canal_geometry)

    assert first == second
    assert first.content_hash == second.content_hash
    assert len(first.content_hash) == 64
    assert first.source_sha256 == network["metadata"]["source_sha256"]


def _mutate(geometry_coverage: dict, action) -> dict:
    mutated = copy.deepcopy(geometry_coverage)
    action(mutated)
    return mutated


def _partial_entry(coverage: dict) -> dict:
    return next(
        edge for edge in coverage["edges"] if edge.get("status") == "partial"
    )


def _waste_way_entry(coverage: dict) -> dict:
    return next(
        edge for edge in coverage["edges"] if edge.get("downstream") == WASTE_WAY
    )


@pytest.mark.parametrize(
    ("description", "action"),
    [
        (
            "no partial edge",
            lambda coverage: _partial_entry(coverage).update(
                status="full", missing=[]
            ),
        ),
        (
            "unexpected flume gap length",
            lambda coverage: _partial_entry(coverage).update(gap_m=200),
        ),
        (
            "unexpected missing chainage",
            lambda coverage: _partial_entry(coverage)["missing"][0].update(
                to_km="0+200"
            ),
        ),
        (
            "waste way at a different chainage",
            lambda coverage: _waste_way_entry(coverage).update(km="0+180"),
        ),
        (
            "second partial edge",
            lambda coverage: next(
                edge
                for edge in coverage["edges"]
                if edge.get("status") == "full"
            ).update(status="partial", missing=[]),
        ),
    ],
)
def test_derivation_fails_closed_on_unexpected_survey_shape(
    network, geometry_coverage, canal_geometry, description, action
):
    mutated = _mutate(geometry_coverage, action)

    with pytest.raises(RoutingTopologyError):
        derive_routing_topology(network, mutated, canal_geometry)


@pytest.mark.parametrize(
    ("description", "action"),
    [
        (
            "surveyed remainder length disagrees",
            lambda geometry: next(
                r
                for r in geometry["reaches"]
                if r["from_node"] == "M(0,0)" and r["to_node"] == "M(0,2)"
            ).update(covered_m=1400),
        ),
        (
            "composite survey section starts at the dam, not the flume end",
            lambda geometry: next(
                s
                for s in geometry["canal_sections"]
                if s["from_node"] == "M(0,0)" and s["to_node"] == "M(0,2)"
            ).update(from_km="0+000"),
        ),
        (
            "a surveyed serial reach disappears",
            lambda geometry: geometry["reaches"].pop(),
        ),
        (
            "a full serial span silently changes length",
            lambda geometry: next(
                r
                for r in geometry["reaches"]
                if r["from_node"] == "M(0,2)" and r["to_node"] == "M(0,3)"
            ).update(span_m=5383),
        ),
    ],
)
def test_derivation_fails_closed_on_canal_geometry_disagreement(
    network, geometry_coverage, canal_geometry, description, action
):
    mutated = _mutate(canal_geometry, action)

    with pytest.raises(RoutingTopologyError):
        derive_routing_topology(network, geometry_coverage, mutated)


def test_derivation_fails_closed_on_swapped_withdrawal_identity(
    network, geometry_coverage, canal_geometry
):
    """A withdrawal structure and a branch head must not be able to trade
    categories: the three reviewed withdrawal structures are pinned by
    identity, not just by count."""
    mutated = copy.deepcopy(geometry_coverage)
    fto = next(
        edge
        for edge in mutated["edges"]
        if edge.get("downstream") == "M(0,0;2,0;1,0)"
    )
    rmc_head = next(
        edge for edge in mutated["edges"] if edge.get("downstream") == RMC_HEAD
    )
    fto["category"] = "junction_head"
    fto.pop("km", None)
    rmc_head["category"] = "offtake"
    rmc_head["km"] = "2+450"

    with pytest.raises(RoutingTopologyError):
        derive_routing_topology(network, mutated, canal_geometry)
