#!/usr/bin/env python3
"""
Convert Excel file canal section data to JSON format
for the Flow Monitoring Service
"""

import pandas as pd
import json
from datetime import datetime
import sys
import os

def convert_excel_to_canal_sections(excel_file, output_file):
    """
    Convert SCADA Excel file to canal sections JSON
    
    Expected columns in Excel:
    - Gate Valve: Gate identifier (e.g., M(0,0))
    - ระยะทาง (เมตร): Distance to next gate in meters
    - Bed Slope: Canal bed slope (optional)
    - Manning n: Manning's roughness coefficient (optional)
    - Canal Width (m): Bottom width of canal (optional)
    - Canal Depth (m): Design depth of canal (optional)
    - Side Slope: Side slope ratio H:V (optional)
    """
    
    # Read Excel file
    df = pd.read_excel(excel_file, header=1)  # Assuming headers are in row 1
    
    # Filter out rows without gate valve names
    df = df[df['Gate Valve'].notna()]
    
    canal_sections = []
    
    # Process each row to create canal sections
    for i in range(len(df) - 1):
        current_row = df.iloc[i]
        next_row = df.iloc[i + 1]
        
        # Skip if no distance data
        if pd.isna(current_row.get('ระยะทาง (เมตร)')):
            continue
            
        from_gate = str(current_row['Gate Valve']).strip()
        to_gate = str(next_row['Gate Valve']).strip()
        
        # Check if they're on the same canal
        current_canal = current_row.get('Canal Name', '')
        next_canal = next_row.get('Canal Name', '')
        
        # Only create section if on same canal
        if current_canal == next_canal and current_canal:
            section = {
                "section_id": f"{current_canal}_{from_gate}_to_{to_gate}".replace(' ', ''),
                "from_node": from_gate,
                "to_node": to_gate,
                "description": f"{current_canal} from {from_gate} to {to_gate}",
                "geometry": {
                    "length_m": float(current_row['ระยะทาง (เมตร)']),
                    "cross_section": {
                        "type": "trapezoidal",  # Default, can be customized
                        "bottom_width_m": float(current_row.get('Canal Width (m)', 10.0)),
                        "depth_m": float(current_row.get('Canal Depth (m)', 3.0)),
                        "side_slope": float(current_row.get('Side Slope', 1.5)),
                        "lining": current_row.get('Lining Type', 'earth')
                    },
                    "hydraulic_params": {
                        "manning_n": float(current_row.get('Manning n', 0.035)),  # Default for earth canal
                        "bed_slope": float(current_row.get('Bed Slope', 0.0001)),
                        "design_discharge": float(current_row.get('q_max (m^3/s)', 0)) if not pd.isna(current_row.get('q_max (m^3/s)')) else None,
                        "freeboard_m": float(current_row.get('Freeboard (m)', 0.5))
                    }
                }
            }
            
            # Calculate top width based on trapezoidal geometry
            depth = section["geometry"]["cross_section"]["depth_m"]
            side_slope = section["geometry"]["cross_section"]["side_slope"]
            bottom_width = section["geometry"]["cross_section"]["bottom_width_m"]
            section["geometry"]["cross_section"]["top_width_m"] = bottom_width + 2 * side_slope * depth
            
            canal_sections.append(section)
    
    # Also create control structures list from gate data
    control_structures = []
    for _, row in df.iterrows():
        gate_id = str(row['Gate Valve']).strip()
        
        if pd.isna(row.get('Sill Elevation (m)')):
            continue
            
        structure = {
            "structure_id": f"GATE_{gate_id.replace('(', '').replace(')', '').replace(',', '_')}",
            "location": gate_id,
            "type": str(row.get('Gate Type', 'slide_gate')).lower().replace(' ', '_'),
            "specifications": {
                "width_m": float(row.get('Gate Width (m)', 3.0)),
                "height_m": float(row.get('Gate Height (m)', 2.5)),
                "sill_elevation_m": float(row.get('Sill Elevation (m)', 0.0)),
                "discharge_coefficient": 0.61,  # Default, updated by K1/K2 calibration
                "max_opening_m": float(row.get('Gate Height (m)', 2.5))
            }
        }
        
        # Add drop structure info if present
        if str(row.get('Has Drop', 'No')).lower() in ['yes', '1', 'true']:
            structure["drop_structure"] = {
                "drop_height_m": float(row.get('Drop Height (m)', 0.0)),
                "drop_type": str(row.get('Drop Type', 'vertical')).lower()
            }
        
        control_structures.append(structure)
    
    # Create measurement points for gates with coordinates
    measurement_points = []
    point_counter = 1
    for _, row in df.iterrows():
        if not pd.isna(row.get('Latitude')) and not pd.isna(row.get('Longitude')):
            gate_id = str(row['Gate Valve']).strip()
            point = {
                "point_id": f"MP_{row.get('Canal Name', 'UNKNOWN')}_{point_counter:02d}",
                "location": gate_id,
                "type": "gate_sensor",
                "sensor_id": f"GS{point_counter:03d}",
                "reference_elevation_m": float(row.get('Sill Elevation (m)', 0.0)),
                "coordinates": {
                    "lat": float(row['Latitude']),
                    "lon": float(row['Longitude'])
                }
            }
            measurement_points.append(point)
            point_counter += 1
    
    # Create output JSON structure
    output = {
        "metadata": {
            "source_file": os.path.basename(excel_file),
            "generated_date": datetime.now().isoformat(),
            "coordinate_system": "UTM Zone 48N",
            "vertical_datum": "MSL",
            "last_survey": datetime.now().strftime("%Y-%m-%d")
        },
        "canal_sections": canal_sections,
        "control_structures": control_structures,
        "measurement_points": measurement_points,
        "notes": {
            "manning_n_values": {
                "concrete_good": 0.014,
                "concrete_fair": 0.017,
                "earth_maintained": 0.025,
                "earth_unmaintained": 0.035,
                "rock_cut": 0.030
            },
            "typical_bed_slopes": {
                "main_canal": 0.0001,
                "secondary_canal": 0.00015,
                "tertiary_canal": 0.0002
            }
        }
    }
    
    # Write to JSON file
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"Successfully converted {len(canal_sections)} canal sections")
    print(f"Generated {len(control_structures)} control structures")
    print(f"Created {len(measurement_points)} measurement points")
    print(f"Output saved to: {output_file}")
    
    # Print summary
    print("\nCanal Sections Summary:")
    print(f"{'Section ID':<30} {'Length (m)':>10} {'Slope':>8}")
    print("-" * 50)
    for section in canal_sections[:10]:  # Show first 10
        section_id = section['section_id']
        length = section['geometry']['length_m']
        slope = section['geometry']['hydraulic_params']['bed_slope']
        print(f"{section_id:<30} {length:>10.0f} {slope:>8.5f}")
    if len(canal_sections) > 10:
        print(f"... and {len(canal_sections) - 10} more sections")


def main():
    if len(sys.argv) < 2:
        print("Usage: python excel_to_canal_sections.py <excel_file> [output_json]")
        print("\nExample:")
        print("  python excel_to_canal_sections.py 'SCADA Section Detailed Information 2025-07-13 V0.95 SL.xlsx'")
        sys.exit(1)
    
    excel_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else "canal_geometry.json"
    
    if not os.path.exists(excel_file):
        print(f"Error: Excel file '{excel_file}' not found")
        sys.exit(1)
    
    convert_excel_to_canal_sections(excel_file, output_file)


if __name__ == "__main__":
    main()