from __future__ import annotations

from typing import List, Optional
from uuid import UUID
from datetime import datetime

from schemas import SensorConfig, SensorCalibration, CalibrationHistory, SensorHealthMetrics
from db import DatabaseManager


class SensorService:
    """Minimal sensor service to satisfy API imports and basic behavior.

    Methods return empty, well-typed results to keep the API responsive
    until real data sources are integrated.
    """

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or DatabaseManager()

    async def calibrate_sensor(self, calibration: SensorCalibration) -> None:
        # In a full implementation, persist calibration to Timescale/Postgres
        return None

    async def get_sensor_config(self, sensor_id: UUID) -> Optional[SensorConfig]:
        # Placeholder: return None to indicate not found
        return None

    async def get_sensor_health(self, location_id: Optional[UUID]) -> List[SensorHealthMetrics]:
        # Placeholder: return empty list
        return []

    async def get_calibration_history(self, sensor_id: UUID, limit: int = 10) -> List[CalibrationHistory]:
        # Placeholder: return empty list
        return []
