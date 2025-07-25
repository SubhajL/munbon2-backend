#!/usr/bin/env python3
"""
Dynamic Flow Reducer - Adjusts upstream gates as downstream demands are satisfied
This is CRITICAL for efficient water use and preventing canal overflow
"""

import numpy as np
from typing import Dict, List, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta

@dataclass
class ZoneDelivery:
    zone: str
    flow_rate: float
    volume: float
    start_time: datetime
    end_time: datetime
    path: List[str]

@dataclass
class GateAdjustment:
    gate_id: str
    time: datetime
    old_flow: float
    new_flow: float
    old_opening: float
    new_opening: float
    reason: str

class DynamicFlowReducer:
    """
    Manages dynamic reduction of upstream flows as zones complete
    """
    
    def __init__(self):
        self.gate_capacity = 5.0  # m³/s per gate
        
    def calculate_dynamic_adjustments(self, deliveries: List[ZoneDelivery]) -> List[GateAdjustment]:
        """
        Calculate when and how to reduce upstream gate flows
        """
        
        print("\n=== DYNAMIC FLOW REDUCTION ANALYSIS ===\n")
        
        # Sort deliveries by end time
        sorted_deliveries = sorted(deliveries, key=lambda d: d.end_time)
        
        # Track flow requirements through each gate over time
        gate_flows = {}  # gate_id -> [(time, flow_change, reason)]
        
        # Initial flows (all zones active)
        print("1. Initial Flow Requirements (all zones active):")
        active_flows = self._calculate_gate_flows(deliveries)
        for gate, flow in sorted(active_flows.items()):
            print(f"   {gate}: {flow:.1f} m³/s")
        
        # Track adjustments as zones complete
        adjustments = []
        remaining_deliveries = deliveries.copy()
        
        print("\n2. Flow Adjustments as Zones Complete:")
        
        for completed_delivery in sorted_deliveries:
            print(f"\n   At {completed_delivery.end_time.strftime('%H:%M')} - {completed_delivery.zone} completes")
            
            # Remove completed delivery
            remaining_deliveries.remove(completed_delivery)
            
            # Recalculate required flows
            if remaining_deliveries:
                new_flows = self._calculate_gate_flows(remaining_deliveries)
            else:
                new_flows = {}
            
            # Find gates that can be reduced or closed
            for gate in active_flows:
                old_flow = active_flows.get(gate, 0)
                new_flow = new_flows.get(gate, 0)
                
                if old_flow != new_flow:
                    # Calculate gate openings
                    old_opening = min(100, (old_flow / self.gate_capacity) * 100)
                    new_opening = min(100, (new_flow / self.gate_capacity) * 100) if new_flow > 0 else 0
                    
                    adjustment = GateAdjustment(
                        gate_id=gate,
                        time=completed_delivery.end_time,
                        old_flow=old_flow,
                        new_flow=new_flow,
                        old_opening=old_opening,
                        new_opening=new_opening,
                        reason=f"{completed_delivery.zone} complete"
                    )
                    adjustments.append(adjustment)
                    
                    if new_flow == 0:
                        print(f"      CLOSE {gate} (was {old_flow:.1f} m³/s)")
                    else:
                        print(f"      REDUCE {gate}: {old_flow:.1f} → {new_flow:.1f} m³/s")
                        print(f"             Opening: {old_opening:.0f}% → {new_opening:.0f}%")
            
            # Update active flows
            active_flows = new_flows.copy()
        
        return adjustments
    
    def _calculate_gate_flows(self, deliveries: List[ZoneDelivery]) -> Dict[str, float]:
        """Calculate required flow through each gate for active deliveries"""
        
        gate_flows = {}
        
        for delivery in deliveries:
            # Add flow requirement along the path
            for i in range(len(delivery.path) - 1):
                gate_id = f"{delivery.path[i]}->{delivery.path[i+1]}"
                gate_flows[gate_id] = gate_flows.get(gate_id, 0) + delivery.flow_rate
        
        return gate_flows
    
    def demonstrate_dynamic_reduction(self):
        """
        Demonstrate dynamic flow reduction for Zones 2, 5, and 6
        """
        
        print("\n" + "="*70)
        print("DYNAMIC FLOW REDUCTION - PREVENTING OVERFLOW")
        print("="*70)
        
        start = datetime.now().replace(hour=6, minute=0, second=0, microsecond=0)
        
        # Define deliveries with different completion times
        deliveries = [
            ZoneDelivery(
                zone="Zone 2",
                flow_rate=2.0,
                volume=10000,
                start_time=start + timedelta(minutes=75),  # Water arrives
                end_time=start + timedelta(hours=2.5),     # Completes first
                path=["Source", "M(0,0)", "M(0,2)", "M(0,3)", "M(0,5)", "Zone2"]
            ),
            ZoneDelivery(
                zone="Zone 5",
                flow_rate=1.5,
                volume=7500,
                start_time=start + timedelta(minutes=90),
                end_time=start + timedelta(hours=3.0),     # Completes second
                path=["Source", "M(0,0)", "M(0,2)", "M(0,3)", "M(0,5)", "M(0,12)", "Zone5"]
            ),
            ZoneDelivery(
                zone="Zone 6",
                flow_rate=1.0,
                volume=5000,
                start_time=start + timedelta(minutes=105),
                end_time=start + timedelta(hours=3.5),     # Completes last
                path=["Source", "M(0,0)", "M(0,2)", "M(0,3)", "M(0,5)", "M(0,12)", "M(0,14)", "Zone6"]
            )
        ]
        
        # Calculate adjustments
        adjustments = self.calculate_dynamic_adjustments(deliveries)
        
        # Show timeline
        print("\n3. Complete Gate Adjustment Timeline:")
        print("\n   Time    Gate              Action                    Flow Change")
        print("   " + "-"*65)
        
        print(f"   06:00   Source→M(0,0)     OPEN to 90%              0 → 4.5 m³/s")
        print(f"           (All zones starting)")
        
        for adj in adjustments:
            time_str = adj.time.strftime('%H:%M')
            if adj.new_flow == 0:
                action = f"CLOSE"
                flow_change = f"{adj.old_flow:.1f} → 0 m³/s"
            else:
                action = f"REDUCE to {adj.new_opening:.0f}%"
                flow_change = f"{adj.old_flow:.1f} → {adj.new_flow:.1f} m³/s"
            
            print(f"   {time_str}   {adj.gate_id:<17} {action:<25} {flow_change}")
            print(f"           ({adj.reason})")
        
        # Show water savings
        print("\n4. Water Conservation Benefits:")
        
        # Without dynamic reduction
        total_time = (deliveries[-1].end_time - start).total_seconds() / 3600
        water_without = 4.5 * total_time * 3600  # m³
        
        # With dynamic reduction
        water_with = sum(d.volume for d in deliveries)
        
        savings = water_without - water_with
        savings_percent = (savings / water_without) * 100
        
        print(f"\n   Without dynamic reduction:")
        print(f"   - Main gate stays at 4.5 m³/s for {total_time:.1f} hours")
        print(f"   - Total water used: {water_without:,.0f} m³")
        
        print(f"\n   With dynamic reduction:")
        print(f"   - Gates reduced as zones complete")
        print(f"   - Total water used: {water_with:,.0f} m³")
        
        print(f"\n   WATER SAVED: {savings:,.0f} m³ ({savings_percent:.1f}%)")
        
        # Show overflow risk
        print("\n5. Overflow Risk Without Dynamic Reduction:")
        print("\n   After Zone 2 completes (8:30 AM):")
        print("   - Zone 2 gates close, stopping 2.0 m³/s consumption")
        print("   - But Source→M(0,0) still sending 4.5 m³/s!")
        print("   - EXCESS FLOW: 2.0 m³/s with nowhere to go")
        print("   - Result: Canal overflow, erosion, waste")
        
        print("\n   With Dynamic Reduction:")
        print("   - Source→M(0,0) immediately reduced to 2.5 m³/s")
        print("   - Matches remaining demand exactly")
        print("   - No overflow risk")
        
        return adjustments

def create_visual_timeline():
    """Create visual representation of dynamic flow adjustment"""
    
    print("\n\n6. Visual Timeline of Gate Adjustments:")
    print("\n   Source")
    print("     │")
    print("   06:00: 4.5 m³/s (Zones 2+5+6)")
    print("   08:30: 2.5 m³/s (Zones 5+6 only) ← REDUCED!")
    print("   09:00: 1.0 m³/s (Zone 6 only)    ← REDUCED AGAIN!")
    print("   09:30: 0 m³/s   (All complete)   ← CLOSED!")
    print("     │")
    print("   M(0,0)")
    print("     │")
    print("   [Same reduction pattern cascades downstream]")
    
    print("\n\n7. Gate Coordination Rules:")
    print("\n   RULE 1: When a zone completes, immediately reduce flow")
    print("   RULE 2: Reduction must cascade upstream to source")
    print("   RULE 3: Gate flow = sum of active downstream demands")
    print("   RULE 4: Monitor actual flow to verify reductions")


def main():
    """Run dynamic flow reduction demonstration"""
    
    reducer = DynamicFlowReducer()
    adjustments = reducer.demonstrate_dynamic_reduction()
    
    create_visual_timeline()
    
    print("\n\n" + "="*70)
    print("CRITICAL INSIGHT: Dynamic Flow Management")
    print("="*70)
    print("\nYou were absolutely right to ask about this!")
    print("\nThe system MUST dynamically reduce upstream flows as")
    print("downstream zones complete their irrigation. Otherwise:")
    print("- Canals will overflow")
    print("- Water will be wasted")
    print("- Infrastructure may be damaged")
    print("\nThis is ESSENTIAL for safe and efficient operation!")


if __name__ == "__main__":
    main()