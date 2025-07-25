#!/usr/bin/env python3
"""
Analyze the SCADA Excel file to understand network structure changes
"""

import pandas as pd
import os

def read_and_analyze_scada(filename):
    """Read and analyze the SCADA Excel file"""
    
    try:
        # Try to read all sheet names first
        excel_file = pd.ExcelFile(filename)
        print(f"Available sheets in the Excel file:")
        for i, sheet in enumerate(excel_file.sheet_names):
            print(f"  {i}: {sheet}")
        
        # Read the first worksheet (worksheet 1)
        print("\n=== Reading Worksheet 1 ===")
        df1 = pd.read_excel(filename, sheet_name=0)
        print(f"Shape: {df1.shape}")
        print(f"Columns: {df1.columns.tolist()}")
        
        # Display first few rows
        print("\nFirst 10 rows:")
        print(df1.head(10))
        
        # Check if it's the structure sheet
        if 'Source' in df1.columns and 'Target' in df1.columns:
            print("\n=== Network Structure Found ===")
            print("Sample edges:")
            for i in range(min(20, len(df1))):
                print(f"  {df1.iloc[i]['Source']} -> {df1.iloc[i]['Target']}")
            
            # Save to CSV for easier viewing
            df1.to_csv('network_structure.csv', index=False)
            print("\nNetwork structure saved to network_structure.csv")
            
        # Also check the second sheet (requirements)
        if len(excel_file.sheet_names) > 1:
            print("\n=== Reading Requirements Sheet ===")
            df2 = pd.read_excel(filename, sheet_name=1, skiprows=1)
            print(f"Columns: {df2.columns.tolist()}")
            
            if 'Gate Valve' in df2.columns:
                print("\nGate valves found:")
                gates = df2['Gate Valve'].dropna().unique()
                for gate in sorted(gates)[:20]:
                    print(f"  {gate}")
                print(f"  ... (total: {len(gates)} gates)")
        
        return df1
        
    except Exception as e:
        print(f"Error reading Excel file: {e}")
        return None

# Main execution
if __name__ == "__main__":
    scada_file = "/Users/subhajlimanond/dev/munbon2-backend/SCADA Section Detailed Information 2025-07-13 V0.95 SL.xlsx"
    
    print(f"Analyzing: {scada_file}")
    df = read_and_analyze_scada(scada_file)