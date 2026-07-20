"""
Scheduler Service Client
Handles communication with the scheduler service
"""

from typing import Any, Dict, List, Optional
from uuid import UUID
import httpx
from core import get_logger
from config import settings

logger = get_logger(__name__)


# --- Fail-closed control-plan read errors (PR 4.4) --------------------------
# Distinct from the legacy schedule methods below, which swallow failures into
# None. These NEVER swallow: they raise a typed error carrying the upstream
# status so the BFF route can preserve the exact state (never fabricate).
class SchedulerControlPlanError(RuntimeError):
    """Base for fail-closed scheduler control-plan read failures."""


class SchedulerAuthError(SchedulerControlPlanError):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class SchedulerControlPlanNotFoundError(SchedulerControlPlanError):
    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class SchedulerBadRequestError(SchedulerControlPlanError):
    """The scheduler rejected the request as a CLIENT error (400/422): a stale or
    cross-filter cursor, an invalid lifecycle_state, or a malformed UUID filter.

    These are the caller's fault, not an upstream outage, so the route forwards the
    exact status (422→422, 400→400) instead of masking it as a 502 and firing a
    false outage alert."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class SchedulerUnavailableError(SchedulerControlPlanError):
    """The scheduler store/model is unavailable or unreachable (→ 503)."""


class SchedulerContractError(SchedulerControlPlanError):
    """The scheduler answered with a malformed/non-object body (→ 502)."""


class SchedulerUpstreamError(SchedulerControlPlanError):
    """An unexpected upstream status the BFF cannot classify (→ 502)."""


class SchedulerClient:
    """Client for interacting with Scheduler service"""

    def __init__(
        self,
        base_url: Optional[str] = None,
        *,
        transport: Optional[httpx.AsyncBaseTransport] = None,
        http_client: Optional[httpx.AsyncClient] = None,
    ):
        # Use mock server URL if enabled, otherwise use actual scheduler service URL
        if base_url is not None:
            self.base_url = base_url
        elif settings.use_mock_server:
            self.base_url = f"{settings.mock_server_url}/scheduler"
        else:
            self.base_url = settings.scheduler_url
        self.base_url = self.base_url.rstrip("/")
        # An injectable transport lets tests drive httpx.MockTransport with no
        # network or monkeypatching.
        self._transport = transport
        # A lifespan-owned pooled AsyncClient (PR 4.4a-2): when provided it is
        # REUSED for every read (connection pooling) and never closed here — the
        # app lifespan owns its lifecycle. Without it, each read opens its own
        # short-lived client (the legacy path the tests still exercise).
        self._http_client = http_client
        self.logger = logger.bind(client="scheduler")
        self.timeout = httpx.Timeout(30.0, connect=5.0)
    
    async def get_schedules(
        self, 
        section_id: Optional[str] = None,
        schedule_type: Optional[str] = None,
        status: Optional[str] = None,
        date: Optional[str] = None
    ) -> Optional[List[Dict]]:
        """Get irrigation schedules"""
        try:
            params = {}
            if section_id:
                params["section_id"] = section_id
            if schedule_type:
                params["schedule_type"] = schedule_type
            if status:
                params["status"] = status
            if date:
                params["date"] = date
                
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/api/v1/schedules",
                    params=params
                )
                response.raise_for_status()
                data = response.json()
                return data.get("schedules", [])
        except httpx.HTTPError as e:
            self.logger.error("Failed to get schedules", error=str(e))
            return None
    
    async def create_schedule(self, schedule_data: Dict) -> Optional[Dict]:
        """Create a new irrigation schedule"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/v1/schedules",
                    json=schedule_data
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            self.logger.error("Failed to create schedule", error=str(e))
            return None
    
    async def update_schedule(self, schedule_id: str, updates: Dict) -> Optional[Dict]:
        """Update an existing schedule"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.put(
                    f"{self.base_url}/api/v1/schedules/{schedule_id}",
                    json=updates
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            self.logger.error("Failed to update schedule", 
                            schedule_id=schedule_id, error=str(e))
            return None
    
    async def get_schedule_executions(
        self,
        schedule_id: str,
        start_date: str,
        end_date: str
    ) -> Optional[List[Dict]]:
        """Get execution history for a schedule"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/api/v1/schedules/{schedule_id}/executions",
                    params={
                        "start_date": start_date,
                        "end_date": end_date
                    }
                )
                response.raise_for_status()
                data = response.json()
                return data.get("executions", [])
        except httpx.HTTPError as e:
            self.logger.error("Failed to get schedule executions", 
                            schedule_id=schedule_id, error=str(e))
            return None
    
    async def check_schedule_conflicts(
        self,
        section_id: str,
        start_time: str,
        duration_minutes: int
    ) -> Optional[Dict]:
        """Check for scheduling conflicts"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/api/v1/schedules/conflicts",
                    params={
                        "section_id": section_id,
                        "start_time": start_time,
                        "duration_minutes": duration_minutes
                    }
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            self.logger.error("Failed to check schedule conflicts", 
                            section_id=section_id, error=str(e))
            return None
    
    async def execute_schedule_now(self, schedule_id: str) -> Optional[Dict]:
        """Execute a schedule immediately"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/v1/schedules/{schedule_id}/execute"
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            self.logger.error("Failed to execute schedule", 
                            schedule_id=schedule_id, error=str(e))
            return None
    # --- Fail-closed control-plan reads (PR 4.4) ----------------------------
    async def _get_control_plan_document(
        self,
        path: str,
        bearer_token: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """One authenticated GET that NEVER swallows failure: it raises a typed
        error carrying the upstream status, and returns only a JSON object on a
        200. The operator bearer token is forwarded but never logged."""
        url = f"{self.base_url}{path}"
        headers = {"Authorization": f"Bearer {bearer_token}"}
        try:
            if self._http_client is not None:
                response = await self._http_client.get(
                    url, headers=headers, params=params, timeout=self.timeout
                )
            else:
                async with httpx.AsyncClient(
                    timeout=self.timeout, transport=self._transport
                ) as client:
                    response = await client.get(
                        url, headers=headers, params=params
                    )
        except httpx.HTTPError as exc:
            self.logger.error(
                "scheduler control-plan request failed to connect",
                path=path,
                error=str(exc),
            )
            raise SchedulerUnavailableError(
                "scheduler is unavailable"
            ) from exc

        status = response.status_code
        if status == 200:
            try:
                payload = response.json()
            except ValueError as exc:
                raise SchedulerContractError(
                    "scheduler response is not valid JSON"
                ) from exc
            if not isinstance(payload, dict):
                raise SchedulerContractError(
                    "scheduler control-plan response must be an object"
                )
            return payload

        detail = _extract_detail(response)
        self.logger.warning(
            "scheduler control-plan request returned an error",
            path=path,
            status=status,
        )
        if status in (401, 403):
            raise SchedulerAuthError(status, detail)
        if status == 404:
            raise SchedulerControlPlanNotFoundError(detail)
        if status in (400, 422):
            # A CLIENT error the BFF forwards opaquely (stale/cross-filter cursor,
            # invalid lifecycle_state, malformed UUID filter) — NOT an outage.
            raise SchedulerBadRequestError(status, detail)
        if status == 503:
            raise SchedulerUnavailableError(detail)
        raise SchedulerUpstreamError(
            f"scheduler returned an unexpected status {status}"
        )

    async def get_control_plan_projection(
        self, plan_id: UUID, plan_version: int, bearer_token: str
    ) -> Dict[str, Any]:
        """Fetch the exact scheduler plan detail; no projection/defaulting."""
        return await self._get_control_plan_document(
            f"/api/v1/control-plans/{plan_id}/versions/{plan_version}",
            bearer_token,
        )

    async def get_control_plan_ledger(
        self, plan_id: UUID, plan_version: int, bearer_token: str
    ) -> Dict[str, Any]:
        """Fetch the exact scheduler ledger; preserves null bounds/states."""
        return await self._get_control_plan_document(
            f"/api/v1/control-plans/{plan_id}/versions/{plan_version}/ledger",
            bearer_token,
        )

    async def get_prediction_coverage(
        self, plan_id: UUID, plan_version: int, bearer_token: str
    ) -> Dict[str, Any]:
        """Fetch the scheduler's DEDICATED bounded prediction-coverage read (PR
        4.4b-3) — not the full detail. Same fail-closed taxonomy as the other reads
        (incl. 400/422 → BadRequest), so a scheduler that has not yet deployed the
        endpoint 404s and the route fails closed rather than fabricating coverage."""
        return await self._get_control_plan_document(
            "/api/v1/control-plans/"
            f"{plan_id}/versions/{plan_version}/prediction-coverage",
            bearer_token,
        )

    async def get_lifecycle_history(
        self, plan_id: UUID, plan_version: int, bearer_token: str
    ) -> Dict[str, Any]:
        """Fetch the scheduler's DEDICATED bounded lifecycle-history read (PR
        4.4b-3) — not the full detail. Same fail-closed taxonomy as the other
        reads; a 404 (endpoint not yet deployed) fails closed, never fabricated."""
        return await self._get_control_plan_document(
            "/api/v1/control-plans/"
            f"{plan_id}/versions/{plan_version}/lifecycle-history",
            bearer_token,
        )

    async def get_intent_timeline(
        self, plan_id: UUID, plan_version: int, bearer_token: str
    ) -> Dict[str, Any]:
        """Fetch the scheduler's bounded per-intent timeline (PR 6.5a). Same fail-closed
        taxonomy; a 404 (endpoint not yet deployed) fails closed, never fabricated."""
        return await self._get_control_plan_document(
            f"/api/v1/control-plans/{plan_id}/versions/{plan_version}/intent-timeline",
            bearer_token,
        )

    async def get_readback_observations(
        self, plan_id: UUID, plan_version: int, bearer_token: str
    ) -> Dict[str, Any]:
        """Fetch the scheduler's bounded readback observations (PR 6.5a). Fail-closed taxonomy."""
        return await self._get_control_plan_document(
            "/api/v1/control-plans/"
            f"{plan_id}/versions/{plan_version}/readback-observations",
            bearer_token,
        )

    async def get_execution_state(
        self, plan_id: UUID, plan_version: int, bearer_token: str
    ) -> Dict[str, Any]:
        """Fetch the scheduler's bounded plan-level execution/hold state (PR 6.5a). Fail-closed."""
        return await self._get_control_plan_document(
            f"/api/v1/control-plans/{plan_id}/versions/{plan_version}/execution-state",
            bearer_token,
        )

    async def list_control_plans(
        self,
        *,
        filters: Dict[str, Any],
        cursor: Optional[str],
        limit: int,
        bearer_token: str,
    ) -> Dict[str, Any]:
        """Fetch one bounded page of the scheduler control-plan list.

        Forwards the operator bearer + the exact filters/cursor/limit as query
        params and preserves the SAME fail-closed taxonomy as the detail reads
        (404→NotFound, 401/403→Auth, 503/transport→Unavailable, malformed→
        Contract, other→Upstream). It NEVER fabricates an empty page on failure:
        every non-200 raises a typed error the route re-raises as a status."""
        params: Dict[str, Any] = {
            key: value for key, value in filters.items() if value is not None
        }
        params["limit"] = limit
        if cursor is not None:
            params["cursor"] = cursor
        return await self._get_control_plan_document(
            "/api/v1/control-plans", bearer_token, params=params
        )


def _extract_detail(response: httpx.Response) -> str:
    """Best-effort extraction of the scheduler's {"detail": ...} message,
    without leaking transport internals or the target host."""
    try:
        body = response.json()
    except ValueError:
        return f"scheduler error {response.status_code}"
    if isinstance(body, dict) and "detail" in body:
        detail = body["detail"]
        return detail if isinstance(detail, str) else str(detail)
    return f"scheduler error {response.status_code}"
