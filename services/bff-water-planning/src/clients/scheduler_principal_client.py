from __future__ import annotations

from typing import Optional

import httpx
from config import settings
from pydantic import ValidationError
from schemas.planning_depth import EffectivePrincipalProjection


class SchedulerPrincipalError(RuntimeError):
    pass


class SchedulerPrincipalAuthError(SchedulerPrincipalError):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class SchedulerPrincipalUnavailableError(SchedulerPrincipalError):
    pass


class SchedulerPrincipalContractError(SchedulerPrincipalError):
    pass


class SchedulerPrincipalClient:
    def __init__(
        self,
        base_url: Optional[str] = None,
        *,
        transport: Optional[httpx.AsyncBaseTransport] = None,
        http_client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self.base_url = (base_url or settings.scheduler_url).rstrip("/")
        self._transport = transport
        self._http_client = http_client
        self._timeout = httpx.Timeout(10.0, connect=3.0)

    async def load_effective_principal(
        self, bearer_token: str
    ) -> EffectivePrincipalProjection:
        url = f"{self.base_url}/api/v1/auth/principal"
        headers = {"Authorization": f"Bearer {bearer_token}"}
        try:
            if self._http_client is not None:
                response = await self._http_client.get(
                    url,
                    headers=headers,
                    timeout=self._timeout,
                )
            else:
                async with httpx.AsyncClient(
                    timeout=self._timeout,
                    transport=self._transport,
                ) as client:
                    response = await client.get(url, headers=headers)
        except httpx.HTTPError as exc:
            raise SchedulerPrincipalUnavailableError(
                "scheduler principal is unavailable"
            ) from exc

        if response.status_code == 200:
            try:
                return EffectivePrincipalProjection.model_validate(response.json())
            except (ValueError, ValidationError) as exc:
                raise SchedulerPrincipalContractError(
                    "scheduler principal response is invalid"
                ) from exc
        if response.status_code in (401, 403):
            raise SchedulerPrincipalAuthError(
                response.status_code,
                _safe_detail(response),
            )
        if response.status_code == 503:
            raise SchedulerPrincipalUnavailableError(
                "scheduler principal is unavailable"
            )
        raise SchedulerPrincipalContractError(
            "scheduler principal returned an unexpected status"
        )


def _safe_detail(response: httpx.Response) -> str:
    try:
        detail = response.json().get("detail")
    except (ValueError, AttributeError):
        detail = None
    if isinstance(detail, str) and detail:
        return detail
    return "authentication failed"
