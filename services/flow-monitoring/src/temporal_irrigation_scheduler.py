#!/usr/bin/env python3
"""
Temporal Irrigation Scheduler for Munbon Network
Handles both spatial (which gates) and temporal (when to open/close) coordination
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import json

@dataclass
class IrrigationRequest:
    """Single irrigation request"""
    zone: str
    volume_m3: float  # Total volume needed
    flow_rate_m3s: float  # Desired flow rate
    priority: int = 1  # 1=highest priority
    
    @property
    def duration_hours(self) -> float:
        """Calculate irrigation duration"""
        return self.volume_m3 / self.flow_rate_m3s / 3600

@dataclass
class GateOperation:
    """Single gate operation command"""
    gate_id: str
    action: str  # 'open' or 'close'
    opening_percent: float
    time: datetime
    reason: str

@dataclass
class IrrigationSchedule:
    """Complete irrigation schedule"""
    requests: List[IrrigationRequest]
    gate_operations: List[GateOperation]
    timeline: Dict[str, List[dict]]  # zone -> timeline of events
    total_duration_hours: float
    water_usage_m3: float

class TemporalIrrigationScheduler:
    """
    Schedules gate operations over time to deliver requested water volumes
    """
    
    def __init__(self, network_file: str, canal_geometry_file: str):
        """Initialize scheduler with network data"""
        
        # Load network
        with open(network_file, 'r') as f:
            self.network = json.load(f)
        
        # Load canal geometry for travel times
        with open(canal_geometry_file, 'r') as f:
            self.canal_data = json.load(f)
        
        # Build network graph
        self.graph = {}
        for edge in self.network.get('edges', []):
            parent = edge['parent']
            child = edge['child']
            if parent not in self.graph:
                self.graph[parent] = []
            self.graph[parent].append(child)
        
        # Travel times between nodes (minutes)
        self.travel_times = self._calculate_travel_times()
        
        # Gate capacities (m³/s)
        self.gate_capacities = {}
        for edge in self.network.get('edges', []):
            gate_id = f"{edge['parent']}->{edge['child']}"
            self.gate_capacities[gate_id] = 5.0  # Default 5 m³/s
    
    def _calculate_travel_times(self) -> Dict[str, float]:
        """Calculate water travel times between adjacent nodes"""
        travel_times = {}
        
        # Use canal geometry data
        for section_id, section_list in self.canal_data.items():
            if isinstance(section_list, list) and len(section_list) > 0:
                section = section_list[0]  # Take first section
                # Average travel time based on length and typical velocity
                length_m = section.get('length_m', 1000)
                velocity_ms = 1.0  # Typical 1 m/s
                travel_time_min = (length_m / velocity_ms) / 60
                travel_times[section_id] = travel_time_min
        
        # Default for missing sections
        for edge in self.network.get('edges', []):
            gate_id = f"{edge['parent']}->{edge['child']}"
            if gate_id not in travel_times:
                travel_times[gate_id] = 15.0  # Default 15 minutes
        
        return travel_times
    
    def find_path(self, start: str, end: str) -> List[str]:
        """Find path from start to end node"""
        
        # Simple BFS
        from collections import deque
        
        queue = deque([(start, [start])])
        visited = {start}
        
        while queue:
            current, path = queue.popleft()
            
            if current == end:
                return path
            
            for neighbor in self.graph.get(current, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))
        
        return []
    
    def calculate_path_travel_time(self, path: List[str]) -> float:
        """Calculate total travel time along a path (minutes)"""
        
        total_time = 0.0
        for i in range(len(path) - 1):
            gate_id = f"{path[i]}->{path[i+1]}"
            total_time += self.travel_times.get(gate_id, 15.0)
        
        return total_time
    
    def schedule_irrigation(self, requests: List[IrrigationRequest], 
                          start_time: datetime) -> IrrigationSchedule:
        """
        Create temporal schedule for irrigation requests
        
        Args:
            requests: List of irrigation requests with volumes and flow rates
            start_time: When to start irrigation
            
        Returns:
            Complete schedule with gate operations timeline
        """
        
        print("\n=== TEMPORAL IRRIGATION SCHEDULER ===")
        print(f"Start time: {start_time.strftime('%Y-%m-%d %H:%M')}")
        print(f"Requests: {len(requests)} zones")
        
        # Sort by priority
        requests.sort(key=lambda r: r.priority)
        
        gate_operations = []
        timeline = {}
        
        for req in requests:
            print(f"\n{req.zone}:")
            print(f"  Volume: {req.volume_m3:,.0f} m³")
            print(f"  Flow rate: {req.flow_rate_m3s:.2f} m³/s")
            print(f"  Duration: {req.duration_hours:.1f} hours")
            
            # Find path
            path = self.find_path('Source', req.zone)
            if not path:
                print(f"  ERROR: No path found to {req.zone}")
                continue
            
            print(f"  Path: {' → '.join(path)}")
            
            # Calculate travel time
            travel_time = self.calculate_path_travel_time(path)
            print(f"  Travel time: {travel_time:.0f} minutes")
            
            # Create timeline for this zone
            zone_timeline = []
            
            # Gate opening sequence
            gate_open_time = start_time
            
            for i in range(len(path) - 1):
                gate_id = f"{path[i]}->{path[i+1]}"
                
                # Calculate when to open this gate
                # Open gates sequentially with small delay
                if i > 0:
                    gate_open_time += timedelta(minutes=2)
                
                # Determine opening percentage based on flow rate
                capacity = self.gate_capacities.get(gate_id, 5.0)
                opening_percent = min(100, (req.flow_rate_m3s / capacity) * 100)
                
                # Create open operation
                open_op = GateOperation(
                    gate_id=gate_id,
                    action='open',
                    opening_percent=opening_percent,
                    time=gate_open_time,
                    reason=f"Open for {req.zone} irrigation"
                )
                gate_operations.append(open_op)
                
                zone_timeline.append({
                    'time': gate_open_time.strftime('%H:%M'),
                    'action': f"Open {gate_id} to {opening_percent:.0f}%"
                })
            
            # Water arrival time
            arrival_time = start_time + timedelta(minutes=travel_time)
            zone_timeline.append({
                'time': arrival_time.strftime('%H:%M'),
                'action': f"Water arrives at {req.zone}"
            })
            
            # Irrigation duration
            irrigation_end = arrival_time + timedelta(hours=req.duration_hours)
            zone_timeline.append({
                'time': irrigation_end.strftime('%H:%M'),
                'action': f"Complete {req.volume_m3:,.0f} m³ delivery"
            })
            
            # Gate closing sequence (in reverse order)
            gate_close_time = irrigation_end
            
            for i in range(len(path) - 2, -1, -1):
                gate_id = f"{path[i]}->{path[i+1]}"
                
                # Account for drain time
                if i < len(path) - 2:
                    gate_close_time += timedelta(minutes=5)
                
                # Create close operation
                close_op = GateOperation(
                    gate_id=gate_id,
                    action='close',
                    opening_percent=0,
                    time=gate_close_time,
                    reason=f"Complete {req.zone} irrigation"
                )
                gate_operations.append(close_op)
                
                zone_timeline.append({
                    'time': gate_close_time.strftime('%H:%M'),
                    'action': f"Close {gate_id}"
                })
            
            timeline[req.zone] = zone_timeline
        
        # Sort all operations by time
        gate_operations.sort(key=lambda op: op.time)
        
        # Calculate totals
        total_volume = sum(req.volume_m3 for req in requests)
        end_time = max(op.time for op in gate_operations)
        total_duration = (end_time - start_time).total_seconds() / 3600
        
        return IrrigationSchedule(
            requests=requests,
            gate_operations=gate_operations,
            timeline=timeline,
            total_duration_hours=total_duration,
            water_usage_m3=total_volume
        )
    
    def optimize_concurrent_irrigation(self, requests: List[IrrigationRequest],
                                     start_time: datetime) -> IrrigationSchedule:
        """
        Optimize schedule for concurrent irrigation where possible
        Handles shared path segments and capacity constraints
        """
        
        print("\n=== OPTIMIZED CONCURRENT IRRIGATION ===")
        
        # Group requests by shared path segments
        path_groups = self._group_by_shared_paths(requests)
        
        gate_operations = []
        timeline = {}
        
        # Schedule each group
        current_time = start_time
        
        for group_name, group_requests in path_groups.items():
            print(f"\nGroup: {group_name}")
            print(f"Zones: {[r.zone for r in group_requests]}")
            
            # Check if concurrent irrigation is possible
            total_flow = sum(r.flow_rate_m3s for r in group_requests)
            shared_capacity = self._get_shared_path_capacity(group_requests)
            
            if total_flow <= shared_capacity:
                print(f"Concurrent irrigation possible (Total: {total_flow:.2f} m³/s)")
                # Schedule all together
                self._schedule_concurrent_group(
                    group_requests, current_time, 
                    gate_operations, timeline
                )
            else:
                print(f"Sequential irrigation required (Total {total_flow:.2f} > Capacity {shared_capacity:.2f})")
                # Schedule sequentially
                for req in group_requests:
                    self._schedule_single_zone(
                        req, current_time,
                        gate_operations, timeline
                    )
                    current_time += timedelta(hours=req.duration_hours + 0.5)
        
        # Create final schedule
        total_volume = sum(req.volume_m3 for req in requests)
        end_time = max(op.time for op in gate_operations) if gate_operations else start_time
        total_duration = (end_time - start_time).total_seconds() / 3600
        
        return IrrigationSchedule(
            requests=requests,
            gate_operations=gate_operations,
            timeline=timeline,
            total_duration_hours=total_duration,
            water_usage_m3=total_volume
        )
    
    def _group_by_shared_paths(self, requests: List[IrrigationRequest]) -> Dict[str, List[IrrigationRequest]]:
        """Group requests by shared path segments"""
        
        groups = {}
        
        for req in requests:
            path = self.find_path('Source', req.zone)
            
            # Find shared segment (simplified - uses first split point)
            if len(path) > 3:
                key = f"Shared_{path[2]}"  # Group by third node
            else:
                key = "Direct"
            
            if key not in groups:
                groups[key] = []
            groups[key].append(req)
        
        return groups
    
    def _get_shared_path_capacity(self, requests: List[IrrigationRequest]) -> float:
        """Get minimum capacity of shared path segments"""
        
        # Find common path prefix
        paths = [self.find_path('Source', req.zone) for req in requests]
        
        # Find shortest common prefix
        min_len = min(len(p) for p in paths)
        common_len = 0
        
        for i in range(min_len):
            if all(p[i] == paths[0][i] for p in paths):
                common_len = i + 1
            else:
                break
        
        # Get minimum capacity in shared segment
        min_capacity = float('inf')
        
        for i in range(common_len - 1):
            gate_id = f"{paths[0][i]}->{paths[0][i+1]}"
            capacity = self.gate_capacities.get(gate_id, 5.0)
            min_capacity = min(min_capacity, capacity)
        
        return min_capacity
    
    def _schedule_concurrent_group(self, requests: List[IrrigationRequest],
                                  start_time: datetime,
                                  gate_operations: List[GateOperation],
                                  timeline: Dict[str, List[dict]]):
        """Schedule concurrent irrigation for a group"""
        
        # Implementation would handle:
        # - Opening shared gates with combined flow
        # - Coordinating split points
        # - Synchronized closing
        pass
    
    def _schedule_single_zone(self, request: IrrigationRequest,
                            start_time: datetime,
                            gate_operations: List[GateOperation],
                            timeline: Dict[str, List[dict]]):
        """Schedule single zone irrigation"""
        
        # Implementation similar to main scheduling logic
        pass
    
    def print_schedule(self, schedule: IrrigationSchedule):
        """Print human-readable schedule"""
        
        print("\n" + "="*80)
        print("IRRIGATION SCHEDULE SUMMARY")
        print("="*80)
        
        print(f"\nTotal water usage: {schedule.water_usage_m3:,.0f} m³")
        print(f"Total duration: {schedule.total_duration_hours:.1f} hours")
        
        print("\n" + "-"*80)
        print("GATE OPERATION TIMELINE")
        print("-"*80)
        print(f"{'Time':<12} {'Gate':<25} {'Action':<10} {'Opening':<10} {'Reason'}")
        print("-"*80)
        
        for op in schedule.gate_operations:
            print(f"{op.time.strftime('%H:%M'):<12} {op.gate_id:<25} "
                  f"{op.action:<10} {op.opening_percent:>6.1f}% {op.reason}")
        
        print("\n" + "-"*80)
        print("ZONE IRRIGATION TIMELINE")
        print("-"*80)
        
        for zone, events in schedule.timeline.items():
            print(f"\n{zone}:")
            for event in events:
                print(f"  {event['time']}: {event['action']}")


def demonstrate_temporal_scheduling():
    """Demonstrate temporal irrigation scheduling"""
    
    # Create sample network
    network_data = {
        "edges": [
            {"parent": "Source", "child": "M(0,0)"},
            {"parent": "M(0,0)", "child": "M(0,2)"},
            {"parent": "M(0,2)", "child": "M(0,3)"},
            {"parent": "M(0,3)", "child": "M(0,5)"},
            {"parent": "M(0,5)", "child": "Zone2"},
            {"parent": "M(0,5)", "child": "M(0,12)"},
            {"parent": "M(0,12)", "child": "Zone5"},
            {"parent": "M(0,12)", "child": "M(0,14)"},
            {"parent": "M(0,14)", "child": "Zone6"}
        ]
    }
    
    # Save network
    with open('temporal_demo_network.json', 'w') as f:
        json.dump(network_data, f)
    
    # Create scheduler
    scheduler = TemporalIrrigationScheduler(
        'temporal_demo_network.json',
        '/Users/subhajlimanond/dev/munbon2-backend/canal_sections_6zones_final.json'
    )
    
    # Define irrigation requests
    requests = [
        IrrigationRequest(
            zone="Zone2",
            volume_m3=10000,  # 10,000 m³
            flow_rate_m3s=2.0,  # 2 m³/s
            priority=1
        ),
        IrrigationRequest(
            zone="Zone5",
            volume_m3=7500,   # 7,500 m³
            flow_rate_m3s=1.5,  # 1.5 m³/s
            priority=2
        ),
        IrrigationRequest(
            zone="Zone6",
            volume_m3=5000,   # 5,000 m³
            flow_rate_m3s=1.0,  # 1 m³/s
            priority=3
        )
    ]
    
    # Schedule irrigation starting at 6 AM
    start_time = datetime.now().replace(hour=6, minute=0, second=0, microsecond=0)
    
    # Create schedule
    schedule = scheduler.schedule_irrigation(requests, start_time)
    
    # Print schedule
    scheduler.print_schedule(schedule)
    
    # Save detailed schedule
    schedule_data = {
        'start_time': start_time.isoformat(),
        'requests': [
            {
                'zone': r.zone,
                'volume_m3': r.volume_m3,
                'flow_rate_m3s': r.flow_rate_m3s,
                'duration_hours': r.duration_hours
            }
            for r in requests
        ],
        'operations': [
            {
                'time': op.time.isoformat(),
                'gate': op.gate_id,
                'action': op.action,
                'opening_percent': op.opening_percent,
                'reason': op.reason
            }
            for op in schedule.gate_operations
        ],
        'summary': {
            'total_volume_m3': schedule.water_usage_m3,
            'total_duration_hours': schedule.total_duration_hours
        }
    }
    
    with open('irrigation_schedule.json', 'w') as f:
        json.dump(schedule_data, f, indent=2)
    
    print("\n\nDetailed schedule saved to irrigation_schedule.json")


if __name__ == "__main__":
    demonstrate_temporal_scheduling()