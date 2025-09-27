#!/usr/bin/env python3
"""
Job Order System for Manual Gate Operations
Manages work orders for field teams to operate manual gates
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import json
import uuid
import logging

from .gate_properties_enhanced import GatePropertiesEnhanced

logger = logging.getLogger(__name__)


class JobOrderStatus(Enum):
    """Status of job order"""
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"
    

class JobOrderPriority(Enum):
    """Priority levels for job orders"""
    EMERGENCY = "emergency"  # < 2 hours
    HIGH = "high"           # < 6 hours
    NORMAL = "normal"       # < 24 hours
    LOW = "low"             # < 48 hours
    

class JobOrderType(Enum):
    """Types of gate operations"""
    OPEN_GATE = "open_gate"
    CLOSE_GATE = "close_gate"
    ADJUST_GATE = "adjust_gate"
    INSPECT_GATE = "inspect_gate"
    EMERGENCY_CLOSE = "emergency_close"
    

@dataclass
class GateOperationInstruction:
    """Detailed instructions for gate operation"""
    current_opening_m: float
    target_opening_m: float
    operation_type: JobOrderType
    estimated_turns: Optional[int] = None  # For wheel-operated gates
    estimated_duration_minutes: int = 15
    safety_notes: Optional[str] = None
    special_tools_required: List[str] = field(default_factory=list)
    
    @property
    def opening_change_m(self) -> float:
        """Calculate change in opening"""
        return self.target_opening_m - self.current_opening_m
        
    @property
    def is_closing(self) -> bool:
        """Check if operation is closing the gate"""
        return self.opening_change_m < 0
        

@dataclass
class JobOrder:
    """Job order for manual gate operation"""
    order_id: str
    gate_id: str
    gate_location: Dict[str, float]  # lat, lon
    zone: int
    
    # Operation details
    instruction: GateOperationInstruction
    priority: JobOrderPriority
    
    # Scheduling
    created_at: datetime
    due_by: datetime
    scheduled_for: Optional[datetime] = None
    
    # Assignment
    assigned_to: Optional[str] = None  # Team or operator ID
    assigned_at: Optional[datetime] = None
    
    # Execution
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Status tracking
    status: JobOrderStatus = JobOrderStatus.PENDING
    
    # Verification
    actual_opening_m: Optional[float] = None
    verification_photo_url: Optional[str] = None
    completion_notes: Optional[str] = None
    
    # System tracking
    created_by: str = "flow_monitoring_system"
    reason: Optional[str] = None
    related_orders: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "order_id": self.order_id,
            "gate_id": self.gate_id,
            "gate_location": self.gate_location,
            "zone": self.zone,
            "instruction": {
                "current_opening_m": self.instruction.current_opening_m,
                "target_opening_m": self.instruction.target_opening_m,
                "operation_type": self.instruction.operation_type.value,
                "estimated_duration_minutes": self.instruction.estimated_duration_minutes,
                "safety_notes": self.instruction.safety_notes,
                "special_tools_required": self.instruction.special_tools_required
            },
            "priority": self.priority.value,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "due_by": self.due_by.isoformat(),
            "scheduled_for": self.scheduled_for.isoformat() if self.scheduled_for else None,
            "assigned_to": self.assigned_to,
            "assigned_at": self.assigned_at.isoformat() if self.assigned_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "actual_opening_m": self.actual_opening_m,
            "completion_notes": self.completion_notes,
            "reason": self.reason
        }


class JobOrderManager:
    """Manages job orders for manual gate operations"""
    
    def __init__(self):
        self.orders: Dict[str, JobOrder] = {}
        self.gate_status: Dict[str, float] = {}  # Current gate openings
        self.team_assignments: Dict[str, List[str]] = {}  # Team -> Order IDs
        
        # Priority time windows
        self.priority_windows = {
            JobOrderPriority.EMERGENCY: timedelta(hours=2),
            JobOrderPriority.HIGH: timedelta(hours=6),
            JobOrderPriority.NORMAL: timedelta(hours=24),
            JobOrderPriority.LOW: timedelta(hours=48)
        }
        
    def create_job_order(
        self,
        gate: GatePropertiesEnhanced,
        target_opening_m: float,
        priority: JobOrderPriority = JobOrderPriority.NORMAL,
        reason: Optional[str] = None,
        scheduled_time: Optional[datetime] = None
    ) -> JobOrder:
        """Create a new job order for manual gate operation"""
        
        # Get current gate opening
        current_opening = self.gate_status.get(gate.gate_id, 0.0)
        
        # Determine operation type
        if target_opening_m == 0:
            operation_type = JobOrderType.CLOSE_GATE
        elif current_opening == 0:
            operation_type = JobOrderType.OPEN_GATE
        else:
            operation_type = JobOrderType.ADJUST_GATE
            
        # Create instruction
        instruction = GateOperationInstruction(
            current_opening_m=current_opening,
            target_opening_m=target_opening_m,
            operation_type=operation_type,
            estimated_duration_minutes=self._estimate_duration(gate, current_opening, target_opening_m)
        )
        
        # Add special requirements for large gates
        if gate.shape == gate.shape.RECTANGULAR and gate.width_m > 3.0:
            instruction.special_tools_required.append("large_wheel_key")
            instruction.safety_notes = "Two-person operation required for safety"
            
        # Create order
        now = datetime.now()
        order = JobOrder(
            order_id=f"JO-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}",
            gate_id=gate.gate_id,
            gate_location={"lat": gate.latitude, "lon": gate.longitude} if gate.latitude else {},
            zone=gate.zone or 0,
            instruction=instruction,
            priority=priority,
            created_at=now,
            due_by=now + self.priority_windows[priority],
            scheduled_for=scheduled_time,
            reason=reason
        )
        
        self.orders[order.order_id] = order
        logger.info(f"Created job order {order.order_id} for gate {gate.gate_id}")
        
        return order
        
    def create_batch_orders(
        self,
        gate_operations: List[Tuple[GatePropertiesEnhanced, float]],
        priority: JobOrderPriority = JobOrderPriority.NORMAL,
        reason: str = "Scheduled irrigation adjustment"
    ) -> List[JobOrder]:
        """Create multiple job orders for coordinated operation"""
        
        orders = []
        
        # Group by zone for efficient routing
        zone_groups = {}
        for gate, target_opening in gate_operations:
            zone = gate.zone or 0
            if zone not in zone_groups:
                zone_groups[zone] = []
            zone_groups[zone].append((gate, target_opening))
            
        # Create orders with zone-based scheduling
        base_time = datetime.now()
        time_offset = timedelta(hours=0)
        
        for zone, operations in sorted(zone_groups.items()):
            # Schedule operations in same zone together
            scheduled_time = base_time + time_offset
            
            for gate, target_opening in operations:
                order = self.create_job_order(
                    gate=gate,
                    target_opening_m=target_opening,
                    priority=priority,
                    reason=f"{reason} - Zone {zone}",
                    scheduled_time=scheduled_time
                )
                orders.append(order)
                
                # Add time for operation
                scheduled_time += timedelta(minutes=order.instruction.estimated_duration_minutes)
                
            # Add travel time between zones
            time_offset += timedelta(hours=1)
            
        # Link related orders
        order_ids = [o.order_id for o in orders]
        for order in orders:
            order.related_orders = [oid for oid in order_ids if oid != order.order_id]
            
        logger.info(f"Created {len(orders)} batch job orders")
        return orders
        
    def assign_order(self, order_id: str, team_id: str) -> bool:
        """Assign job order to a team"""
        
        if order_id not in self.orders:
            logger.error(f"Order {order_id} not found")
            return False
            
        order = self.orders[order_id]
        
        if order.status != JobOrderStatus.PENDING:
            logger.warning(f"Order {order_id} is not pending (status: {order.status})")
            return False
            
        order.assigned_to = team_id
        order.assigned_at = datetime.now()
        order.status = JobOrderStatus.ASSIGNED
        
        # Track assignment
        if team_id not in self.team_assignments:
            self.team_assignments[team_id] = []
        self.team_assignments[team_id].append(order_id)
        
        logger.info(f"Assigned order {order_id} to team {team_id}")
        return True
        
    def start_order(self, order_id: str) -> bool:
        """Mark order as started"""
        
        if order_id not in self.orders:
            return False
            
        order = self.orders[order_id]
        
        if order.status != JobOrderStatus.ASSIGNED:
            logger.warning(f"Order {order_id} is not assigned (status: {order.status})")
            return False
            
        order.started_at = datetime.now()
        order.status = JobOrderStatus.IN_PROGRESS
        
        logger.info(f"Started order {order_id}")
        return True
        
    def complete_order(
        self,
        order_id: str,
        actual_opening_m: float,
        notes: Optional[str] = None,
        photo_url: Optional[str] = None
    ) -> bool:
        """Mark order as completed with verification"""
        
        if order_id not in self.orders:
            return False
            
        order = self.orders[order_id]
        
        if order.status != JobOrderStatus.IN_PROGRESS:
            logger.warning(f"Order {order_id} is not in progress (status: {order.status})")
            return False
            
        order.completed_at = datetime.now()
        order.status = JobOrderStatus.COMPLETED
        order.actual_opening_m = actual_opening_m
        order.completion_notes = notes
        order.verification_photo_url = photo_url
        
        # Update gate status
        self.gate_status[order.gate_id] = actual_opening_m
        
        # Check if target was achieved
        tolerance = 0.05  # 5cm tolerance
        if abs(actual_opening_m - order.instruction.target_opening_m) > tolerance:
            logger.warning(
                f"Order {order_id}: Target {order.instruction.target_opening_m:.2f}m, "
                f"Actual {actual_opening_m:.2f}m"
            )
            
        logger.info(f"Completed order {order_id}")
        return True
        
    def get_pending_orders(self, zone: Optional[int] = None) -> List[JobOrder]:
        """Get all pending orders, optionally filtered by zone"""
        
        pending = [
            order for order in self.orders.values()
            if order.status == JobOrderStatus.PENDING
        ]
        
        if zone is not None:
            pending = [o for o in pending if o.zone == zone]
            
        # Sort by priority and due time
        priority_rank = {
            JobOrderPriority.EMERGENCY: 0,
            JobOrderPriority.HIGH: 1,
            JobOrderPriority.NORMAL: 2,
            JobOrderPriority.LOW: 3
        }
        
        pending.sort(key=lambda o: (priority_rank[o.priority], o.due_by))
        
        return pending
        
    def get_team_orders(self, team_id: str) -> List[JobOrder]:
        """Get all orders assigned to a team"""
        
        order_ids = self.team_assignments.get(team_id, [])
        return [self.orders[oid] for oid in order_ids if oid in self.orders]
        
    def get_overdue_orders(self) -> List[JobOrder]:
        """Get orders that are past their due time"""
        
        now = datetime.now()
        overdue = [
            order for order in self.orders.values()
            if order.status in [JobOrderStatus.PENDING, JobOrderStatus.ASSIGNED]
            and order.due_by < now
        ]
        
        return sorted(overdue, key=lambda o: o.due_by)
        
    def _estimate_duration(
        self,
        gate: GatePropertiesEnhanced,
        current_opening: float,
        target_opening: float
    ) -> int:
        """Estimate operation duration in minutes"""
        
        opening_change = abs(target_opening - current_opening)
        
        # Base time depends on gate size
        if gate.shape == gate.shape.CIRCULAR:
            base_time = 10 + int(gate.diameter_m * 5)
        else:
            base_time = 10 + int(gate.width_m * gate.height_m * 2)
            
        # Add time for opening change
        # Assume ~0.1m per minute for manual operation
        operation_time = int(opening_change * 10)
        
        return base_time + operation_time
        
    def export_orders(self, filename: str) -> None:
        """Export orders to JSON file"""
        
        orders_data = {
            order_id: order.to_dict()
            for order_id, order in self.orders.items()
        }
        
        with open(filename, 'w') as f:
            json.dump(orders_data, f, indent=2)
            
        logger.info(f"Exported {len(orders_data)} orders to {filename}")