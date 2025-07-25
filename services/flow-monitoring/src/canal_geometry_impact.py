#!/usr/bin/env python3
"""
Canal Geometry Impact Analysis
Shows how canal length and geometry affect irrigation control
"""

import numpy as np
from typing import Dict, List, Tuple
from dataclasses import dataclass
import json

@dataclass
class CanalSection:
    """Canal geometry between two gates"""
    section_id: str
    length_m: float
    bottom_width_m: float
    side_slope: float  # H:V ratio
    manning_n: float
    bed_slope: float
    
    def calculate_travel_time(self, flow_rate: float) -> float:
        """Calculate water travel time through this section"""
        # Calculate normal depth using Manning's equation
        y = self._calculate_normal_depth(flow_rate)
        
        # Calculate velocity
        A = self.bottom_width_m * y + self.side_slope * y * y
        P = self.bottom_width_m + 2 * y * np.sqrt(1 + self.side_slope**2)
        R = A / P
        V = (1/self.manning_n) * R**(2/3) * self.bed_slope**(1/2)
        
        # Travel time
        travel_time_minutes = (self.length_m / V) / 60
        return travel_time_minutes
    
    def calculate_storage_volume(self, depth: float) -> float:
        """Calculate water volume stored in this section at given depth"""
        A = self.bottom_width_m * depth + self.side_slope * depth * depth
        volume = A * self.length_m
        return volume
    
    def _calculate_normal_depth(self, Q: float) -> float:
        """Iterative calculation of normal depth"""
        # Simplified - returns approximate depth
        # In reality, uses Newton-Raphson iteration
        return 1.0 + (Q / 5.0) * 0.3  # Simplified formula

class CanalGeometryAnalyzer:
    """Analyzes impact of canal geometry on irrigation operations"""
    
    def __init__(self):
        # Load actual canal data from your file
        with open('/Users/subhajlimanond/dev/munbon2-backend/canal_sections_6zones_final.json', 'r') as f:
            self.canal_data = json.load(f)
        
        # Parse canal sections
        self.sections = {}
        for key, section_list in self.canal_data.items():
            if isinstance(section_list, list) and len(section_list) > 0:
                s = section_list[0]
                self.sections[key] = CanalSection(
                    section_id=key,
                    length_m=s.get('length_m', 1000),
                    bottom_width_m=s.get('bottom_width_m', 3.0),
                    side_slope=s.get('side_slope', 1.5),
                    manning_n=s.get('manning_n', 0.035),
                    bed_slope=s.get('bed_slope', 0.0001)
                )
    
    def analyze_geometry_impacts(self):
        """Show how canal geometry affects operations"""
        
        print("\n=== CANAL GEOMETRY IMPACT ANALYSIS ===\n")
        
        # Example path: Source to Zone 2
        path_sections = [
            "Source->M(0,0)",
            "M(0,0)->M(0,2)", 
            "M(0,2)->M(0,3)",
            "M(0,3)->M(0,5)",
            "M(0,5)->Zone2"
        ]
        
        print("1. Canal Sections from Source to Zone 2:")
        print("\n   Section            Length   Width   Slope    Manning's n   Travel Time")
        print("   " + "-"*75)
        
        total_length = 0
        total_travel_time = 0
        flow_rate = 2.0  # m³/s for Zone 2
        
        for section_id in path_sections:
            if section_id in self.sections:
                s = self.sections[section_id]
                travel_time = s.calculate_travel_time(flow_rate)
                total_length += s.length_m
                total_travel_time += travel_time
                
                print(f"   {section_id:<18} {s.length_m:>6.0f}m  {s.bottom_width_m:>5.1f}m  "
                      f"{s.bed_slope:>7.5f}  {s.manning_n:>7.3f}      {travel_time:>6.1f} min")
        
        print(f"\n   TOTAL:             {total_length:>6.0f}m                                    "
              f"{total_travel_time:>6.1f} min")
        
        # Show impact on operations
        print("\n2. Operational Impacts of Canal Geometry:")
        
        print("\n   A. TRAVEL TIME IMPACTS:")
        print(f"      - Water takes {total_travel_time:.0f} minutes to reach Zone 2")
        print(f"      - Must open gates {total_travel_time:.0f} minutes BEFORE irrigation needed")
        print(f"      - Close gates {total_travel_time:.0f} minutes BEFORE stopping irrigation")
        
        print("\n   B. STORAGE VOLUME IMPACTS:")
        total_storage = 0
        for section_id in path_sections:
            if section_id in self.sections:
                s = self.sections[section_id]
                storage = s.calculate_storage_volume(1.5)  # 1.5m depth
                total_storage += storage
                print(f"      {section_id}: {storage:,.0f} m³ storage capacity")
        
        print(f"      TOTAL CANAL STORAGE: {total_storage:,.0f} m³")
        print(f"      This water is 'in transit' and must be accounted for!")
        
        # Show different flow scenarios
        print("\n3. Flow Rate vs Travel Time (Geometry Impact):")
        print("\n   Flow Rate   Travel Time   Velocity   Comment")
        print("   " + "-"*50)
        
        for flow in [0.5, 1.0, 2.0, 3.0, 4.0]:
            total_time = 0
            avg_velocity = 0
            for section_id in path_sections:
                if section_id in self.sections:
                    s = self.sections[section_id]
                    time = s.calculate_travel_time(flow)
                    total_time += time
                    velocity = s.length_m / (time * 60)  # m/s
                    avg_velocity += velocity
            
            avg_velocity /= len(path_sections)
            print(f"   {flow:>4.1f} m³/s   {total_time:>6.0f} min    {avg_velocity:>5.2f} m/s   ", end="")
            
            if flow < 1.0:
                print("(Too slow - excessive losses)")
            elif flow > 3.0:
                print("(Risk of erosion)")
            else:
                print("(Optimal range)")
        
        # Show canal capacity constraints
        print("\n4. Canal Capacity Constraints:")
        
        for section_id in ["M(0,0)->M(0,2)", "M(0,2)->M(0,3)", "M(0,3)->M(0,5)"]:
            if section_id in self.sections:
                s = self.sections[section_id]
                # Estimate max capacity (simplified)
                max_depth = 2.0  # Maximum safe depth
                A_max = s.bottom_width_m * max_depth + s.side_slope * max_depth**2
                P_max = s.bottom_width_m + 2 * max_depth * np.sqrt(1 + s.side_slope**2)
                R_max = A_max / P_max
                V_max = (1/s.manning_n) * R_max**(2/3) * s.bed_slope**(1/2)
                Q_max = A_max * V_max
                
                print(f"\n   {section_id}:")
                print(f"      Geometry: {s.bottom_width_m}m bottom, 1:{s.side_slope} slopes")
                print(f"      Maximum safe flow: {Q_max:.1f} m³/s")
                print(f"      Safety factor at 4.5 m³/s: {Q_max/4.5:.1f}x")
                
                if Q_max < 4.5:
                    print(f"      WARNING: Insufficient capacity for combined flow!")
        
        return total_travel_time, total_storage
    
    def demonstrate_timing_calculations(self):
        """Show how geometry affects gate timing"""
        
        print("\n\n5. Gate Operation Timing Based on Geometry:")
        
        # Scenario: Deliver water to Zone 2 at 8:00 AM
        target_time = "08:00 AM"
        flow_rate = 2.0  # m³/s
        
        print(f"\n   Goal: Water arrives at Zone 2 at {target_time}")
        print(f"   Flow rate: {flow_rate} m³/s")
        
        # Calculate backwards
        gate_timings = []
        cumulative_time = 0
        
        path = [
            ("M(0,5)->Zone2", "M(0,5)", "Zone2"),
            ("M(0,3)->M(0,5)", "M(0,3)", "M(0,5)"),
            ("M(0,2)->M(0,3)", "M(0,2)", "M(0,3)"),
            ("M(0,0)->M(0,2)", "M(0,0)", "M(0,2)"),
            ("Source->M(0,0)", "Source", "M(0,0)")
        ]
        
        print("\n   Working backwards from delivery point:")
        
        for section_id, upstream, downstream in reversed(path):
            if section_id in self.sections:
                s = self.sections[section_id]
                travel_time = s.calculate_travel_time(flow_rate)
                cumulative_time += travel_time
                
                open_time_minutes = -cumulative_time  # Negative means before 8:00
                hours = int(abs(open_time_minutes) // 60)
                minutes = int(abs(open_time_minutes) % 60)
                
                if open_time_minutes < 0:
                    time_str = f"{8-hours-1}:{60-minutes:02d} AM"
                else:
                    time_str = f"{8+hours}:{minutes:02d} AM"
                
                gate_timings.append({
                    'gate': section_id,
                    'open_time': time_str,
                    'travel_time': travel_time,
                    'distance': s.length_m
                })
        
        print("\n   Gate Opening Schedule:")
        for timing in reversed(gate_timings):
            print(f"      {timing['open_time']} - Open {timing['gate']}")
            print(f"              (Water travels {timing['distance']:.0f}m in "
                  f"{timing['travel_time']:.0f} minutes)")
        
        print(f"\n      {target_time} - Water arrives at Zone 2!")
        
        # Show closing schedule
        print("\n   Gate Closing Schedule (after 10,000 m³ delivered):")
        delivery_duration = 10000 / (flow_rate * 3600)  # hours
        print(f"   Delivery duration: {delivery_duration:.1f} hours")
        
        # Add delivery time
        end_hour = 8 + int(delivery_duration)
        end_minute = int((delivery_duration % 1) * 60)
        
        print(f"\n   Starting from {end_hour}:{end_minute:02d} (delivery complete):")
        
        for timing in gate_timings:
            close_hour = end_hour
            close_minute = end_minute + int(timing['travel_time'])
            if close_minute >= 60:
                close_hour += close_minute // 60
                close_minute = close_minute % 60
            
            print(f"      {close_hour}:{close_minute:02d} - Close {timing['gate']}")
            print(f"              (Allow {timing['travel_time']:.0f} min for canal to drain)")

def main():
    """Run canal geometry analysis"""
    
    analyzer = CanalGeometryAnalyzer()
    travel_time, storage = analyzer.analyze_geometry_impacts()
    analyzer.demonstrate_timing_calculations()
    
    print("\n\n" + "="*70)
    print("KEY INSIGHTS: Canal Geometry Impacts")
    print("="*70)
    
    print("\n1. TRAVEL TIME: Water doesn't teleport!")
    print(f"   - Takes {travel_time:.0f} minutes from source to Zone 2")
    print("   - Must account for this in gate opening/closing times")
    
    print("\n2. STORAGE VOLUME: Water in transit")
    print(f"   - {storage:,.0f} m³ stored in canals during operation")
    print("   - This water continues flowing after gates close")
    
    print("\n3. CAPACITY LIMITS: Geometry constrains flow")
    print("   - Each section has maximum safe capacity")
    print("   - Shared sections must handle combined flows")
    
    print("\n4. VELOCITY IMPACTS: Flow rate affects timing")
    print("   - Higher flows travel faster (shorter delay)")
    print("   - But risk erosion if too fast")
    
    print("\nThe system MUST consider canal geometry for accurate control!")


if __name__ == "__main__":
    main()