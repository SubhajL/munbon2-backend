import asyncio
import os

import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import make_asgi_app

from config import settings
from api import router as api_router
from api import gates as gates_api
from api import control as control_api
from api import hydraulics as hydraulics_api
from core.logging import setup_logging
from core.metrics import setup_metrics
from core.config_loader import (
    file_sha256,
    load_gate_calibrations_config,
    load_routing_topology,
)
from core.commandability_approval import (
    is_commandability_approved,
    load_commandability_approval,
    verify_commandability_approval,
)
from core.model_release import load_configured_hydraulic_model_release
from core.network_flow_controller import NetworkFlowController
from core.prediction_engine import (
    PredictionEngineError,
    build_prediction_engine_descriptor,
    load_prediction_engine_descriptor,
)
from core.reach_response import reach_responses_from_model_release
from db.connections import DatabaseManager
from db.demand_store_postgres import PostgresDemandStore

# Kafka consumer is optional; import lazily when configured
from controllers.dual_mode_gate_controller import DualModeGateController
from services.design_profile_service import DesignProfileService
from services.control_prediction_service import (
    ControlPredictionService,
    build_withdrawal_structure_max_flow_map,
)


# Setup structured logging
setup_logging(settings.log_level)
logger = structlog.get_logger()

# Global instances
db_manager = DatabaseManager()
kafka_consumer = None
gate_controller = None


def _load_prediction_engine_descriptor(descriptor_path: str, service_root: str):
    """Load the committed engine descriptor and confirm it still matches the
    LIVE source bytes. Fail CLOSED (return None) on a missing/malformed file, an
    unbuildable source, or ANY drift from the running engine.

    Serving a stale descriptor would advertise engine A while the process runs
    engine B — a false provenance / wrong-replay risk. When the descriptor is
    None, fresh identity-v2 writes, require-v2, and model-snapshot construction
    all fail closed at request time, while v1 replays (which never need the
    current descriptor) keep working."""
    try:
        descriptor = load_prediction_engine_descriptor(descriptor_path)
    except (PredictionEngineError, OSError) as exc:
        logger.warning(
            "Prediction engine descriptor unavailable",
            path=descriptor_path,
            error=str(exc),
        )
        return None
    try:
        rebuilt = build_prediction_engine_descriptor(service_root)
    except (PredictionEngineError, OSError) as exc:
        logger.error(
            "Prediction engine descriptor cannot be verified against the live "
            "source; refusing to serve it",
            path=descriptor_path,
            error=str(exc),
        )
        return None
    if rebuilt.get("content_hash") != descriptor.get("content_hash"):
        logger.error(
            "Prediction engine descriptor drifted from source; refusing to "
            "serve a stale identity (re-pin the descriptor)",
            committed_build_digest=descriptor.get("build_digest"),
            source_build_digest=rebuilt.get("build_digest"),
        )
        return None
    logger.info(
        "Prediction engine descriptor loaded",
        engine_id=descriptor["engine_id"],
        build_digest=descriptor["build_digest"],
    )
    return descriptor


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global gate_controller, kafka_consumer

    logger.info("Starting Flow Monitoring Service", port=settings.port)

    # Startup
    try:
        # Initialize database connections
        await db_manager.connect_all()
        logger.info("Database connections established")

        # Canonical configs, anchored to this file (the old cwd-relative paths only
        # worked when booted from the service root).
        config_dir = os.path.join(os.path.dirname(__file__), "config")
        network_file = os.path.join(config_dir, "network.json")
        geometry_file = os.path.join(config_dir, "canal_geometry.json")
        calibration_file = os.path.join(config_dir, "gate_calibrations.json")
        zone_topology_file = os.path.join(config_dir, "zone_topology.json")

        # Legacy dual-stack quarantine (Wave 1.5, Decision 2): /api/v1/gates/* stays
        # OFF unless explicitly enabled, and when enabled it runs on the canonical
        # configs — never the fragmented munbon_network_final.json (2/57 reachable).
        if settings.gates_api_enabled:
            gate_controller = DualModeGateController(
                db_manager, network_file, geometry_file
            )
            gates_api.gate_controller = gate_controller
            gates_api.disabled_reason = None
            logger.info("Gate controller initialized (legacy stack, canonical configs)")
        else:
            gates_api.gate_controller = None
            gates_api.disabled_reason = (
                "legacy gates API disabled by default (PROGRAM_REVIEW_2026-07-09 "
                "decision 2); set GATES_API_ENABLED=true to re-enable it until the "
                "F-02 SCADA bridge replaces this surface"
            )
            logger.info("Legacy gates API disabled (GATES_API_ENABLED=false)")

        # Wire the canonical demand->flow engine (A1-A3 / F-11b / B5) for /api/v1/control/plan.
        flow_controller = NetworkFlowController(
            network_file, geometry_file, calibration_file
        )
        control_api.flow_controller = flow_controller
        logger.info("Flow controller (demand->reach aggregation) initialized")

        # Typed derived routing topology (PR 2.1a): loads unconditionally and
        # fails startup on any drift, even when no model release is configured.
        geometry_coverage_file = os.path.join(config_dir, "geometry_coverage.json")
        routing_topology_file = os.path.join(config_dir, "routing_topology.json")
        app.state.routing_topology = load_routing_topology(
            routing_topology_file,
            network_file,
            geometry_coverage_file,
            geometry_file,
        )
        logger.info(
            "Routing topology loaded",
            elements=len(app.state.routing_topology.elements),
            transport_reaches=len(app.state.routing_topology.transport_reach_ids()),
            content_hash=app.state.routing_topology.content_hash,
        )
        app.state.model_config_sha256 = {
            **flow_controller.config_sha256,
            "geometry_coverage": file_sha256(geometry_coverage_file),
            "routing_topology": file_sha256(routing_topology_file),
        }

        app.state.hydraulic_model_release = load_configured_hydraulic_model_release(
            settings.hydraulic_model_release_path,
            app.state.routing_topology.transport_reach_ids(),
        )
        if app.state.hydraulic_model_release is None:
            app.state.reach_responses = ()
            logger.info("Hydraulic model release unavailable (no path configured)")
        else:
            app.state.reach_responses = reach_responses_from_model_release(
                app.state.hydraulic_model_release
            )
            logger.info(
                "Hydraulic model release loaded",
                release_id=app.state.hydraulic_model_release.release_id,
                content_hash=app.state.hydraulic_model_release.content_hash,
                reach_response_members=len(app.state.reach_responses),
            )

        # PR 4.4b-1: load the content-addressed prediction ENGINE descriptor.
        # Missing/drifted is a boot warning (like the release) — a prediction
        # in require-v2 without it fails closed at request time.
        service_root = os.path.dirname(os.path.dirname(__file__))
        descriptor_path = settings.prediction_engine_descriptor_path or os.path.join(
            service_root, "data", "prediction-engine", "prediction-engine-v1.json"
        )
        app.state.prediction_engine_descriptor = _load_prediction_engine_descriptor(
            descriptor_path, service_root
        )
        app.state.commandability_approval = load_commandability_approval(
            settings.commandability_approval_path
        )
        if app.state.commandability_approval is not None:
            verify_commandability_approval(
                app.state.commandability_approval,
                app.state.hydraulic_model_release,
                app.state.prediction_engine_descriptor,
                app.state.model_config_sha256,
            )
        logger.info(
            "Hydraulic commandability approval evaluated",
            state=(
                "approved"
                if is_commandability_approved(app.state.commandability_approval)
                else (
                    "not_approved"
                    if app.state.commandability_approval is not None
                    else "unconfigured"
                )
            ),
        )
        app.state.prediction_identity_rollout_mode = (
            settings.prediction_identity_rollout_mode
        )

        withdrawal_capacity = build_withdrawal_structure_max_flow_map(
            app.state.routing_topology,
            load_gate_calibrations_config(calibration_file),
        )
        app.state.control_prediction_service = ControlPredictionService(
            routing_topology=app.state.routing_topology,
            reach_responses=app.state.reach_responses,
            structure_max_flow_m3s_by_id=withdrawal_capacity,
            maximum_horizon_seconds=(
                None
                if app.state.hydraulic_model_release is None
                else app.state.hydraulic_model_release.operating_envelope.maximum_horizon_seconds
            ),
            prediction_engine_descriptor=app.state.prediction_engine_descriptor,
        )
        logger.info(
            "Control prediction service initialized (non-commanding)",
            prediction_identity_rollout_mode=(
                app.state.prediction_identity_rollout_mode
            ),
            prediction_engine_loaded=(
                app.state.prediction_engine_descriptor is not None
            ),
        )

        control_api.design_profile_service = DesignProfileService(
            network_file,
            geometry_file,
            calibration_file,
            zone_topology_file,
        )
        logger.info("Static all-zone design-profile service initialized")

        # Wave 2.4: append-only versioned demand/allocation/delivery stores behind
        # /api/v1/control/demands. ensure_schema is idempotent; a failure here
        # aborts startup — booting without the contract store would fail open.
        demand_store = PostgresDemandStore(db_manager.postgres.pool)
        await demand_store.ensure_schema()
        control_api.demand_store = demand_store
        logger.info("Demand contract store initialized (append-only, ros_gis)")

        # PR 4.1: prediction persistence is MIGRATION-OWNED — no ensure_schema
        # here. Until `python migrations/migrate.py apply
        # 0001_prediction_persistence` has run, the probe returns None and the
        # prediction routes answer 503 (boot is not aborted).
        from db.prediction_repository import (
            create_prediction_repository_if_migrated,
        )

        # Lazy re-probe: a transient DB blip at boot (or a migration applied
        # after boot) must not leave the routes 503 until a restart.
        app.state.prediction_repository_probe = (
            lambda: create_prediction_repository_if_migrated(db_manager.postgres.pool)
        )
        app.state.prediction_repository = (
            await create_prediction_repository_if_migrated(db_manager.postgres.pool)
        )
        if app.state.prediction_repository is None:
            logger.warning(
                "Prediction persistence unavailable: migration "
                "0001_prediction_persistence is not applied"
            )
        else:
            logger.info("Prediction run store initialized (migration-owned)")

        # App-scoped hydraulics service on the same canonical configs (Wave 1.3);
        # replaces per-request construction with a never-connected DatabaseManager.
        from services.hydraulic_service import HydraulicService

        hydraulics_api.hydraulic_service = HydraulicService(db_manager)
        logger.info("Hydraulic service initialized (app-scoped)")

        # Start Kafka consumer only if configured
        if settings.kafka_brokers:
            from services.kafka_consumer import KafkaConsumerService

            kafka_consumer = KafkaConsumerService()
            asyncio.create_task(kafka_consumer.start())
            logger.info("Kafka consumer started")
        else:
            logger.info("Kafka disabled (no KAFKA_BROKERS configured)")

        # Setup metrics
        setup_metrics()

        yield

    finally:
        # Shutdown
        logger.info("Shutting down Flow Monitoring Service")

        control_api.design_profile_service = None

        # Stop Kafka consumer
        if kafka_consumer:
            await kafka_consumer.stop()

        # Close database connections
        await db_manager.disconnect_all()

        logger.info("Cleanup completed")


# Create FastAPI application
app = FastAPI(
    title="Flow Monitoring Service",
    description=(
        "Comprehensive hydraulic monitoring including flow rates, "
        "water volumes, and levels"
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router, prefix=settings.api_prefix)

# Add Prometheus metrics endpoint
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)


@app.get("/health")
async def health_check():
    """Process liveness ONLY — never claims dependency health. Dependency truth
    (DB, loaded release, prediction persistence) lives at `/ready`."""
    return {
        "status": "healthy",
        "service": settings.service_name,
        "version": "1.0.0",
    }


@app.get("/ready")
async def readiness_check():
    """Dependency-truth readiness: 503 unless Postgres is healthy, a valid
    commandable=false release is loaded, the prediction service is initialized,
    and the prediction tables + migration checksum are present. Fail-closed; the
    body carries only safe status strings (no host/cred/exception leaks)."""
    from core.readiness import check_flow_readiness

    result = await check_flow_readiness(app, db_manager)
    body = {
        "status": "ready" if result.ready else "not ready",
        "checks": result.checks,
    }
    if not result.ready:
        return JSONResponse(status_code=503, content=body)
    return body


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": settings.service_name,
        "version": "1.0.0",
        "description": "Flow Monitoring Service for Munbon Irrigation System",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=settings.environment == "development",
        log_level=settings.log_level.lower(),
    )
