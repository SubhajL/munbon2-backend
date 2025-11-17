from __future__ import annotations

from typing import List, Optional, Tuple
from uuid import UUID
from datetime import datetime

from schemas import EfficiencyMetrics, FlowAnomaly
from db import DatabaseManager


class AnalyticsService:
    """Minimal analytics service to satisfy API imports and basic behavior.

    Methods return empty, well-typed results to keep the API responsive
    until real data sources are integrated.
    """

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or DatabaseManager()

    async def calculate_efficiency_metrics(
        self,
        segment_ids: List[UUID],
        start_time: datetime,
        end_time: datetime,
    ) -> List[EfficiencyMetrics]:
        # Placeholder: return empty list
        return []

    async def analyze_losses(
        self,
        segment_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> dict:
        # Placeholder: return basic shape
        return {
            "segment_id": str(segment_id),
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "estimated_losses_m3": 0.0,
            "components": {},
        }

    async def get_anomalies(
        self,
        location_ids: Optional[List[UUID]] = None,
        severity: Optional[str] = None,
        resolved: Optional[bool] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        offset: int = 0,
        limit: int = 50,
    ) -> Tuple[List[FlowAnomaly], int]:
        # Placeholder: return empty set and total 0
        return [], 0

    async def resolve_anomaly(self, anomaly_id: UUID, resolution_notes: str = "") -> None:
        # Placeholder: do nothing
        return None
