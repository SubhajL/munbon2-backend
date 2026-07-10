#!/usr/bin/env python3
"""
Convert Excel file with K1 and K2 columns to calibration JSON
for the Flow Monitoring Service
"""

import pandas as pd
import json
from datetime import datetime
import sys
import os

def convert_excel_to_calibration_json(excel_file, output_file):
    """
    Convert SCADA Excel file with K1 and K2 columns to calibration JSON
    
    Expected columns in Excel:
    - Gate Valve: Gate identifier (e.g., M(0,0))
    - K1: Calibration coefficient K1
    - K2: Calibration coefficient K2
    - Additional columns for metadata (optional)
    """
    
    # Read Excel file
    df = pd.read_excel(excel_file, header=1)  # Assuming headers are in row 1
    
    # Filter out rows without gate valve names
    df = df[df['Gate Valve'].notna()]
    
    calibrations = []
    gate_properties = []
    
    for _, row in df.iterrows():
        gate_id = str(row['Gate Valve']).strip()
        
        # Skip if K1 or K2 is missing
        if pd.isna(row.get('K1')) or pd.isna(row.get('K2')):
            print(f"Warning: Skipping {gate_id} - missing K1 or K2")
            continue
        
        # Create calibration entry
        calibration = {
            "gate_id": gate_id,
            "K1": float(row['K1']),
            "K2": float(row['K2']),
            "calibration_date": datetime.now().isoformat(),
            "calibration_method": "field_measurement",
            "confidence": float(row.get('Confidence', 0.9)),  # Default 0.9 if not specified
            "notes": f"Zone {row.get('Zone', 'Unknown')}, Canal: {row.get('Canal Name', 'Unknown')}"
        }
        
        # Add flow range if available
        if not pd.isna(row.get('q_max (m^3/s)')):
            q_max = float(row['q_max (m^3/s)'])
            calibration["flow_range_tested"] = [0.1, q_max]
        
        calibrations.append(calibration)
        
        # Create gate properties entry
        gate_prop = {
            "gate_id": gate_id,
            "gate_type": row.get('Gate Type', 'slide_gate').lower().replace(' ', '_'),  # Can specify gate type
            "width_m": float(row.get('Gate Width (m)', 3.0)),  # Default 3m if not specified
            "height_m": float(row.get('Gate Height (m)', 2.5)),  # Default 2.5m if not specified
            "sill_elevation_m": float(row.get('Sill Elevation (m)', 0.0)),
            "has_drop_structure": str(row.get('Has Drop', 'No')).lower() in ['yes', '1', 'true'],
            "drop_height_m": float(row.get('Drop Height (m)', 0.0)) if not pd.isna(row.get('Drop Height (m)')) else 0.0,
            "drop_type": str(row.get('Drop Type', 'none')).lower() if not pd.isna(row.get('Drop Type')) else 'none',
            "location": {
                "canal": row.get('Canal Name', ''),
                "zone": int(row.get('Zone', 0)) if not pd.isna(row.get('Zone')) else 0,
                "coordinates": {
                    "lat": float(row.get('Latitude', 0)) if not pd.isna(row.get('Latitude')) else None,
                    "lon": float(row.get('Longitude', 0)) if not pd.isna(row.get('Longitude')) else None
                }
            },
            "irrigation_area_rai": float(row.get('Area (Rais)', 0)) if not pd.isna(row.get('Area (Rais)')) else 0,
            "max_flow_m3s": float(row.get('q_max (m^3/s)', 0)) if not pd.isna(row.get('q_max (m^3/s)')) else 0
        }
        
        gate_properties.append(gate_prop)
    
    # Create output JSON structure
    output = {
        "metadata": {
            "source_file": os.path.basename(excel_file),
            "generated_date": datetime.now().isoformat(),
            "total_gates": len(calibrations),
            "description": "Gate calibration data for Munbon Irrigation System"
        },
        "calibrations": calibrations,
        "gate_properties": gate_properties
    }
    
    # Write to JSON file
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"Successfully converted {len(calibrations)} gate calibrations")
    print(f"Output saved to: {output_file}")
    
    # Print summary
    print("\nCalibration Summary:")
    print(f"{'Gate ID':<20} {'K1':>6} {'K2':>6} {'Confidence':>10}")
    print("-" * 45)
    for cal in calibrations[:10]:  # Show first 10
        print(f"{cal['gate_id']:<20} {cal['K1']:>6.3f} {cal['K2']:>6.3f} {cal['confidence']:>10.2f}")
    if len(calibrations) > 10:
        print(f"... and {len(calibrations) - 10} more gates")


def main():
    if len(sys.argv) < 2:
        print("Usage: python excel_to_calibration_json.py <excel_file> [output_json]")
        print("\nExample:")
        print("  python excel_to_calibration_json.py 'SCADA Section Detailed Information 2025-07-13 V0.95 SL.xlsx'")
        sys.exit(1)
    
    excel_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else "gate_calibrations.json"
    
    if not os.path.exists(excel_file):
        print(f"Error: Excel file '{excel_file}' not found")
        sys.exit(1)
    
    convert_excel_to_calibration_json(excel_file, output_file)


if __name__ == "__main__":
    main()