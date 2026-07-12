"""
api.control — C9 control endpoints exposing the NetworkFlowController aggregation engine.

`POST /plan` turns a per-node water demand into the required flow on every network reach
(A1-A3 graph-descendants aggregation, optional B5 conveyance loss). It fails closed on bad
demand (unknown / negative / source-node) with HTTP 400, and never fabricates demand — this
retires the old hardcoded 25.0 m3/s stub (F-03/C9).

`flow_controller` is a module-level singleton set once at app startup (main.py lifespan),
mirroring the api.gates pattern. This module imports only schemas + core + fastapi (no db /
settings) so it stays unit-testable in isolation.
"""
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException

from core.network_flow_controller import NetworkFlowController
from core.network_topology import NetworkTopologyError
from core.node_id import normalize_node_id
from schemas.control import PlanRequest, PlanResponse, ReachChainageGap, ReachFlow

logger = structlog.get_logger()
router = APIRouter()

# Initialized in main.py lifespan; None until then.
flow_controller: Optional[NetworkFlowController] = None


def get_flow_controller() -> NetworkFlowController:
    """Dependency: the loaded controller, or 503 if the service has not initialized it."""
    if flow_controller is None:
        raise HTTPException(status_code=503, detail="Flow controller not initialized")
    return flow_controller


@router.post("/plan", response_model=PlanResponse)
async def plan(
    request: PlanRequest,
    controller: NetworkFlowController = Depends(get_flow_controller),
) -> PlanResponse:
    """Required flow on every reach to serve `request.demands` (fail-closed on bad demand)."""
    try:
        reach_flow = controller.required_flow_per_reach(
            request.demands,
            apply_losses=request.apply_losses,
            charge_dry_reaches=request.charge_dry_reaches,
            always_wet=request.always_wet,
        )
    except NetworkTopologyError as exc:  # server/config error (subclass of ValueError) -> 503
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:  # unknown / negative / non-finite / source demand -> client error
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    head_flow = sum(flow for (upstream, _), flow in reach_flow.items() if upstream == "S")
    # Response ids are CANONICAL COMPACT (Wave 1.2) — one stable contract for consumers,
    # independent of the survey's irregular spacing in the network file.
    missing = (
        [
            [normalize_node_id(u), normalize_node_id(v)]
            for u, v in sorted(controller.reaches_missing_geometry)
        ]
        if request.apply_losses
        else []
    )
    # Partially surveyed reaches take zero loss on their unsurveyed chainage —
    # say so, or the head-gate figure reads as full loss coverage (2.1b).
    gaps = (
        [
            ReachChainageGap(upstream=u, downstream=v, gap_m=gap)
            for (u, v), gap in sorted(controller.reaches_with_chainage_gaps.items())
        ]
        if request.apply_losses
        else []
    )
    return PlanResponse(
        reaches=[
            ReachFlow(
                upstream=normalize_node_id(u),
                downstream=normalize_node_id(v),
                required_flow_m3s=q,
            )
            for (u, v), q in reach_flow.items()
        ],
        head_flow_m3s=head_flow,
        apply_losses=request.apply_losses,
        charge_dry_reaches=request.charge_dry_reaches,
        reaches_missing_geometry=missing,
        reaches_with_chainage_gaps=gaps,
    )
