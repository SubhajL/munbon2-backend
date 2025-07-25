"""
Sequencing optimizer for zone deliveries
Determines optimal order to minimize water residence time and maximize efficiency
"""

import numpy as np
from typing import List, Dict, Tuple, Optional
from itertools import permutations
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

@dataclass
class DeliverySequence:
    sequence: List[str]
    total_time_hours: float
    total_volume_m3: float
    avg_residence_time_hours: float
    efficiency_score: float
    gate_operations: List[Dict[str, any]]

@dataclass
class ZoneDeliveryRequest:
    zone_id: str
    volume_m3: float
    priority: int
    deadline: datetime
    min_flow_m3s: float
    max_flow_m3s: float

class SequencingOptimizer:
    def __init__(self):
        # Zone elevation data (highest to lowest)
        self.zone_elevations = {
            "Zone_1": 219.0,
            "Zone_2": 217.5,
            "Zone_3": 217.0,
            "Zone_4": 216.5,
            "Zone_5": 215.5,
            "Zone_6": 215.5
        }
        
        # Distance from main canal (M(0,0))
        self.zone_distances = {
            "Zone_1": 1800,
            "Zone_2": 2000,
            "Zone_3": 2500,
            "Zone_4": 2800,
            "Zone_5": 3200,
            "Zone_6": 3400
        }
        
        # Shared path segments
        self.shared_segments = {
            ("Zone_1", "Zone_2"): ["Source", "M(0,0)"],
            ("Zone_1", "Zone_3"): ["Source", "M(0,0)"],
            ("Zone_2", "Zone_3"): ["Source", "M(0,0)"],
            ("Zone_4", "Zone_5"): ["Source", "M(0,0)"],
            ("Zone_5", "Zone_6"): ["Source", "M(0,0)"]
        }
    
    def optimize_delivery_sequence(
        self,
        delivery_requests: List[ZoneDeliveryRequest],
        constraints: Dict[str, any] = None
    ) -> DeliverySequence:
        """Find optimal delivery sequence"""
        
        if len(delivery_requests) <= 1:
            return self._create_simple_sequence(delivery_requests)
        
        # For small numbers, try all permutations
        if len(delivery_requests) <= 6:
            return self._exhaustive_search(delivery_requests, constraints)
        
        # For larger numbers, use heuristic approach
        return self._heuristic_optimization(delivery_requests, constraints)
    
    def _exhaustive_search(
        self,
        requests: List[ZoneDeliveryRequest],
        constraints: Dict[str, any]
    ) -> DeliverySequence:
        """Try all possible sequences and find the best"""
        
        best_sequence = None
        best_score = float('-inf')
        
        zone_ids = [req.zone_id for req in requests]
        
        for perm in permutations(zone_ids):
            sequence = self._evaluate_sequence(list(perm), requests, constraints)
            
            if sequence.efficiency_score > best_score:
                best_score = sequence.efficiency_score
                best_sequence = sequence
        
        return best_sequence
    
    def _heuristic_optimization(
        self,
        requests: List[ZoneDeliveryRequest],
        constraints: Dict[str, any]
    ) -> DeliverySequence:
        """Use heuristics for larger problem sizes"""
        
        # Sort by multiple criteria
        sorted_requests = self._multi_criteria_sort(requests)
        
        # Build sequence using greedy approach with local improvements
        sequence = self._build_greedy_sequence(sorted_requests)
        
        # Apply local search improvements
        improved_sequence = self._local_search_improvement(sequence, requests, constraints)
        
        return improved_sequence
    
    def _multi_criteria_sort(self, requests: List[ZoneDeliveryRequest]) -> List[str]:
        """Sort zones by multiple criteria"""
        
        scores = {}
        
        for req in requests:
            # Priority score (higher is better)
            priority_score = req.priority / 10.0
            
            # Elevation score (higher elevation first - gravity advantage)
            elevation_score = self.zone_elevations.get(req.zone_id, 215) / 220.0
            
            # Urgency score (closer deadline is more urgent)
            time_to_deadline = (req.deadline - datetime.now()).total_seconds() / 3600
            urgency_score = 1.0 / (1.0 + time_to_deadline / 24)  # Normalize to 0-1
            
            # Volume efficiency (larger volumes first)
            volume_score = min(req.volume_m3 / 100000, 1.0)
            
            # Combined score
            total_score = (
                0.4 * priority_score +
                0.3 * elevation_score +
                0.2 * urgency_score +
                0.1 * volume_score
            )
            
            scores[req.zone_id] = total_score
        
        # Sort by score (descending)
        sorted_zones = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
        return sorted_zones
    
    def _build_greedy_sequence(self, sorted_zones: List[str]) -> List[str]:
        """Build initial sequence using greedy approach"""
        
        if not sorted_zones:
            return []
        
        sequence = [sorted_zones[0]]
        remaining = sorted_zones[1:]
        
        while remaining:
            # Find next zone that minimizes switching cost
            current_zone = sequence[-1]
            best_next = None
            min_cost = float('inf')
            
            for zone in remaining:
                cost = self._calculate_switching_cost(current_zone, zone)
                if cost < min_cost:
                    min_cost = cost
                    best_next = zone
            
            if best_next:
                sequence.append(best_next)
                remaining.remove(best_next)
            else:
                # Fallback: add first remaining
                sequence.append(remaining[0])
                remaining = remaining[1:]
        
        return sequence
    
    def _calculate_switching_cost(self, from_zone: str, to_zone: str) -> float:
        """Calculate cost of switching from one zone to another"""
        
        cost = 0.0
        
        # Elevation difference penalty (prefer downhill)
        elev_from = self.zone_elevations.get(from_zone, 217)
        elev_to = self.zone_elevations.get(to_zone, 217)
        
        if elev_to > elev_from:
            # Uphill - higher cost
            cost += (elev_to - elev_from) * 10
        else:
            # Downhill - lower cost
            cost += (elev_from - elev_to) * 2
        
        # Distance penalty
        dist_from = self.zone_distances.get(from_zone, 2000)
        dist_to = self.zone_distances.get(to_zone, 2000)
        cost += abs(dist_to - dist_from) / 1000
        
        # Shared path bonus
        if self._have_shared_path(from_zone, to_zone):
            cost *= 0.8  # 20% reduction for shared paths
        
        return cost
    
    def _have_shared_path(self, zone1: str, zone2: str) -> bool:
        """Check if two zones share part of their delivery path"""
        key1 = (zone1, zone2)
        key2 = (zone2, zone1)
        return key1 in self.shared_segments or key2 in self.shared_segments
    
    def _local_search_improvement(
        self,
        sequence: List[str],
        requests: List[ZoneDeliveryRequest],
        constraints: Dict[str, any]
    ) -> DeliverySequence:
        """Improve sequence using local search (2-opt)"""
        
        current_sequence = sequence.copy()
        current_eval = self._evaluate_sequence(current_sequence, requests, constraints)
        
        improved = True
        while improved:
            improved = False
            
            # Try all 2-opt swaps
            for i in range(len(current_sequence) - 1):
                for j in range(i + 1, len(current_sequence)):
                    # Create new sequence with swap
                    new_sequence = current_sequence.copy()
                    new_sequence[i], new_sequence[j] = new_sequence[j], new_sequence[i]
                    
                    # Evaluate
                    new_eval = self._evaluate_sequence(new_sequence, requests, constraints)
                    
                    # Accept if better
                    if new_eval.efficiency_score > current_eval.efficiency_score:
                        current_sequence = new_sequence
                        current_eval = new_eval
                        improved = True
                        break
                
                if improved:
                    break
        
        return current_eval
    
    def _evaluate_sequence(
        self,
        sequence: List[str],
        requests: List[ZoneDeliveryRequest],
        constraints: Dict[str, any]
    ) -> DeliverySequence:
        """Evaluate a delivery sequence"""
        
        # Create request lookup
        request_map = {req.zone_id: req for req in requests}
        
        total_time = 0.0
        total_volume = 0.0
        residence_times = []
        gate_operations = []
        
        current_time = 0.0
        
        for i, zone in enumerate(sequence):
            if zone not in request_map:
                continue
            
            req = request_map[zone]
            
            # Calculate delivery time
            delivery_time = req.volume_m3 / req.max_flow_m3s / 3600  # hours
            
            # Add travel time (simplified)
            travel_time = self.zone_distances.get(zone, 2000) / 1000  # hours
            
            # Calculate residence time (time water spends in system)
            residence_time = current_time + travel_time + delivery_time / 2
            residence_times.append(residence_time)
            
            # Update totals
            total_time += travel_time + delivery_time
            total_volume += req.volume_m3
            current_time += travel_time + delivery_time
            
            # Gate operations
            operations = self._plan_gate_operations(zone, req, i)
            gate_operations.extend(operations)
        
        # Calculate metrics
        avg_residence_time = np.mean(residence_times) if residence_times else 0
        
        # Efficiency score
        efficiency_score = self._calculate_efficiency_score(
            sequence,
            total_time,
            avg_residence_time,
            request_map
        )
        
        return DeliverySequence(
            sequence=sequence,
            total_time_hours=total_time,
            total_volume_m3=total_volume,
            avg_residence_time_hours=avg_residence_time,
            efficiency_score=efficiency_score,
            gate_operations=gate_operations
        )
    
    def _calculate_efficiency_score(
        self,
        sequence: List[str],
        total_time: float,
        avg_residence_time: float,
        request_map: Dict[str, ZoneDeliveryRequest]
    ) -> float:
        """Calculate overall efficiency score"""
        
        score = 100.0
        
        # Time efficiency (prefer shorter total time)
        time_penalty = total_time * 2
        score -= time_penalty
        
        # Residence time penalty (prefer shorter residence)
        residence_penalty = avg_residence_time * 3
        score -= residence_penalty
        
        # Priority satisfaction
        for i, zone in enumerate(sequence):
            if zone in request_map:
                priority = request_map[zone].priority
                # Higher priority zones should be earlier
                position_penalty = i * (10 - priority) / 10
                score -= position_penalty
        
        # Gravity utilization bonus
        for i in range(len(sequence) - 1):
            if i < len(sequence) - 1:
                current_elev = self.zone_elevations.get(sequence[i], 217)
                next_elev = self.zone_elevations.get(sequence[i+1], 217)
                if next_elev < current_elev:
                    # Downhill bonus
                    score += 5
        
        return max(0, score)
    
    def _plan_gate_operations(
        self,
        zone: str,
        request: ZoneDeliveryRequest,
        sequence_position: int
    ) -> List[Dict[str, any]]:
        """Plan gate operations for a zone delivery"""
        
        operations = []
        
        # Main distribution gate
        main_gate = f"M(0,0)->M(0,{zone[-1]})"
        
        operations.append({
            "gate_id": main_gate,
            "action": "open",
            "target_flow_m3s": request.max_flow_m3s,
            "sequence": sequence_position,
            "duration_hours": request.volume_m3 / request.max_flow_m3s / 3600
        })
        
        # Zone inlet gate
        zone_gate = f"M(0,{zone[-1]})->{zone}"
        
        operations.append({
            "gate_id": zone_gate,
            "action": "open",
            "target_flow_m3s": request.max_flow_m3s,
            "sequence": sequence_position,
            "duration_hours": request.volume_m3 / request.max_flow_m3s / 3600
        })
        
        return operations
    
    def _create_simple_sequence(
        self,
        requests: List[ZoneDeliveryRequest]
    ) -> DeliverySequence:
        """Create sequence for single delivery"""
        
        if not requests:
            return DeliverySequence(
                sequence=[],
                total_time_hours=0,
                total_volume_m3=0,
                avg_residence_time_hours=0,
                efficiency_score=0,
                gate_operations=[]
            )
        
        req = requests[0]
        delivery_time = req.volume_m3 / req.max_flow_m3s / 3600
        
        return DeliverySequence(
            sequence=[req.zone_id],
            total_time_hours=delivery_time,
            total_volume_m3=req.volume_m3,
            avg_residence_time_hours=delivery_time / 2,
            efficiency_score=100.0,
            gate_operations=self._plan_gate_operations(req.zone_id, req, 0)
        )