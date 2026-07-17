"""Typed hydraulic-routing topology derived from canonical SCADA artifacts.

The canonical network (58 gates / 58 edges) answers connectivity and gate
ordering. Hydraulic routing needs typed elements: only physical transport
spans carry travel-time/loss/dispersion/capacity responses, while the
source boundary, junction heads, and terminal withdrawal structures are
non-transport transitions at V1 resolution. The single composite span
M(0,0)->M(0,2) is split at the virtual junction J(LMC,0+170): a 170 m
outlet flume followed by the 1,450 m surveyed LMC section, with Waste Way
re-parented to the junction because water reaches it through the flume.

Derivation is a pure function of the canonical artifacts and fails closed
on any survey shape it was not reviewed against.
"""

import hashlib
import json
from dataclasses import dataclass
from enum import Enum

SCHEMA_VERSION = 1
VIRTUAL_JUNCTION = "J(LMC,0+170)"
ROOT = "S"

_COMPOSITE_EDGE = ("M(0,0)", "M(0,2)")
_COMPOSITE_SPAN_M = 1620
_FLUME_SPAN_M = 170
_LMC_REMAINDER_SPAN_M = 1450
_FLUME_FROM_KM = "0+000"
_FLUME_TO_KM = "0+170"
_WASTE_WAY_NODE = "M(0,0;1,0)"
_WASTE_WAY_PARENT = "M(0,0)"
_WASTE_WAY_KM = "0+170"

_EXPECTED_ROLE_COUNTS = {
    "boundary": 1,
    "transport": 42,
    "branch_structure": 13,
    "withdrawal_structure": 3,
}

# The three reviewed withdrawal structures are pinned by identity: a
# regenerated workbook must not be able to trade an offtake for a branch
# head while keeping the counts intact.
_EXPECTED_WITHDRAWAL_NODES = frozenset(
    {"M(0,0;1,0)", "M(0,0;2,0;1,0)", "M(0,0;2,1;1,2;1,0)"}
)


class RoutingTopologyError(ValueError):
    """Raised when canonical artifacts cannot yield the reviewed topology."""


class RoutingRole(str, Enum):
    BOUNDARY = "boundary"
    TRANSPORT = "transport"
    BRANCH_STRUCTURE = "branch_structure"
    WITHDRAWAL_STRUCTURE = "withdrawal_structure"


_ID_PREFIX = {
    RoutingRole.BOUNDARY: "B",
    RoutingRole.TRANSPORT: "C",
    RoutingRole.BRANCH_STRUCTURE: "BR",
    RoutingRole.WITHDRAWAL_STRUCTURE: "WD",
}


class RoutingGeometryStatus(str, Enum):
    SURVEYED = "surveyed"
    UNAVAILABLE = "unavailable"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True)
class RoutingElement:
    element_id: str
    upstream_node_id: str
    downstream_node_id: str
    role: RoutingRole
    canonical_edges: tuple[tuple[str, str], ...]
    canal: str | None
    span_m: float | None
    geometry_status: RoutingGeometryStatus
    located_at_km: str | None


@dataclass(frozen=True)
class RoutingTopology:
    schema_version: int
    source_sha256: str
    elements: tuple[RoutingElement, ...]
    content_hash: str

    def transport_reach_ids(self) -> tuple[str, ...]:
        return tuple(
            element.element_id
            for element in self.elements
            if element.role is RoutingRole.TRANSPORT
        )

    def routing_edges(self) -> tuple[tuple[str, str], ...]:
        return tuple(
            (element.upstream_node_id, element.downstream_node_id)
            for element in self.elements
        )

    def canonical_gate_node_ids(self) -> frozenset[str]:
        """The physical SCADA gates — never the virtual routing junction."""
        return frozenset(
            downstream
            for element in self.elements
            for _, downstream in element.canonical_edges
        )


def _element_id(role: RoutingRole, upstream: str, downstream: str) -> str:
    return f"{_ID_PREFIX[role]}_{upstream}_{downstream}"


def _element(
    role: RoutingRole,
    upstream: str,
    downstream: str,
    canonical_edges: tuple[tuple[str, str], ...],
    canal: str | None,
    span_m: float | None,
    geometry_status: RoutingGeometryStatus,
    located_at_km: str | None = None,
) -> RoutingElement:
    return RoutingElement(
        element_id=_element_id(role, upstream, downstream),
        upstream_node_id=upstream,
        downstream_node_id=downstream,
        role=role,
        canonical_edges=canonical_edges,
        canal=canal,
        span_m=span_m,
        geometry_status=geometry_status,
        located_at_km=located_at_km,
    )


def routing_topology_payload(topology: RoutingTopology) -> dict:
    return {
        "schema_version": topology.schema_version,
        "source_sha256": topology.source_sha256,
        "elements": [
            {
                "element_id": element.element_id,
                "upstream_node_id": element.upstream_node_id,
                "downstream_node_id": element.downstream_node_id,
                "role": element.role.value,
                "canonical_edges": [list(edge) for edge in element.canonical_edges],
                "canal": element.canal,
                "span_m": element.span_m,
                "geometry_status": element.geometry_status.value,
                "located_at_km": element.located_at_km,
            }
            for element in topology.elements
        ],
    }


def _content_hash(source_sha256: str, elements: tuple[RoutingElement, ...]) -> str:
    payload = routing_topology_payload(
        RoutingTopology(
            schema_version=SCHEMA_VERSION,
            source_sha256=source_sha256,
            elements=elements,
            content_hash="",
        )
    )
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RoutingTopologyError(message)


def _coverage_by_edge(geometry_coverage: dict) -> dict[tuple[str, str], dict]:
    entries = geometry_coverage.get("edges")
    _require(
        isinstance(entries, list) and entries,
        "geometry coverage must contain a non-empty edges list",
    )
    by_edge: dict[tuple[str, str], dict] = {}
    for entry in entries:
        edge = (entry.get("upstream"), entry.get("downstream"))
        _require(
            all(isinstance(node, str) and node for node in edge),
            f"geometry coverage entry has invalid endpoints: {entry!r}",
        )
        _require(edge not in by_edge, f"duplicate geometry coverage entry {edge!r}")
        by_edge[edge] = entry
    return by_edge


def _validate_composite_entry(entry: dict) -> None:
    _require(
        entry.get("category") == "serial",
        "composite LMC edge must be a serial span",
    )
    _require(
        entry.get("span_m") == _COMPOSITE_SPAN_M
        and entry.get("covered_m") == _LMC_REMAINDER_SPAN_M
        and entry.get("gap_m") == _FLUME_SPAN_M,
        "composite LMC span/coverage does not match the reviewed 170 m flume "
        "plus 1,450 m surveyed section",
    )
    missing = entry.get("missing")
    _require(
        isinstance(missing, list)
        and len(missing) == 1
        and missing[0].get("from_km") == _FLUME_FROM_KM
        and missing[0].get("to_km") == _FLUME_TO_KM,
        "composite LMC missing chainage is not the reviewed 0+000-0+170 flume",
    )


def _validate_canal_geometry_agreement(
    canal_geometry: dict, coverage: dict[tuple[str, str], dict]
) -> None:
    """The independently emitted survey geometry must agree with the split
    and with every serial span the coverage claims."""
    reaches = canal_geometry.get("reaches")
    _require(
        isinstance(reaches, list) and len(reaches) == 41,
        "canal geometry must carry the 41 reviewed serial reach records",
    )
    reach_by_edge = {
        (reach.get("from_node"), reach.get("to_node")): reach for reach in reaches
    }
    for edge, entry in coverage.items():
        if entry.get("category") != "serial":
            continue
        record = reach_by_edge.get(edge)
        _require(
            record is not None,
            f"serial edge {edge!r} has no canal geometry reach record",
        )
        _require(
            record.get("span_m") == entry.get("span_m")
            and record.get("covered_m") == entry.get("covered_m"),
            f"serial edge {edge!r} span/coverage disagrees between geometry "
            "coverage and canal geometry",
        )
    composite = [
        reach
        for reach in reaches
        if (reach.get("from_node"), reach.get("to_node")) == _COMPOSITE_EDGE
    ]
    _require(
        len(composite) == 1,
        "canal geometry must carry exactly one composite LMC reach record",
    )
    record = composite[0]
    _require(
        record.get("span_m") == _COMPOSITE_SPAN_M
        and record.get("covered_m") == _LMC_REMAINDER_SPAN_M
        and record.get("gap_m") == _FLUME_SPAN_M,
        "canal geometry composite reach disagrees with the reviewed "
        "170 m flume plus 1,450 m surveyed split",
    )
    sections = [
        section
        for section in canal_geometry.get("canal_sections", [])
        if (section.get("from_node"), section.get("to_node")) == _COMPOSITE_EDGE
    ]
    _require(
        len(sections) == 1
        and sections[0].get("from_km") == _FLUME_TO_KM
        and sections[0].get("to_km") == "1+620"
        and sections[0].get("geometry", {}).get("length_m")
        == _LMC_REMAINDER_SPAN_M,
        "the surveyed composite LMC section must span exactly 0+170-1+620 "
        "with 1,450 m of geometry",
    )


def derive_routing_topology(
    network: dict, geometry_coverage: dict, canal_geometry: dict
) -> RoutingTopology:
    metadata = network.get("metadata", {})
    source_sha256 = metadata.get("source_sha256")
    _require(
        isinstance(source_sha256, str) and len(source_sha256) == 64,
        "network metadata must carry the workbook source_sha256",
    )
    coverage_sha = geometry_coverage.get("metadata", {}).get("source_sha256")
    _require(
        coverage_sha == source_sha256,
        "geometry coverage and network derive from different workbooks",
    )

    edges = [tuple(edge) for edge in network.get("edges", [])]
    _require(bool(edges), "network must contain edges")
    coverage = _coverage_by_edge(geometry_coverage)
    _require(
        set(coverage) == set(edges),
        "geometry coverage edges must match canonical network edges exactly",
    )

    partial_edges = [
        edge for edge, entry in coverage.items() if entry.get("status") == "partial"
    ]
    _require(
        partial_edges == [_COMPOSITE_EDGE],
        f"expected exactly one reviewed partial edge {_COMPOSITE_EDGE}, "
        f"found {partial_edges!r}",
    )
    _validate_composite_entry(coverage[_COMPOSITE_EDGE])
    canal_geometry_sha = canal_geometry.get("metadata", {}).get("source_sha256")
    _require(
        canal_geometry_sha == source_sha256,
        "canal geometry and network derive from different workbooks",
    )
    _validate_canal_geometry_agreement(canal_geometry, coverage)

    withdrawal_nodes = {
        downstream
        for (upstream, downstream), entry in coverage.items()
        if entry.get("category") == "offtake"
    }
    _require(
        withdrawal_nodes == set(_EXPECTED_WITHDRAWAL_NODES),
        f"withdrawal structures {sorted(withdrawal_nodes)} do not match the "
        f"reviewed set {sorted(_EXPECTED_WITHDRAWAL_NODES)}",
    )

    waste_way_entry = coverage.get((_WASTE_WAY_PARENT, _WASTE_WAY_NODE))
    _require(
        waste_way_entry is not None
        and waste_way_entry.get("category") == "offtake",
        "Waste Way offtake edge is missing from geometry coverage",
    )
    _require(
        waste_way_entry.get("km") == _WASTE_WAY_KM,
        "Waste Way is no longer surveyed at 0+170; the reviewed virtual "
        "junction placement does not apply",
    )

    elements: list[RoutingElement] = []
    for edge in edges:
        upstream, downstream = edge
        entry = coverage[edge]
        category = entry.get("category")
        canal = entry.get("canal")
        if category == "source":
            elements.append(
                _element(
                    RoutingRole.BOUNDARY,
                    upstream,
                    downstream,
                    (edge,),
                    canal,
                    None,
                    RoutingGeometryStatus.NOT_APPLICABLE,
                )
            )
        elif category == "junction_head":
            elements.append(
                _element(
                    RoutingRole.BRANCH_STRUCTURE,
                    upstream,
                    downstream,
                    (edge,),
                    canal,
                    None,
                    RoutingGeometryStatus.NOT_APPLICABLE,
                )
            )
        elif category == "offtake":
            parent = (
                VIRTUAL_JUNCTION
                if downstream == _WASTE_WAY_NODE
                else upstream
            )
            located_at_km = entry.get("km")
            _require(
                isinstance(located_at_km, str) and located_at_km,
                f"offtake edge {edge!r} must carry its surveyed chainage",
            )
            elements.append(
                _element(
                    RoutingRole.WITHDRAWAL_STRUCTURE,
                    parent,
                    downstream,
                    (edge,),
                    canal,
                    None,
                    RoutingGeometryStatus.NOT_APPLICABLE,
                    located_at_km,
                )
            )
        elif category == "serial":
            if edge == _COMPOSITE_EDGE:
                elements.append(
                    _element(
                        RoutingRole.TRANSPORT,
                        upstream,
                        VIRTUAL_JUNCTION,
                        (edge,),
                        canal,
                        float(_FLUME_SPAN_M),
                        RoutingGeometryStatus.UNAVAILABLE,
                    )
                )
                elements.append(
                    _element(
                        RoutingRole.TRANSPORT,
                        VIRTUAL_JUNCTION,
                        downstream,
                        (edge,),
                        canal,
                        float(_LMC_REMAINDER_SPAN_M),
                        RoutingGeometryStatus.SURVEYED,
                    )
                )
            else:
                _require(
                    entry.get("status") == "full",
                    f"serial edge {edge!r} has unreviewed status "
                    f"{entry.get('status')!r}",
                )
                span_m = entry.get("span_m")
                _require(
                    isinstance(span_m, (int, float)) and span_m > 0,
                    f"serial edge {edge!r} must carry a positive span_m",
                )
                elements.append(
                    _element(
                        RoutingRole.TRANSPORT,
                        upstream,
                        downstream,
                        (edge,),
                        canal,
                        float(span_m),
                        RoutingGeometryStatus.SURVEYED,
                    )
                )
        else:
            raise RoutingTopologyError(
                f"edge {edge!r} has unreviewed category {category!r}"
            )

    _validate_derived_elements(tuple(elements))
    return RoutingTopology(
        schema_version=SCHEMA_VERSION,
        source_sha256=source_sha256,
        elements=tuple(elements),
        content_hash=_content_hash(source_sha256, tuple(elements)),
    )


def build_routing_topology(
    elements: tuple[RoutingElement, ...], source_sha256: str = "0" * 64
) -> RoutingTopology:
    """Structurally validated topology from explicit elements.

    Used for synthetic topologies in tests and tooling; the canonical
    counts (1/42/13/3) are enforced only by derive_routing_topology().
    """
    _validate_structure(tuple(elements))
    return RoutingTopology(
        schema_version=SCHEMA_VERSION,
        source_sha256=source_sha256,
        elements=tuple(elements),
        content_hash=_content_hash(source_sha256, tuple(elements)),
    )


def _validate_derived_elements(elements: tuple[RoutingElement, ...]) -> None:
    counts = {role.value: 0 for role in RoutingRole}
    for element in elements:
        counts[element.role.value] += 1
    _require(
        counts == _EXPECTED_ROLE_COUNTS,
        f"derived role counts {counts} do not match the reviewed topology "
        f"{_EXPECTED_ROLE_COUNTS}",
    )
    _validate_structure(elements)


def _validate_structure(elements: tuple[RoutingElement, ...]) -> None:
    _require(bool(elements), "routing topology must not be empty")
    for element in elements:
        expected_id = _element_id(
            element.role, element.upstream_node_id, element.downstream_node_id
        )
        _require(
            element.element_id == expected_id,
            f"element_id {element.element_id!r} does not match its role and "
            f"endpoints (expected {expected_id!r})",
        )
    element_ids = [element.element_id for element in elements]
    _require(
        len(element_ids) == len(set(element_ids)),
        "derived element ids are not unique",
    )

    children = [element.downstream_node_id for element in elements]
    _require(
        len(children) == len(set(children)) and ROOT not in children,
        "derived topology is not a rooted tree: duplicate or root child",
    )
    parent_of = {
        element.downstream_node_id: element.upstream_node_id for element in elements
    }
    nodes = set(children)
    for node in nodes:
        cursor = node
        seen: set[str] = set()
        while cursor != ROOT:
            _require(
                cursor not in seen, f"derived topology has a cycle at {node!r}"
            )
            seen.add(cursor)
            _require(
                cursor in parent_of,
                f"derived topology is disconnected at {cursor!r}",
            )
            cursor = parent_of[cursor]
