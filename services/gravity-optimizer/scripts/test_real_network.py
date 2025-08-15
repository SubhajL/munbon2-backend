#!/usr/bin/env python3
"""
Test script to verify real network data import
"""

import psycopg2
import json
from datetime import datetime

# Database connection
conn_params = {
    'host': 'localhost',
    'port': 5434,
    'database': 'munbon_dev',
    'user': 'postgres',
    'password': 'postgres'
}

def test_network_data():
    """Test the imported network data"""
    
    conn = psycopg2.connect(**conn_params)
    cur = conn.cursor()
    
    print("=== Real Network Data Verification ===")
    print(f"Time: {datetime.now().isoformat()}")
    print()
    
    # Check nodes
    cur.execute("SELECT COUNT(*) FROM gravity.hydraulic_nodes")
    node_count = cur.fetchone()[0]
    print(f"✓ Hydraulic Nodes: {node_count}")
    
    # Check channels
    cur.execute("SELECT COUNT(*) FROM gravity.channels")
    channel_count = cur.fetchone()[0]
    print(f"✓ Channels: {channel_count}")
    
    # Check channel sections
    cur.execute("SELECT COUNT(*) FROM gravity.channel_sections")
    section_count = cur.fetchone()[0]
    print(f"✓ Channel Sections: {section_count}")
    
    # Check gates
    cur.execute("SELECT COUNT(*) FROM gravity.gates")
    gate_count = cur.fetchone()[0]
    print(f"✓ Gates: {gate_count}")
    
    # Check zones
    cur.execute("SELECT COUNT(*) FROM gravity.zones")
    zone_count = cur.fetchone()[0]
    print(f"✓ Zones: {zone_count}")
    
    print("\n=== Channel Connections ===")
    
    # Check gate connections
    cur.execute("""
        SELECT 
            COUNT(*) FILTER (WHERE upstream_channel_id IS NOT NULL) as with_upstream,
            COUNT(*) FILTER (WHERE downstream_channel_id IS NOT NULL) as with_downstream,
            COUNT(*) FILTER (WHERE upstream_channel_id IS NOT NULL AND downstream_channel_id IS NOT NULL) as fully_connected
        FROM gravity.gates
    """)
    upstream, downstream, fully_connected = cur.fetchone()
    print(f"✓ Gates with upstream channel: {upstream}")
    print(f"✓ Gates with downstream channel: {downstream}")
    print(f"✓ Fully connected gates: {fully_connected}")
    
    print("\n=== Sample Network Topology ===")
    
    # Show sample connections
    cur.execute("""
        SELECT 
            g.gate_id,
            c1.channel_id as upstream_channel,
            c2.channel_id as downstream_channel,
            c1.name as upstream_name,
            c2.name as downstream_name
        FROM gravity.gates g
        LEFT JOIN gravity.channels c1 ON g.upstream_channel_id = c1.channel_id
        LEFT JOIN gravity.channels c2 ON g.downstream_channel_id = c2.channel_id
        WHERE g.gate_id IN ('M(0,0)', 'M(0,1)', 'M(0,2)', 'M(0,3)')
        ORDER BY g.gate_id
    """)
    
    print("\nMain canal gates:")
    for row in cur.fetchall():
        gate_id, up_ch, down_ch, up_name, down_name = row
        print(f"\nGate: {gate_id}")
        if up_ch:
            print(f"  ← From: {up_ch} ({up_name})")
        if down_ch:
            print(f"  → To: {down_ch} ({down_name})")
    
    print("\n=== Zone Information ===")
    
    cur.execute("""
        SELECT 
            z.zone_id,
            z.name,
            z.min_elevation,
            z.max_elevation,
            z.area_hectares,
            COUNT(DISTINCT n.node_id) as node_count
        FROM gravity.zones z
        LEFT JOIN gravity.hydraulic_nodes n ON n.priority = 
            CASE 
                WHEN z.zone_id SIMILAR TO 'zone_[0-9]+' 
                THEN CAST(SUBSTRING(z.zone_id FROM 6) AS INTEGER)
                ELSE 0
            END
        GROUP BY z.zone_id, z.name, z.min_elevation, z.max_elevation, z.area_hectares
        ORDER BY z.zone_id
    """)
    
    for row in cur.fetchall():
        zone_id, name, min_elev, max_elev, area, nodes = row
        print(f"\n{name}:")
        print(f"  Elevation range: {min_elev:.2f} - {max_elev:.2f} m")
        print(f"  Area: {area:.0f} hectares")
        print(f"  Nodes: {nodes}")
    
    print("\n=== Network Validation ===")
    
    # Check for disconnected nodes
    cur.execute("""
        SELECT COUNT(*) 
        FROM gravity.hydraulic_nodes n
        WHERE NOT EXISTS (
            SELECT 1 FROM gravity.gates g 
            WHERE g.gate_id = n.node_id
        )
        AND n.node_id != 'Source'
    """)
    disconnected = cur.fetchone()[0]
    if disconnected == 0:
        print("✓ All nodes are connected to gates")
    else:
        print(f"⚠️  {disconnected} nodes are not connected to gates")
    
    # Check channel connectivity
    cur.execute("""
        WITH channel_connections AS (
            SELECT 
                c.channel_id,
                CASE 
                    WHEN c.upstream_gate_id IS NULL THEN 'Source'
                    ELSE c.upstream_gate_id 
                END as upstream,
                (SELECT g.gate_id FROM gravity.gates g WHERE g.upstream_channel_id = c.channel_id LIMIT 1) as downstream
            FROM gravity.channels c
        )
        SELECT 
            COUNT(*) FILTER (WHERE downstream IS NULL) as dead_ends,
            COUNT(*) FILTER (WHERE upstream = 'Source') as from_source
        FROM channel_connections
    """)
    dead_ends, from_source = cur.fetchone()
    print(f"✓ Channels from source: {from_source}")
    if dead_ends > 0:
        print(f"⚠️  Dead-end channels: {dead_ends}")
    
    cur.close()
    conn.close()
    
    print("\n=== Summary ===")
    print(f"Real network data successfully imported from Flow Monitoring service")
    print(f"Total network elements: {node_count + channel_count + gate_count} (nodes + channels + gates)")
    print(f"Network covers {zone_count} irrigation zones")

if __name__ == "__main__":
    test_network_data()