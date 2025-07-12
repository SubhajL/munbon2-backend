#!/usr/bin/env python3
import sqlite3
import json
import sys

def inspect_geopackage(gpkg_path):
    """Inspect GeoPackage file structure"""
    conn = sqlite3.connect(gpkg_path)
    cursor = conn.cursor()
    
    print(f"Inspecting GeoPackage: {gpkg_path}\n")
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print(f"Found {len(tables)} tables:\n")
    
    for table in tables:
        table_name = table[0]
        print(f"Table: {table_name}")
        
        # Get column info
        cursor.execute(f"PRAGMA table_info({table_name});")
        columns = cursor.fetchall()
        print("  Columns:")
        for col in columns:
            print(f"    - {col[1]} ({col[2]})")
        
        # Get row count
        cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
        count = cursor.fetchone()[0]
        print(f"  Row count: {count}")
        
        # For feature tables, show sample data
        if table_name not in ['gpkg_contents', 'gpkg_geometry_columns', 'gpkg_spatial_ref_sys']:
            cursor.execute(f"SELECT * FROM {table_name} LIMIT 3;")
            rows = cursor.fetchall()
            if rows and len(columns) > 0:
                print("  Sample data (first 3 rows):")
                # Get column names
                col_names = [col[1] for col in columns]
                for i, row in enumerate(rows):
                    print(f"    Row {i+1}:")
                    for j, col_name in enumerate(col_names):
                        if col_name.lower() in ['geom', 'geometry', 'shape'] and row[j]:
                            print(f"      {col_name}: <binary geometry data>")
                        else:
                            print(f"      {col_name}: {row[j]}")
        
        print()
    
    # Check gpkg_contents
    cursor.execute("SELECT table_name, data_type, srs_id FROM gpkg_contents;")
    contents = cursor.fetchall()
    print("\nGeoPackage Contents:")
    for content in contents:
        print(f"  Table: {content[0]}, Type: {content[1]}, SRS ID: {content[2]}")
    
    conn.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python inspect-geopackage.py <path-to-gpkg>")
        sys.exit(1)
    
    inspect_geopackage(sys.argv[1])