from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import AliasChoices, Field, field_validator

# Well-known weak/default signing secrets that must never sign a live token.
_WEAK_JWT_SECRET_DENYLIST = frozenset(
    {
        "change-me",
        "changeme",
        "secret",
        "password",
        "dev",
        "development",
        "test",
        "testing",
        "default",
        "jwt-secret",
        "your-secret-key",
    }
)


def assert_strong_secret(v: str, field: str) -> str:
    """Fail closed on a weak signing secret so no live token is ever signed with a guessable
    key. Shared by the operator ``jwt_secret_key`` and the PR 6.3a service-token secret so the
    two can never drift in strength (root CLAUDE.md: no second copy of an algorithm)."""
    if not isinstance(v, str) or not v.strip():
        raise ValueError(f"{field} must be a non-blank secret")
    if len(v.encode("utf-8")) < 32:
        raise ValueError(f"{field} must be at least 32 bytes of entropy")
    if v.strip().lower() in _WEAK_JWT_SECRET_DENYLIST:
        raise ValueError(f"{field} is a well-known weak/default value")
    # Reject a short unit repeated to reach the length (e.g. "ab"*16), guessable despite >=32B.
    n = len(v)
    for period in range(1, n // 4 + 1):
        if n % period == 0 and v == v[:period] * (n // period):
            raise ValueError(f"{field} must not be a short repeated pattern")
    if len(set(v)) < 5:
        raise ValueError(f"{field} has too little character diversity")
    return v


class Settings(BaseSettings):
    # Service Configuration
    service_name: str = "scheduler"
    service_port: int = 3021
    log_level: str = "INFO"
    environment: str = "development"
    # Backwards-compatibility aliases
    app_name: str = "scheduler"
    app_version: str = "0.1.0"
    allowed_origins: List[str] = ["*"]

    # Database
    # The runtime MUST serve the SAME database the migration runner + PM2 target.
    # migrate.py and PM2 both use POSTGRES_URL, so the runtime consumes it as the
    # canonical source, falling back to DATABASE_URL only when POSTGRES_URL is
    # absent. A deployment that sets both can therefore never run the service
    # against a different DB than migrations were applied to.
    database_url: str = Field(
        validation_alias=AliasChoices("POSTGRES_URL", "DATABASE_URL")
    )
    database_pool_size: int = 20
    database_max_overflow: int = 10

    # Redis
    redis_url: str
    redis_password: Optional[str] = None
    redis_pool_size: int = 10

    # Service URLs
    ros_service_url: str
    gis_service_url: str
    flow_monitoring_url: str
    ros_gis_url: str
    weather_service_url: str
    auth_service_url: str

    # PR 4.3c-1: path to the 6.1a device-capability snapshot the scheduler pins
    # when activating a plan. Unset -> the empty dark default (zero machine-capable
    # gates), so activation fails closed until a real snapshot is configured.
    scheduler_device_capability_snapshot_path: Optional[str] = None

    # JWT Configuration
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    # Control-plane trust hardening (PR 4.4a-1): issuer/audience/mode are
    # REQUIRED (no default) so a deployment cannot silently run without an
    # explicit claim policy. `strict` mints trusted approvals; `compat` cannot.
    jwt_issuer: str
    jwt_audience: str
    jwt_access_token_type: str = "access"
    jwt_claim_policy_mode: str
    jwt_clock_skew_seconds: int = 30
    control_plan_authorization_policy_version: str = "control-plan-rbac-v1"

    # Optimization Settings
    optimization_timeout_seconds: int = 60
    max_parallel_optimizations: int = 5
    schedule_horizon_days: int = 7
    control_model_step_seconds: int = Field(default=300, gt=0)
    control_max_intermediate_trims: int = Field(default=1, ge=0, le=2)
    # PR 5.2b open-loop execution: the worker only claims intents in "shadow" mode;
    # "disabled" is dark (no claiming); "operator_approved" is DEFINED but REFUSED in
    # 5.2 (execute path is 7.x). Nothing here dispatches or actuates.
    control_execution_mode: str = "disabled"
    control_authority_lease_hours: int = Field(default=24, gt=0)
    control_premove_validation_seconds: int = Field(default=300, ge=0)

    # PR 6.3a — shadow dispatcher (DARK-by-default). The SCADA machine-boundary base URL and
    # the DEDICATED service-token secret (cryptographically SEPARATE from jwt_secret_key — a
    # leaked operator secret must not forge a service token). Both optional: either unset ->
    # the dispatcher builds no SCADA client and dispatches nothing, exactly like the rest of
    # the machine-authority surface behind the external trust cutover. issuer/audience default
    # to what SCADA's verifier expects. Token max-age must stay within SCADA's maxAge (5m).
    scheduler_scada_base_url: Optional[str] = None
    scheduler_service_jwt_secret: Optional[str] = None
    scheduler_service_jwt_issuer: str = "munbon-scheduler"
    scheduler_service_jwt_audience: str = "munbon-scada-machine-boundary"
    scheduler_service_jwt_subject: str = "scheduler-shadow-dispatcher"
    # Capped at SCADA's DEFAULT maxAge (5m): the minted token's lifetime must stay <= SCADA's
    # SCHEDULER_SERVICE_JWT_MAX_AGE or SCADA rejects it (401). Keep both sides at 300 unless an
    # operator raises SCADA's maxAge in lockstep. (SCADA's verifier uses no clock-skew tolerance,
    # so mint fresh per call — which the dispatcher does — and keep the two clocks NTP-synced.)
    scheduler_service_jwt_max_age_seconds: int = Field(default=300, gt=0, le=300)

    # PR 6.3b — shadow readback reconciliation, DARK-by-default. off -> no reads, no observations,
    # no holds (byte-identical to no-6.3b). observe -> read + record an observation, NEVER hold.
    # enforce -> read + record + HOLD the plan on a fresh readback that drifts from the plan's
    # expected baseline. Kept off until D6 provides real per-gate readback + baselines.
    control_readback_reconciliation_mode: str = "off"

    # Field Team Configuration
    max_operations_per_day: int = 30
    default_operation_time_minutes: int = 15
    travel_speed_kmh: float = 40.0

    # Real-time Monitoring
    gate_state_check_interval: int = 300  # 5 minutes
    deviation_threshold_percent: float = 10.0
    adaptation_cooldown_minutes: int = 15

    # Performance
    enable_cache: bool = True
    cache_ttl_seconds: int = 3600
    max_batch_size: int = 100

    # CORS
    cors_origins: List[str] = ["*"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v):
        if isinstance(v, str):
            return [i.strip() for i in v.split(",") if i.strip()]
        return v

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
        # Allow population by field name too, so `Settings(database_url=...)`
        # keeps working alongside the POSTGRES_URL/DATABASE_URL validation alias.
        populate_by_name=True,
    )

    @field_validator("jwt_secret_key")
    @classmethod
    def reject_weak_jwt_secret(cls, v: str) -> str:
        """Fail closed: a weak signing secret breaks Settings construction so
        the service can never boot on a guessable key."""
        return assert_strong_secret(v, "jwt_secret_key")

    @field_validator("scheduler_service_jwt_secret")
    @classmethod
    def reject_weak_service_secret(cls, v: Optional[str]) -> Optional[str]:
        """PR 6.3a: the DEDICATED SCADA service-token secret is optional (unset -> dispatcher
        dark), but when present it must be as strong as the operator secret."""
        if v is None:
            return v
        return assert_strong_secret(v, "scheduler_service_jwt_secret")

    @field_validator("jwt_algorithm")
    @classmethod
    def require_hs256(cls, v: str) -> str:
        if v != "HS256":
            raise ValueError("jwt_algorithm must be pinned to HS256")
        return v

    @field_validator("jwt_claim_policy_mode")
    @classmethod
    def require_known_policy_mode(cls, v: str) -> str:
        if v not in ("compat", "strict"):
            raise ValueError(
                "jwt_claim_policy_mode must be exactly 'compat' or 'strict'"
            )
        return v

    @field_validator("control_readback_reconciliation_mode")
    @classmethod
    def require_known_readback_mode(cls, v: str) -> str:
        if v not in ("off", "observe", "enforce"):
            raise ValueError(
                "control_readback_reconciliation_mode must be 'off', 'observe', or 'enforce'"
            )
        return v

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, v: str) -> str:
        if not isinstance(v, str):
            return v
        # Upgrade sync psycopg2 URL to asyncpg
        if v.startswith("postgresql://") and "+asyncpg" not in v:
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v


settings = Settings()
