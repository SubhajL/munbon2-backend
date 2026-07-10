"""
Wave 1.7 — Hypothesis property tests over the core physics kernel. Example-based
suites lock known cases; these lock the INVARIANTS: flow monotonicity, the
fail-closed inverse round-trip (F-01b), grammar-derived spanning trees (F-11b),
and demand/loss conservation (A1–A3 + B5 seam).

Run isolated from the service root:
    PYTHONPATH=src pytest --noconftest -o addopts="" tests/unit/test_property_physics.py
"""
import math

import pytest

from hypothesis import assume, given, settings, strategies as st

# Deterministic, storage-free runs: CI checkouts are ephemeral (no example DB to
# learn from) and a derandomized sweep cannot flake on a rare draw.
settings.register_profile("flowmon", database=None, derandomize=True)
settings.load_profile("flowmon")

from core.demand_aggregation import required_flow_per_reach  # noqa: E402
from core.gate_flow import (  # noqa: E402
    build_gate_flow_calibration,
    gate_flow_m3s,
    min_deliverable_flow_m3s,
    required_opening_m,
)
from core.network_topology import edges_from_names, is_spanning_tree  # noqa: E402
from core.node_id import format_gate_tuples, normalize_gate_id, parse_gate_id  # noqa: E402

# Field-plausible calibration/hydraulic ranges: k1 spans the measured Munbon gates
# (0.78–1.57) with margin; k2 stays negative per the rejected-k2>0 guard (PR #26).
CALIBRATIONS = st.builds(
    lambda k1, k2, width, max_open: build_gate_flow_calibration(
        k1=k1, k2=k2, confidence=0.95, width_m=width, sill_m=218.0, max_opening_m=max_open
    ),
    k1=st.floats(0.3, 3.0),
    k2=st.floats(-4.0, -0.05),
    width=st.floats(0.5, 6.0),
    max_open=st.floats(0.5, 4.0),
)
HEADS = st.tuples(
    st.floats(0.3, 5.0),    # upstream depth over sill (m)
    st.floats(0.01, 2.0),   # driving head difference (m)
).map(lambda t: (218.0 + t[0], 218.0 + t[0] - min(t[1], t[0])))


class TestFlowLawMonotonicity:
    @settings(max_examples=200)
    @given(cal=CALIBRATIONS, heads=HEADS, data=st.data())
    def test_flow_is_non_decreasing_in_opening(self, cal, heads, data):
        upstream, downstream = heads
        lo = data.draw(st.floats(0.0, cal.max_opening_m), label="lo")
        hi = data.draw(st.floats(lo, cal.max_opening_m), label="hi")
        q_lo = gate_flow_m3s(cal, upstream, downstream, lo)
        q_hi = gate_flow_m3s(cal, upstream, downstream, hi)
        assert q_hi >= q_lo - 1e-9

    @settings(max_examples=200)
    @given(cal=CALIBRATIONS, heads=HEADS, opening_frac=st.floats(0.0, 1.0))
    def test_flow_is_finite_and_non_negative(self, cal, heads, opening_frac):
        upstream, downstream = heads
        q = gate_flow_m3s(cal, upstream, downstream, opening_frac * cal.max_opening_m)
        assert q >= 0.0 and math.isfinite(q)

    @settings(max_examples=200)
    @given(cal=CALIBRATIONS, heads=HEADS)
    def test_zero_opening_passes_zero_flow(self, cal, heads):
        upstream, downstream = heads
        assert gate_flow_m3s(cal, upstream, downstream, 0.0) == 0.0


class TestInverseRoundTrip:
    @settings(max_examples=200)
    @given(cal=CALIBRATIONS, heads=HEADS, frac=st.floats(0.05, 1.0))
    def test_feasible_targets_round_trip_through_the_inverse(self, cal, heads, frac):
        # Any target between the Cs-floor discharge and max-opening flow must come
        # back achievable within tolerance when the returned opening is replayed
        # through the forward law (F-01b: never overdeliver, never lie).
        upstream, downstream = heads
        floor = min_deliverable_flow_m3s(cal, upstream, downstream)
        q_max = gate_flow_m3s(cal, upstream, downstream, cal.max_opening_m)
        # keep only gates with an invertible band (assume() reports the hit rate —
        # an early return would silently hollow the property out)
        assume(q_max > floor and q_max > 0)
        q_target = floor + frac * (q_max - floor)
        opening, info = required_opening_m(cal, upstream, downstream, q_target)
        assert info["feasible"] is True
        replayed = gate_flow_m3s(cal, upstream, downstream, opening)
        assert replayed == pytest.approx(q_target, rel=0.02, abs=5e-3)

    @settings(max_examples=200)
    @given(cal=CALIBRATIONS, heads=HEADS, frac=st.floats(0.01, 0.9))
    def test_below_floor_targets_fail_closed(self, cal, heads, frac):
        # strictly below the floor band (<= 0.9*floor): the inverse must refuse —
        # a "feasible" answer here IS the overdelivery lie F-01b exists to prevent.
        upstream, downstream = heads
        floor = min_deliverable_flow_m3s(cal, upstream, downstream)
        assume(floor > 1e-6)
        q_target = frac * floor
        opening, info = required_opening_m(cal, upstream, downstream, q_target)
        assert info["feasible"] is False
        assert opening == 0.0


def _tree_names(draw):
    """Grow a random gate-id tree per the naming grammar: each new valve either
    extends a canal serially ((a, p) -> (a, p+1)) or opens a new branch off an
    existing valve (append (b, 0))."""
    names = [[(0, 0)]]
    branch_counter = {}
    n = draw(st.integers(min_value=0, max_value=25))
    for _ in range(n):
        parent = draw(st.sampled_from(names))
        extend = draw(st.booleans())
        if extend:
            child = parent[:-1] + [(parent[-1][0], parent[-1][1] + 1)]
            if child in names:
                continue
        else:
            key = tuple(map(tuple, parent))
            branch = branch_counter.get(key, 0) + 1
            branch_counter[key] = branch
            child = parent + [(branch, 0)]
        names.append(child)
    return [format_gate_tuples(t) for t in names]


class TestGrammarDerivedTopology:
    @settings(max_examples=100)
    @given(data=st.data())
    def test_edges_from_names_always_yields_a_spanning_tree(self, data):
        names = _tree_names(data.draw)
        edges = edges_from_names(names)
        assert is_spanning_tree(edges)
        assert len(edges) == len(names)

    @settings(max_examples=100)
    @given(data=st.data())
    def test_aggregation_conserves_demand_on_derived_trees(self, data):
        names = _tree_names(data.draw)
        edges = edges_from_names(names)
        demands = {
            name: data.draw(
                st.floats(0.0, 50.0), label=f"demand {name}"
            )
            for name in names
        }
        flow = required_flow_per_reach(edges, demands)
        head = sum(q for (u, _), q in flow.items() if u == "S")
        assert head == pytest.approx(sum(demands.values()))
        # every reach carries at least its subtree's own terminal demand
        for (_, v), q in flow.items():
            assert q >= demands[v] - 1e-9

    @settings(max_examples=100)
    @given(data=st.data(), loss_per_reach=st.floats(0.0, 5.0))
    def test_constant_reach_loss_adds_exactly_once_per_reach(self, data, loss_per_reach):
        names = _tree_names(data.draw)
        edges = edges_from_names(names)
        demands = {name: 1.0 for name in names}
        flow = required_flow_per_reach(
            edges, demands, reach_loss=lambda u, v, q: loss_per_reach
        )
        head = sum(q for (u, _), q in flow.items() if u == "S")
        assert head == pytest.approx(
            sum(demands.values()) + loss_per_reach * len(edges)
        )


class TestNodeIdGrammar:
    @settings(max_examples=200)
    @given(data=st.data())
    def test_parse_format_round_trip_and_spacing_invariance(self, data):
        tuples_ = [
            (data.draw(st.integers(0, 9)), data.draw(st.integers(0, 20)))
            for _ in range(data.draw(st.integers(1, 4)))
        ]
        compact = format_gate_tuples(tuples_)
        assert parse_gate_id(compact) == tuples_
        spaced = compact.replace("(", " ( ").replace(";", " ; ").replace(",", " , ")
        assert normalize_gate_id(spaced) == compact
        assert normalize_gate_id(normalize_gate_id(spaced)) == compact
