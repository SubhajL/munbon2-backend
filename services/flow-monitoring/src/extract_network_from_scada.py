#!/usr/bin/env python3
"""
Extract network structure from SCADA Excel file
"""

import pandas as pd
import json

def extract_network_structure(filename):
    """Extract network structure from SCADA Excel"""
    
    # Read the main sheet with proper headers
    df = pd.read_excel(filename, sheet_name=0, header=0)
    
    # Print actual column names after reading with header
    print("Actual columns after header row:")
    print(df.columns.tolist())
    print("\nFirst few rows of data:")
    print(df.head(10).to_string())
    
    # Try to identify structure based on canal names and connections
    # Looking for patterns in the data
    
    # Read the characteristics sheet
    df_char = pd.read_excel(filename, sheet_name='Characteristics', skiprows=1)
    print("\n=== Characteristics Sheet ===")
    print(f"Columns: {df_char.columns.tolist()}")
    
    # Look for Gate Valve column
    if 'Gate Valve' in df_char.columns:
        print("\nGate Valves found:")
        gates = df_char[df_char['Gate Valve'].notna()]['Gate Valve']
        for gate in gates:
            print(f"  {gate}")
    
    # Let's also check if there's node naming pattern
    print("\n=== Looking for Node Patterns ===")
    
    # Save the raw data for manual inspection
    df.to_csv('scada_sheet1_raw.csv', index=False)
    df_char.to_csv('scada_characteristics_raw.csv', index=False)
    
    print("\nRaw data saved to CSV files for inspection")
    
    return df, df_char

def identify_network_changes(df):
    """Try to identify network structure from the data"""
    
    # Look for canal hierarchy
    canals = {}
    
    # Check if there's a Canal Name column
    canal_col = None
    for col in df.columns:
        if 'Canal' in str(col) or 'canal' in str(col):
            canal_col = col
            break
    
    if canal_col:
        print(f"\nCanal column found: {canal_col}")
        canal_names = df[canal_col].dropna().unique()
        print("Unique canal names:")
        for name in canal_names:
            print(f"  {name}")
    
    return canals

# Main execution
if __name__ == "__main__":
    scada_file = "/Users/subhajlimanond/dev/munbon2-backend/SCADA Section Detailed Information 2025-07-13 V0.95 SL.xlsx"
    
    print(f"Extracting network from: {scada_file}")
    df_main, df_char = extract_network_structure(scada_file)
    
    # Try to identify network
    network = identify_network_changes(df_main)