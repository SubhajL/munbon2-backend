#!/usr/bin/env python3
"""
Extract K1/K2 calibration values from SCADA Excel file V1.0
Creates a JSON file with all gate calibrations for use in Flow Monitoring service
"""

import pandas as pd
import json
import os
from datetime import datetime

def extract_gate_calibrations(excel_path, output_path='gate_calibrations.json'):
    """Extract K1/K2 calibration values from SCADA Excel file"""
    
    print(f"Reading SCADA Excel file: {excel_path}")
    
    try:
        # Read all sheets to find the one with gate data
        excel_file = pd.ExcelFile(excel_path)
        print(f"Available sheets: {excel_file.sheet_names}")
        
        # Initialize calibrations dictionary
        calibrations = {
            "metadata": {
                "source": "SCADA Section Detailed Information V1.0",
                "extraction_date": datetime.now().isoformat(),
                "total_gates": 0,
                "gates_with_k1_k2": 0
            },
            "gates": {}
        }
        
        # Try to find the sheet with gate data
        # Usually it's the second sheet (Requirements)
        for sheet_idx, sheet_name in enumerate(excel_file.sheet_names):
            print(f"\nChecking sheet {sheet_idx}: {sheet_name}")
            
            # Read with different skip rows to handle header rows
            for skip in [0, 1, 2]:
                try:
                    df = pd.read_excel(excel_path, sheet_name=sheet_idx, skiprows=skip)
                    
                    # Check if this sheet has gate calibration data
                    columns_lower = [col.lower() if isinstance(col, str) else str(col) for col in df.columns]
                    
                    # Look for K1/K2 columns
                    k1_col = None
                    k2_col = None
                    gate_col = None
                    
                    for idx, col in enumerate(df.columns):
                        col_lower = columns_lower[idx]
                        if 'k1' in col_lower and 'k2' not in col_lower:
                            k1_col = col
                        elif 'k2' in col_lower:
                            k2_col = col
                        elif 'gate' in col_lower and 'valve' in col_lower:
                            gate_col = col
                            
                    if k1_col and k2_col and gate_col:
                        print(f"Found calibration data in sheet {sheet_idx} (skip={skip})")
                        print(f"  Gate column: {gate_col}")
                        print(f"  K1 column: {k1_col}")
                        print(f"  K2 column: {k2_col}")
                        
                        # Extract other useful columns
                        width_col = None
                        height_col = None
                        l1_col = None  # For automatic gate detection
                        q_max_col = None
                        zone_col = None
                        
                        for idx, col in enumerate(df.columns):
                            col_lower = columns_lower[idx]
                            if 'width' in col_lower:
                                width_col = col
                            elif 'height' in col_lower:
                                height_col = col
                            elif col_lower == 'l1 (m)' or col_lower == 'l1':
                                l1_col = col
                            elif 'q_max' in col_lower or 'qmax' in col_lower:
                                q_max_col = col
                            elif 'zone' in col_lower:
                                zone_col = col
                        
                        # Process each row
                        for idx, row in df.iterrows():
                            gate_id = row.get(gate_col)
                            
                            # Skip if no gate ID
                            if pd.isna(gate_id) or gate_id == '':
                                continue
                                
                            gate_id = str(gate_id).strip()
                            calibrations["metadata"]["total_gates"] += 1
                            
                            # Extract K1 and K2
                            k1_value = row.get(k1_col)
                            k2_value = row.get(k2_col)
                            
                            # Initialize gate data
                            gate_data = {
                                "gate_id": gate_id,
                                "has_calibration": False
                            }
                            
                            # Add K1/K2 if available
                            if not pd.isna(k1_value) and not pd.isna(k2_value):
                                gate_data["k1"] = float(k1_value)
                                gate_data["k2"] = float(k2_value)
                                gate_data["has_calibration"] = True
                                gate_data["calibration_source"] = "field_measurement"
                                calibrations["metadata"]["gates_with_k1_k2"] += 1
                            
                            # Add dimensions
                            if width_col and not pd.isna(row.get(width_col)):
                                width_val = row.get(width_col)
                                # Handle 'C' for circular gates
                                if width_val == 'C':
                                    gate_data["shape"] = "circular"
                                else:
                                    try:
                                        gate_data["width_m"] = float(width_val)
                                        gate_data["shape"] = "rectangular"
                                    except:
                                        pass
                                        
                            if height_col and not pd.isna(row.get(height_col)):
                                try:
                                    gate_data["height_m"] = float(row.get(height_col))
                                except:
                                    pass
                                    
                            # Determine if automatic (L1 = 0)
                            if l1_col and not pd.isna(row.get(l1_col)):
                                l1_val = row.get(l1_col)
                                gate_data["is_automatic"] = (l1_val == 0 or l1_val == 0.0)
                            else:
                                gate_data["is_automatic"] = False
                                
                            # Add flow capacity
                            if q_max_col and not pd.isna(row.get(q_max_col)):
                                try:
                                    gate_data["q_max_m3s"] = float(row.get(q_max_col))
                                except:
                                    pass
                                    
                            # Add zone
                            if zone_col and not pd.isna(row.get(zone_col)):
                                try:
                                    gate_data["zone"] = int(row.get(zone_col))
                                except:
                                    pass
                            
                            # Store gate data
                            calibrations["gates"][gate_id] = gate_data
                        
                        # If we found data, stop searching
                        if calibrations["metadata"]["total_gates"] > 0:
                            break
                            
                except Exception as e:
                    continue
            
            # If we found data, stop searching sheets
            if calibrations["metadata"]["total_gates"] > 0:
                break
        
        # Print summary
        print(f"\nExtraction Summary:")
        print(f"  Total gates found: {calibrations['metadata']['total_gates']}")
        print(f"  Gates with K1/K2: {calibrations['metadata']['gates_with_k1_k2']}")
        
        # Print sample gates with K1/K2
        print(f"\nSample gates with K1/K2 calibration:")
        count = 0
        for gate_id, data in calibrations["gates"].items():
            if data.get("has_calibration"):
                print(f"  {gate_id}: K1={data['k1']}, K2={data['k2']}")
                count += 1
                if count >= 10:
                    print("  ...")
                    break
        
        # Save to JSON
        with open(output_path, 'w') as f:
            json.dump(calibrations, f, indent=2)
        
        print(f"\nCalibrations saved to: {output_path}")
        
        return calibrations
        
    except Exception as e:
        print(f"Error extracting calibrations: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    # Path to SCADA Excel file V1.0
    excel_path = "/Users/subhajlimanond/dev/munbon2-backend/SCADA Section Detailed Information 2025-08-23 V1.0 SL.xlsx"
    output_path = "/Users/subhajlimanond/dev/munbon2-backend/services/flow-monitoring/src/config/gate_calibrations.json"
    
    # Create config directory if it doesn't exist
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Extract calibrations
    calibrations = extract_gate_calibrations(excel_path, output_path)