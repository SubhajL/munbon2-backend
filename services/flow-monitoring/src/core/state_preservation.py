#!/usr/bin/env python3
"""
State Preservation System for Mode Transitions
Captures, stores, and restores complete system state during operational mode changes
"""

import json
import pickle
import gzip
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
import uuid
import logging
import asyncio
from pathlib import Path

import redis
import asyncpg

logger = logging.getLogger(__name__)


class TransitionType(Enum):
    """Types of mode transitions"""
    AUTO_TO_MANUAL = "auto_to_manual"
    MANUAL_TO_AUTO = "manual_to_auto"
    NORMAL_TO_EMERGENCY = "normal_to_emergency"
    EMERGENCY_TO_NORMAL = "emergency_to_normal"
    MAINTENANCE_START = "maintenance_start"
    MAINTENANCE_END = "maintenance_end"
    PARTIAL_FAILURE = "partial_failure"
    SYSTEM_RECOVERY = "system_recovery"


class StateComponent(Enum):
    """Components of system state to preserve"""
    GATE_POSITIONS = "gate_positions"
    WATER_LEVELS = "water_levels"
    FLOW_TARGETS = "flow_targets"
    DELIVERY_SCHEDULES = "delivery_schedules"
    CONTROL_MODES = "control_modes"
    EQUIPMENT_STATUS = "equipment_status"
    ACTIVE_ALARMS = "active_alarms"
    OPTIMIZATION_PARAMS = "optimization_params"


@dataclass
class GateStateSnapshot:
    """Snapshot of gate state at a point in time"""
    gate_id: str
    timestamp: datetime
    control_mode: str
    position_m: float
    position_percent: float
    flow_rate_m3s: float
    upstream_level_m: float
    downstream_level_m: float
    last_command: Optional[str] = None
    last_command_time: Optional[datetime] = None
    equipment_status: str = "operational"
    error_flags: List[str] = field(default_factory=list)


@dataclass
class FlowTargetSnapshot:
    """Snapshot of flow targets"""
    zone_id: str
    target_flow_m3s: float
    allocated_flow_m3s: float
    priority: int
    delivery_window_start: datetime
    delivery_window_end: datetime
    source_gates: List[str] = field(default_factory=list)
    constraints: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DeliveryScheduleSnapshot:
    """Snapshot of active deliveries"""
    delivery_id: str
    status: str  # active, queued, completed
    farmer_id: str
    zone_id: str
    requested_volume_m3: float
    delivered_volume_m3: float
    start_time: datetime
    estimated_end_time: datetime
    actual_end_time: Optional[datetime] = None
    flow_path: List[str] = field(default_factory=list)


@dataclass
class SystemStateSnapshot:
    """Complete system state at a point in time"""
    snapshot_id: str
    transition_id: str
    timestamp: datetime
    transition_type: TransitionType
    trigger_reason: str
    
    # State components
    gate_states: List[GateStateSnapshot]
    water_levels: Dict[str, float]  # node_id -> level
    flow_targets: List[FlowTargetSnapshot]
    delivery_schedules: List[DeliveryScheduleSnapshot]
    control_modes: Dict[str, str]  # gate_id -> mode
    equipment_status: Dict[str, str]  # gate_id -> status
    active_alarms: List[Dict[str, Any]]
    
    # Optimization state
    optimization_params: Dict[str, Any] = field(default_factory=dict)
    
    # Metadata
    preserved_by: str = "system"
    preservation_duration_ms: int = 0
    compressed_size_bytes: int = 0
    component_checksums: Dict[str, str] = field(default_factory=dict)


@dataclass
class StateRestoreResult:
    """Result of state restoration attempt"""
    success: bool
    transition_id: str
    restored_components: List[StateComponent]
    failed_components: List[StateComponent]
    warnings: List[str]
    errors: List[str]
    duration_ms: int


class StatePreservationSystem:
    """
    Manages state preservation and restoration for mode transitions
    """
    
    def __init__(self, redis_client: redis.Redis, db_pool: asyncpg.Pool, 
                 storage_path: str = "/tmp/munbon_states"):
        """
        Initialize state preservation system
        
        Args:
            redis_client: Redis client for fast state access
            db_pool: PostgreSQL connection pool for persistent storage
            storage_path: Local path for state file backups
        """
        self.redis = redis_client
        self.db_pool = db_pool
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # Configuration
        self.redis_ttl_seconds = 86400  # 24 hours
        self.max_state_size_mb = 100
        self.compression_threshold_kb = 100
        
        # State tracking
        self._active_transitions: Dict[str, datetime] = {}
        self._preservation_lock = asyncio.Lock()
        
        logger.info(f"State preservation system initialized with storage at {storage_path}")
    
    async def initialize_database(self):
        """Create necessary database tables"""
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS state_snapshots (
                    snapshot_id UUID PRIMARY KEY,
                    transition_id UUID NOT NULL,
                    timestamp TIMESTAMPTZ NOT NULL,
                    transition_type VARCHAR(50) NOT NULL,
                    trigger_reason TEXT,
                    preserved_by VARCHAR(100),
                    preservation_duration_ms INTEGER,
                    compressed_size_bytes INTEGER,
                    state_data JSONB NOT NULL,
                    component_checksums JSONB,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
                
                CREATE INDEX IF NOT EXISTS idx_state_snapshots_transition 
                ON state_snapshots(transition_id);
                
                CREATE INDEX IF NOT EXISTS idx_state_snapshots_timestamp 
                ON state_snapshots(timestamp);
                
                CREATE TABLE IF NOT EXISTS state_restore_log (
                    restore_id UUID PRIMARY KEY,
                    transition_id UUID NOT NULL,
                    snapshot_id UUID NOT NULL,
                    timestamp TIMESTAMPTZ DEFAULT NOW(),
                    success BOOLEAN NOT NULL,
                    restored_components JSONB,
                    failed_components JSONB,
                    warnings JSONB,
                    errors JSONB,
                    duration_ms INTEGER
                );
            """)
            logger.info("State preservation database tables initialized")
    
    async def preserve_state(self, transition_type: TransitionType, trigger_reason: str,
                           current_state: Dict[str, Any], 
                           preserved_by: str = "system") -> SystemStateSnapshot:
        """
        Preserve complete system state for a mode transition
        
        Args:
            transition_type: Type of transition occurring
            trigger_reason: Why the transition was triggered
            current_state: Complete current system state
            preserved_by: User or system component initiating preservation
            
        Returns:
            SystemStateSnapshot with all preserved data
        """
        start_time = datetime.now()
        transition_id = str(uuid.uuid4())
        snapshot_id = str(uuid.uuid4())
        
        async with self._preservation_lock:
            try:
                # Track active transition
                self._active_transitions[transition_id] = start_time
                
                # Extract state components
                gate_states = await self._extract_gate_states(current_state)
                water_levels = current_state.get("water_levels", {})
                flow_targets = await self._extract_flow_targets(current_state)
                delivery_schedules = await self._extract_delivery_schedules(current_state)
                control_modes = current_state.get("control_modes", {})
                equipment_status = current_state.get("equipment_status", {})
                active_alarms = current_state.get("active_alarms", [])
                optimization_params = current_state.get("optimization_params", {})
                
                # Create snapshot
                snapshot = SystemStateSnapshot(
                    snapshot_id=snapshot_id,
                    transition_id=transition_id,
                    timestamp=start_time,
                    transition_type=transition_type,
                    trigger_reason=trigger_reason,
                    gate_states=gate_states,
                    water_levels=water_levels,
                    flow_targets=flow_targets,
                    delivery_schedules=delivery_schedules,
                    control_modes=control_modes,
                    equipment_status=equipment_status,
                    active_alarms=active_alarms,
                    optimization_params=optimization_params,
                    preserved_by=preserved_by
                )
                
                # Calculate checksums for integrity
                snapshot.component_checksums = self._calculate_checksums(snapshot)
                
                # Store in multiple locations for redundancy
                await self._store_snapshot(snapshot)
                
                # Calculate preservation time
                snapshot.preservation_duration_ms = int(
                    (datetime.now() - start_time).total_seconds() * 1000
                )
                
                logger.info(f"State preserved for transition {transition_id} in "
                          f"{snapshot.preservation_duration_ms}ms")
                
                return snapshot
                
            except Exception as e:
                logger.error(f"Failed to preserve state for transition {transition_id}: {e}")
                raise
            finally:
                # Clean up tracking
                self._active_transitions.pop(transition_id, None)
    
    async def _extract_gate_states(self, current_state: Dict) -> List[GateStateSnapshot]:
        """Extract gate state snapshots from current state"""
        gate_states = []
        
        gates_data = current_state.get("gates", {})
        for gate_id, gate_info in gates_data.items():
            snapshot = GateStateSnapshot(
                gate_id=gate_id,
                timestamp=datetime.now(),
                control_mode=gate_info.get("control_mode", "unknown"),
                position_m=gate_info.get("position_m", 0.0),
                position_percent=gate_info.get("position_percent", 0.0),
                flow_rate_m3s=gate_info.get("flow_rate", 0.0),
                upstream_level_m=gate_info.get("upstream_level", 0.0),
                downstream_level_m=gate_info.get("downstream_level", 0.0),
                last_command=gate_info.get("last_command"),
                last_command_time=gate_info.get("last_command_time"),
                equipment_status=gate_info.get("equipment_status", "unknown"),
                error_flags=gate_info.get("error_flags", [])
            )
            gate_states.append(snapshot)
        
        return gate_states
    
    async def _extract_flow_targets(self, current_state: Dict) -> List[FlowTargetSnapshot]:
        """Extract flow target snapshots from current state"""
        flow_targets = []
        
        targets_data = current_state.get("flow_targets", {})
        for zone_id, target_info in targets_data.items():
            snapshot = FlowTargetSnapshot(
                zone_id=zone_id,
                target_flow_m3s=target_info.get("target", 0.0),
                allocated_flow_m3s=target_info.get("allocated", 0.0),
                priority=target_info.get("priority", 0),
                delivery_window_start=target_info.get("window_start", datetime.now()),
                delivery_window_end=target_info.get("window_end", datetime.now() + timedelta(hours=1)),
                source_gates=target_info.get("source_gates", []),
                constraints=target_info.get("constraints", {})
            )
            flow_targets.append(snapshot)
        
        return flow_targets
    
    async def _extract_delivery_schedules(self, current_state: Dict) -> List[DeliveryScheduleSnapshot]:
        """Extract delivery schedule snapshots from current state"""
        schedules = []
        
        deliveries_data = current_state.get("active_deliveries", [])
        for delivery in deliveries_data:
            snapshot = DeliveryScheduleSnapshot(
                delivery_id=delivery.get("id", str(uuid.uuid4())),
                status=delivery.get("status", "unknown"),
                farmer_id=delivery.get("farmer_id", ""),
                zone_id=delivery.get("zone_id", ""),
                requested_volume_m3=delivery.get("requested_volume", 0.0),
                delivered_volume_m3=delivery.get("delivered_volume", 0.0),
                start_time=delivery.get("start_time", datetime.now()),
                estimated_end_time=delivery.get("estimated_end_time", datetime.now()),
                actual_end_time=delivery.get("actual_end_time"),
                flow_path=delivery.get("flow_path", [])
            )
            schedules.append(snapshot)
        
        return schedules
    
    def _calculate_checksums(self, snapshot: SystemStateSnapshot) -> Dict[str, str]:
        """Calculate checksums for each state component"""
        import hashlib
        
        checksums = {}
        
        # Convert components to bytes and calculate SHA256
        components = {
            "gate_states": json.dumps([asdict(g) for g in snapshot.gate_states], default=str).encode(),
            "water_levels": json.dumps(snapshot.water_levels).encode(),
            "flow_targets": json.dumps([asdict(f) for f in snapshot.flow_targets], default=str).encode(),
            "delivery_schedules": json.dumps([asdict(d) for d in snapshot.delivery_schedules], default=str).encode(),
            "control_modes": json.dumps(snapshot.control_modes).encode(),
            "equipment_status": json.dumps(snapshot.equipment_status).encode()
        }
        
        for component_name, component_data in components.items():
            checksums[component_name] = hashlib.sha256(component_data).hexdigest()
        
        return checksums
    
    async def _store_snapshot(self, snapshot: SystemStateSnapshot):
        """Store snapshot in multiple locations"""
        # Convert to dictionary
        snapshot_dict = asdict(snapshot)
        
        # Serialize for storage
        snapshot_json = json.dumps(snapshot_dict, default=str)
        snapshot_bytes = snapshot_json.encode()
        
        # Compress if large
        if len(snapshot_bytes) > self.compression_threshold_kb * 1024:
            snapshot_bytes = gzip.compress(snapshot_bytes)
            snapshot.compressed_size_bytes = len(snapshot_bytes)
        
        # Store in Redis for fast access
        redis_key = f"state:snapshot:{snapshot.snapshot_id}"
        await self.redis.setex(
            redis_key,
            self.redis_ttl_seconds,
            snapshot_bytes
        )
        
        # Store transition mapping
        await self.redis.setex(
            f"state:transition:{snapshot.transition_id}",
            self.redis_ttl_seconds,
            snapshot.snapshot_id
        )
        
        # Store in PostgreSQL for persistence
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO state_snapshots (
                    snapshot_id, transition_id, timestamp, transition_type,
                    trigger_reason, preserved_by, preservation_duration_ms,
                    compressed_size_bytes, state_data, component_checksums
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            """, 
                uuid.UUID(snapshot.snapshot_id),
                uuid.UUID(snapshot.transition_id),
                snapshot.timestamp,
                snapshot.transition_type.value,
                snapshot.trigger_reason,
                snapshot.preserved_by,
                snapshot.preservation_duration_ms,
                snapshot.compressed_size_bytes,
                json.dumps(snapshot_dict, default=str),
                json.dumps(snapshot.component_checksums)
            )
        
        # Store backup file
        file_path = self.storage_path / f"{snapshot.snapshot_id}.pkl.gz"
        with open(file_path, 'wb') as f:
            pickle.dump(snapshot, f)
        
        logger.debug(f"Snapshot {snapshot.snapshot_id} stored in Redis, PostgreSQL, and file")
    
    async def restore_state(self, transition_id: str, 
                          components: Optional[List[StateComponent]] = None) -> StateRestoreResult:
        """
        Restore system state from a preserved snapshot
        
        Args:
            transition_id: ID of the transition to restore from
            components: Optional list of specific components to restore
            
        Returns:
            StateRestoreResult with restoration details
        """
        start_time = datetime.now()
        warnings = []
        errors = []
        restored_components = []
        failed_components = []
        
        try:
            # Retrieve snapshot
            snapshot = await self._retrieve_snapshot(transition_id)
            if not snapshot:
                errors.append(f"No snapshot found for transition {transition_id}")
                return StateRestoreResult(
                    success=False,
                    transition_id=transition_id,
                    restored_components=[],
                    failed_components=components or list(StateComponent),
                    warnings=warnings,
                    errors=errors,
                    duration_ms=0
                )
            
            # Verify checksums
            if not await self._verify_checksums(snapshot):
                warnings.append("Checksum verification failed - data may be corrupted")
            
            # Determine components to restore
            if components is None:
                components = list(StateComponent)
            
            # Restore each component
            for component in components:
                try:
                    await self._restore_component(snapshot, component)
                    restored_components.append(component)
                except Exception as e:
                    failed_components.append(component)
                    errors.append(f"Failed to restore {component.value}: {str(e)}")
            
            # Log restoration
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            
            result = StateRestoreResult(
                success=len(failed_components) == 0,
                transition_id=transition_id,
                restored_components=restored_components,
                failed_components=failed_components,
                warnings=warnings,
                errors=errors,
                duration_ms=duration_ms
            )
            
            # Record in database
            await self._log_restoration(snapshot.snapshot_id, result)
            
            logger.info(f"State restoration for transition {transition_id} completed in {duration_ms}ms. "
                       f"Success: {result.success}")
            
            return result
            
        except Exception as e:
            logger.error(f"State restoration failed for transition {transition_id}: {e}")
            errors.append(str(e))
            return StateRestoreResult(
                success=False,
                transition_id=transition_id,
                restored_components=[],
                failed_components=components or list(StateComponent),
                warnings=warnings,
                errors=errors,
                duration_ms=int((datetime.now() - start_time).total_seconds() * 1000)
            )
    
    async def _retrieve_snapshot(self, transition_id: str) -> Optional[SystemStateSnapshot]:
        """Retrieve snapshot from storage"""
        # Try Redis first
        snapshot_id = await self.redis.get(f"state:transition:{transition_id}")
        
        if snapshot_id:
            snapshot_data = await self.redis.get(f"state:snapshot:{snapshot_id}")
            if snapshot_data:
                # Decompress if needed
                try:
                    snapshot_data = gzip.decompress(snapshot_data)
                except:
                    pass  # Not compressed
                
                snapshot_dict = json.loads(snapshot_data)
                return self._dict_to_snapshot(snapshot_dict)
        
        # Try PostgreSQL
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT state_data FROM state_snapshots 
                WHERE transition_id = $1 
                ORDER BY timestamp DESC 
                LIMIT 1
            """, uuid.UUID(transition_id))
            
            if row:
                return self._dict_to_snapshot(row['state_data'])
        
        # Try file backup
        for file_path in self.storage_path.glob("*.pkl.gz"):
            try:
                with open(file_path, 'rb') as f:
                    snapshot = pickle.load(f)
                    if snapshot.transition_id == transition_id:
                        return snapshot
            except:
                continue
        
        return None
    
    def _dict_to_snapshot(self, data: Dict) -> SystemStateSnapshot:
        """Convert dictionary back to SystemStateSnapshot"""
        # Convert nested objects
        data['transition_type'] = TransitionType(data['transition_type'])
        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        
        # Convert gate states
        data['gate_states'] = [
            GateStateSnapshot(**gs) for gs in data['gate_states']
        ]
        
        # Convert flow targets
        data['flow_targets'] = [
            FlowTargetSnapshot(**ft) for ft in data['flow_targets']
        ]
        
        # Convert delivery schedules
        data['delivery_schedules'] = [
            DeliveryScheduleSnapshot(**ds) for ds in data['delivery_schedules']
        ]
        
        return SystemStateSnapshot(**data)
    
    async def _verify_checksums(self, snapshot: SystemStateSnapshot) -> bool:
        """Verify state integrity using checksums"""
        current_checksums = self._calculate_checksums(snapshot)
        
        for component, expected_checksum in snapshot.component_checksums.items():
            if current_checksums.get(component) != expected_checksum:
                logger.warning(f"Checksum mismatch for component {component}")
                return False
        
        return True
    
    async def _restore_component(self, snapshot: SystemStateSnapshot, component: StateComponent):
        """Restore a specific state component"""
        # This would integrate with actual system components
        # For now, logging the restoration
        logger.info(f"Restoring {component.value} from snapshot {snapshot.snapshot_id}")
        
        # Component-specific restoration logic would go here
        # For example:
        # - GATE_POSITIONS: Send position commands to gates
        # - WATER_LEVELS: Adjust control setpoints
        # - FLOW_TARGETS: Update optimization targets
        # - DELIVERY_SCHEDULES: Reinstate active deliveries
        # etc.
    
    async def _log_restoration(self, snapshot_id: str, result: StateRestoreResult):
        """Log restoration attempt to database"""
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO state_restore_log (
                    restore_id, transition_id, snapshot_id, success,
                    restored_components, failed_components, warnings, errors, duration_ms
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """,
                uuid.uuid4(),
                uuid.UUID(result.transition_id),
                uuid.UUID(snapshot_id),
                result.success,
                json.dumps([c.value for c in result.restored_components]),
                json.dumps([c.value for c in result.failed_components]),
                json.dumps(result.warnings),
                json.dumps(result.errors),
                result.duration_ms
            )
    
    async def cleanup_old_snapshots(self, retention_days: int = 7):
        """Clean up old snapshots beyond retention period"""
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        
        async with self.db_pool.acquire() as conn:
            deleted = await conn.execute("""
                DELETE FROM state_snapshots 
                WHERE timestamp < $1
            """, cutoff_date)
            
            logger.info(f"Cleaned up {deleted} old state snapshots")
        
        # Clean up old files
        for file_path in self.storage_path.glob("*.pkl.gz"):
            if file_path.stat().st_mtime < cutoff_date.timestamp():
                file_path.unlink()
    
    async def get_transition_history(self, 
                                   start_time: Optional[datetime] = None,
                                   end_time: Optional[datetime] = None,
                                   transition_type: Optional[TransitionType] = None) -> List[Dict]:
        """Get history of state transitions"""
        query = """
            SELECT 
                transition_id, timestamp, transition_type, trigger_reason,
                preserved_by, preservation_duration_ms, compressed_size_bytes
            FROM state_snapshots
            WHERE 1=1
        """
        params = []
        
        if start_time:
            params.append(start_time)
            query += f" AND timestamp >= ${len(params)}"
        
        if end_time:
            params.append(end_time)
            query += f" AND timestamp <= ${len(params)}"
        
        if transition_type:
            params.append(transition_type.value)
            query += f" AND transition_type = ${len(params)}"
        
        query += " ORDER BY timestamp DESC"
        
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            
        return [dict(row) for row in rows]