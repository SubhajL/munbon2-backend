#!/usr/bin/env python3
"""
Analyze network changes from the updated SCADA Excel file
"""

import pandas as pd
import networkx as nx
import json

def analyze_excel_structure(filename):
    """Analyze the Excel file structure and network changes"""
    
    # Read all sheets
    excel_file = pd.ExcelFile(filename)
    print(f"Available sheets: {excel_file.sheet_names}")
    
    # Read worksheet 1 (assuming it contains the network structure)
    if excel_file.sheet_names:
        df_structure = pd.read_excel(filename, sheet_name=0)
        print(f"\nWorksheet 1 columns: {df_structure.columns.tolist()}")
        print(f"Shape: {df_structure.shape}")
        print(f"\nFirst few rows:")
        print(df_structure.head())
        
        # Check for Source/Target columns or similar
        if 'Source' in df_structure.columns and 'Target' in df_structure.columns:
            print(f"\nNetwork edges found:")
            print(df_structure[['Source', 'Target']].head(20))
            
            # Count nodes
            all_nodes = set(df_structure['Source'].unique()) | set(df_structure['Target'].unique())
            print(f"\nTotal unique nodes: {len(all_nodes)}")
            
            # Check for LMC, RMC nodes
            lmc_nodes = [n for n in all_nodes if 'LMC' in str(n) or 'M(' in str(n)]
            rmc_nodes = [n for n in all_nodes if 'RMC' in str(n)]
            
            print(f"\nLMC-related nodes: {len(lmc_nodes)}")
            print(f"RMC-related nodes: {len(rmc_nodes)}")
            
            return df_structure
    
    return None

def compare_networks(old_structure_file, new_excel_file):
    """Compare old and new network structures"""
    
    # Read old structure
    old_df = pd.read_excel(old_structure_file)
    old_edges = set(zip(old_df['Source'], old_df['Target']))
    
    # Read new structure
    new_df = analyze_excel_structure(new_excel_file)
    if new_df is not None and 'Source' in new_df.columns:
        new_edges = set(zip(new_df['Source'], new_df['Target']))
        
        # Find differences
        removed_edges = old_edges - new_edges
        added_edges = new_edges - old_edges
        
        print(f"\n=== Network Changes ===")
        print(f"Removed edges: {len(removed_edges)}")
        for edge in sorted(removed_edges):
            print(f"  - {edge[0]} -> {edge[1]}")
        
        print(f"\nAdded edges: {len(added_edges)}")
        for edge in sorted(added_edges):
            print(f"  + {edge[0]} -> {edge[1]}")
        
        return {
            'removed': list(removed_edges),
            'added': list(added_edges)
        }
    
    return None

if __name__ == "__main__":
    # Analyze the new Excel file
    new_file = "/Users/subhajlimanond/dev/munbon2-backend/SCADA Section Detailed Information 2025-07-13 V0.95 SL.xlsx"
    
    print("=== Analyzing New SCADA Excel File ===")
    df = analyze_excel_structure(new_file)
    
    # If old Structure.xlsx exists, compare
    import os
    old_structure = "/Users/subhajlimanond/dev/munbon2-backend/Structure.xlsx"
    if os.path.exists(old_structure):
        print("\n=== Comparing with Original Structure ===")
        changes = compare_networks(old_structure, new_file)
        
        # Save changes to JSON
        if changes:
            with open('network_changes.json', 'w') as f:
                json.dump(changes, f, indent=2)
            print("\nNetwork changes saved to network_changes.json")