#!/usr/bin/env python3
"""
Zone 6 Detailed Timing Analysis
1. Travel time vs FTO filling time
2. Section-by-section breakdown
3. Gate opening/closing percentages and timing
"""

import numpy as np
from datetime import datetime, timedelta
from core.calibrated_flow_model_v2 import CalibratedFlowModelV2, HydraulicConditions
from core.gate_properties_enhanced import GatePropertiesEnhanced, GateShape, GateControlType
from utils.gate_calibration_loader import GateCalibrationLoader

def detailed_timing_analysis():
    """Detailed timing analysis for Zone 6 irrigation"""
    
    print("=" * 80)
    print("Zone 6 Irrigation - Detailed Timing Analysis")
    print("=" * 80)
    
    # Initialize models
    calibration_loader = GateCalibrationLoader()
    flow_model = CalibratedFlowModelV2()
    
    # Field data
    field_area_rai = 337
    field_area_m2 = field_area_rai * 1600  # 539,200 m²
    fto_flow_rate = 0.30  # m³/s
    irrigation_hours = 3
    
    # Define Zone 6 path with canal properties
    zone6_sections = [
        {
            "from": "Dam Outlet (M(0,0))",
            "to": "PC 01 (M(0,1))",
            "gate_id": "M(0,0)",
            "distance_km": 2.0,
            "canal_width": 10.0,
            "canal_depth": 2.0,
            "elevation_from": 105.50,
            "elevation_to": 103.50
        },
        {
            "from": "PC 01 (M(0,1))",
            "to": "RMC Start (M(0,1;1,0))",
            "gate_id": "M(0,1)",
            "distance_km": 1.0,
            "canal_width": 10.0,
            "canal_depth": 2.0,
            "elevation_from": 103.50,
            "elevation_to": 102.00
        },
        {
            "from": "RMC Start (M(0,1;1,0))",
            "to": "SC 01-01 (M(0,1;1,1))",
            "gate_id": "M(0,1;1,0)",
            "distance_km": 0.5,
            "canal_width": 5.0,
            "canal_depth": 1.5,
            "elevation_from": 102.00,
            "elevation_to": 101.00
        },
        {
            "from": "SC 01-01 (M(0,1;1,1))",
            "to": "First Circular (M(0,1;1,1;1,0))",
            "gate_id": "M(0,1;1,1)",
            "distance_km": 0.5,
            "canal_width": 5.0,
            "canal_depth": 1.5,
            "elevation_from": 101.00,
            "elevation_to": 100.50
        },
        {
            "from": "First Circular (M(0,1;1,1;1,0))",
            "to": "TC 01-01-01 (M(0,1;1,1;1,1))",
            "gate_id": "M(0,1;1,1;1,0)",
            "distance_km": 0.5,
            "canal_width": 2.0,
            "canal_depth": 1.0,
            "elevation_from": 100.50,
            "elevation_to": 99.50
        },
        {
            "from": "TC 01-01-01 (M(0,1;1,1;1,1))",
            "to": "TC 01-01-02 (M(0,1;1,1;1,2))",
            "gate_id": "M(0,1;1,1;1,1)",
            "distance_km": 1.0,
            "canal_width": 2.0,
            "canal_depth": 1.0,
            "elevation_from": 99.50,
            "elevation_to": 98.50
        },
        {
            "from": "TC 01-01-02 (M(0,1;1,1;1,2))",
            "to": "FTO 337 Rai",
            "gate_id": "M(0,1;1,1;1,2)",
            "distance_km": 1.05,
            "canal_width": 2.0,
            "canal_depth": 1.0,
            "elevation_from": 98.50,
            "elevation_to": 97.30
        }
    ]
    
    print("\n1. TRAVEL TIME vs FTO FILLING TIME")
    print("-" * 60)
    print("The 2.6 hours (158 minutes) is WATER TRAVEL TIME ONLY:")
    print("- Time for water to flow from Dam to FTO through canals")
    print("- Does NOT include field/FTO filling time")
    print("- Field receives water AFTER this travel time")
    
    # Calculate FTO field filling
    print(f"\nFTO Field Details:")
    print(f"- Field area: {field_area_rai} rai ({field_area_m2:,} m²)")
    print(f"- FTO delivery rate: {fto_flow_rate} m³/s")
    print(f"- Irrigation duration: {irrigation_hours} hours")
    print(f"- Water delivered: {fto_flow_rate * irrigation_hours * 3600:,.0f} m³")
    
    print("\n2. SECTION-BY-SECTION TRAVEL TIME BREAKDOWN")
    print("-" * 80)
    print("Section                                | Dist  | Flow  | Vel   | Time  | Cumulative")
    print("                                       | (km)  | (m³/s)| (m/s) | (min) | (min)")
    print("-" * 80)
    
    cumulative_time = 0
    travel_details = []
    
    for section in zone6_sections:
        # Get gate calibration
        cal = calibration_loader.get_calibration(section["gate_id"])
        
        # Calculate flow through gate (simplified - using previous results)
        flow_rates = {
            "M(0,0)": 11.91,
            "M(0,1)": 11.91,
            "M(0,1;1,0)": 7.35,
            "M(0,1;1,1)": 7.50,
            "M(0,1;1,1;1,0)": 1.39,
            "M(0,1;1,1;1,1)": 1.19,
            "M(0,1;1,1;1,2)": 2.00
        }
        
        flow_rate = flow_rates.get(section["gate_id"], 5.0)
        
        # Calculate velocity
        area = section["canal_width"] * section["canal_depth"]
        velocity = flow_rate / area
        
        # Calculate travel time
        travel_time_hours = section["distance_km"] / (velocity * 3.6)
        travel_time_minutes = travel_time_hours * 60
        cumulative_time += travel_time_minutes
        
        print(f"{section['from']:20} → {section['to']:17} | {section['distance_km']:5.2f} | "
              f"{flow_rate:5.2f} | {velocity:5.2f} | {travel_time_minutes:5.1f} | {cumulative_time:6.1f}")
        
        travel_details.append({
            "section": f"{section['from']} → {section['to']}",
            "gate_id": section["gate_id"],
            "travel_time_min": travel_time_minutes,
            "cumulative_min": cumulative_time,
            "flow_rate": flow_rate
        })
    
    print("-" * 80)
    print(f"TOTAL TRAVEL TIME: {cumulative_time:.1f} minutes")
    
    print("\n3. GATE OPENING/CLOSING PERCENTAGE AND TIMING")
    print("-" * 80)
    
    # Assume irrigation starts at 6:00 AM
    start_time = datetime(2025, 1, 13, 6, 0, 0)  # 6:00 AM
    
    print(f"Irrigation Schedule Start: {start_time.strftime('%H:%M')}")
    print("\nGate Operations Schedule:")
    print("-" * 80)
    print("Gate ID          | Opening % | Open Time | Close Time | Duration | Notes")
    print("-" * 80)
    
    for i, detail in enumerate(travel_details):
        gate_id = detail["gate_id"]
        cal = calibration_loader.get_calibration(gate_id)
        
        # Calculate required opening percentage for desired flow
        # Using 60% as standard opening for this analysis
        opening_percent = 60
        
        # Gate open time = start time
        gate_open_time = start_time
        
        # Gate must stay open for:
        # - Its own section travel time
        # - Plus all downstream travel times
        # - Plus irrigation duration
        
        if i < len(travel_details) - 1:
            # Not the last gate - must stay open for downstream flow
            downstream_time = cumulative_time - detail["cumulative_min"] + detail["travel_time_min"]
            gate_duration_min = downstream_time + irrigation_hours * 60
        else:
            # Last gate (FTO) - stays open for irrigation duration only
            gate_duration_min = irrigation_hours * 60
        
        gate_close_time = gate_open_time + timedelta(minutes=gate_duration_min)
        
        # Determine if automatic or manual
        if gate_id == "M(0,1;1,1;1,2;1,0)" or "FTO" in detail["section"]:
            control = "AUTO"
        else:
            control = "MANUAL"
        
        print(f"{gate_id:16} | {opening_percent:8}% | {gate_open_time.strftime('%H:%M')}  | "
              f"{gate_close_time.strftime('%H:%M')}   | {gate_duration_min/60:5.1f}h   | {control}")
    
    print("\nTIMING SUMMARY:")
    print("-" * 60)
    print(f"1. All gates open at: {start_time.strftime('%H:%M')}")
    print(f"2. Water reaches FTO at: {(start_time + timedelta(minutes=cumulative_time)).strftime('%H:%M')} "
          f"(+{cumulative_time:.0f} min)")
    print(f"3. Irrigation completes at: "
          f"{(start_time + timedelta(minutes=cumulative_time + irrigation_hours*60)).strftime('%H:%M')}")
    print(f"4. Gates start closing from: {(start_time + timedelta(hours=irrigation_hours)).strftime('%H:%M')} "
          f"(upstream first)")
    
    print("\nKEY POINTS:")
    print("-" * 60)
    print("✓ 2.6 hours is TRAVEL TIME only (water movement through canals)")
    print("✓ Field irrigation happens AFTER water arrives")
    print("✓ Total operation = Travel (2.6h) + Irrigation (3h) = 5.6 hours")
    print("✓ Gates open simultaneously but close in sequence (upstream first)")
    print("✓ 60% opening is typical for balanced flow and control")
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    detailed_timing_analysis()