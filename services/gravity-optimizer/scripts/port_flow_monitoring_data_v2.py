#!/usr/bin/env python3
"""
Enhanced port of Flow Monitoring canal network data to Gravity Optimizer schema
Includes channel connections from network edges
"""

import json
import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EnhancedFlowMonitoringDataPorter:
    """Enhanced ETL pipeline with channel connections"""
    
    def __init__(self, flow_monitoring_path: str, gravity_optimizer_path: str):
        self.flow_monitoring_path = Path(flow_monitoring_path)
        self.gravity_optimizer_path = Path(gravity_optimizer_path)
        
        # Known elevations from hydraulic model
        self.known_elevations = {
            'Source': 221.0,
            'M(0,0)': 218.0,    # Outlet sill
            'M(0,1)': 217.9,    # RMC start
            'M(0,2)': 217.9,    # LMC start
            'M(0,3)': 217.8,    # 9R branch
            'M(0,5)': 217.0,    # Zone 2 start
            'M(0,12)': 215.0,   # 38R branch
            'M(0,14)': 214.5    # LMC end
        }
        
    def load_network_with_edges(self) -> Tuple[Dict, List]:
        """Load network structure including edges/connections"""
        network_file = self.flow_monitoring_path / 'src' / 'network_structure_updated.json'
        
        if not network_file.exists():
            # Try alternative file
            network_file = self.flow_monitoring_path / 'src' / 'munbon_network_complete.json'
        
        with open(network_file, 'r') as f:
            data = json.load(f)
        
        gates = data.get('gates', {})
        edges = data.get('edges', [])
        
        logger.info(f"Loaded {len(gates)} gates and {len(edges)} connections")
        
        return gates, edges
    
    def load_canal_geometry(self) -> pd.DataFrame:
        """Load canal geometry from SCADA characteristics CSV"""
        csv_file = self.flow_monitoring_path / 'src' / 'scada_characteristics_raw.csv'
        
        # Read with proper encoding for Thai characters
        df = pd.read_csv(csv_file, encoding='utf-8')
        
        # Clean column names
        df.columns = [col.strip() for col in df.columns]
        
        # Extract relevant data
        canal_data = []
        for idx, row in df.iterrows():
            if pd.notna(row.get('เริ่ม')) and pd.notna(row.get('สิ้นสุด')):
                try:
                    canal_data.append({
                        'start_km': row['เริ่ม'],
                        'end_km': row['สิ้นสุด'],
                        'length_m': float(row['ระยะ']) if pd.notna(row['ระยะ']) else 0,
                        'q_max': float(row['Qmax (จากแผนรอบเวรส่งน้ำ)']) if pd.notna(row.get('Qmax (จากแผนรอบเวรส่งน้ำ)')) else None,
                        'bed_width': float(row['B']) if pd.notna(row.get('B')) else None,
                        'depth': float(row['D']) if pd.notna(row.get('D')) else None,
                        'manning_n': float(row['n']) if pd.notna(row.get('n')) else 0.018,
                        'bed_slope': float(row['s']) if pd.notna(row.get('s')) else 0.0002,
                        'area_m2': float(row['A']) if pd.notna(row.get('A')) else None,
                        'velocity': float(row['V']) if pd.notna(row.get('V')) else None,
                        'side_slope': 1.5,  # Standard trapezoidal
                        'lining': row.get('หมายเหตุ', 'concrete')
                    })
                except (ValueError, TypeError) as e:
                    logger.warning(f"Skipping row {idx}: {e}")
                    
        return pd.DataFrame(canal_data)
    
    def create_channels_from_edges(self, edges: List, gates: Dict, elevations: Dict) -> List[Dict]:
        """Create channel sections from network edges"""
        channels = []
        
        for idx, (upstream_gate, downstream_gate) in enumerate(edges):
            # Skip if gates don't exist
            if upstream_gate not in gates or downstream_gate not in gates:
                continue
            
            upstream_data = gates[upstream_gate]
            downstream_data = gates[downstream_gate]
            
            # Estimate channel properties based on gate data
            q_max = None
            if 'q_max' in upstream_data and not pd.isna(upstream_data['q_max']):
                q_max = float(upstream_data['q_max'])
            elif 'q_max' in downstream_data and not pd.isna(downstream_data['q_max']):
                q_max = float(downstream_data['q_max'])
            else:
                q_max = 10.0  # Default
            
            # Determine channel type based on capacity and canal name
            canal_name = upstream_data.get('canal', 'Unknown')
            if 'LMC' in canal_name and q_max > 8:
                channel_type = 'main'
            elif q_max > 4:
                channel_type = 'lateral'
            else:
                channel_type = 'sublateral'
            
            # Calculate length from km markers if available
            length = 1000  # Default 1km
            if 'km' in upstream_data and 'km' in downstream_data:
                try:
                    # Parse km markers like "0+300" or "1+620"
                    up_km = self.parse_km_marker(str(upstream_data['km']))
                    down_km = self.parse_km_marker(str(downstream_data['km']))
                    if up_km is not None and down_km is not None:
                        length = abs(down_km - up_km) * 1000  # Convert to meters
                except:
                    pass
            
            # Calculate bed slope from elevations
            up_elev = elevations.get(upstream_gate, 216.0)
            down_elev = elevations.get(downstream_gate, 216.0)
            bed_slope = max((up_elev - down_elev) / length, 0.0001)  # Minimum slope
            
            # Generate shorter channel ID by using edge index
            channel_id = f"CH_{idx+1:03d}"
            section_id = f"SEC_{idx+1:03d}_01"
            
            channels.append({
                'channel_id': channel_id,
                'name': f"{canal_name} Section {upstream_gate} to {downstream_gate}",
                'channel_type': channel_type,
                'upstream_gate_id': upstream_gate,
                'downstream_gate_id': downstream_gate,
                'total_length': length,
                'avg_bed_slope': bed_slope,
                'capacity': q_max,
                'bed_width': 3.0 + (q_max / 2),  # Estimate based on capacity
                'depth': 2.0 + (q_max / 5),      # Estimate based on capacity
                'manning_n': 0.018,              # Concrete lining
                'side_slope': 1.5,
                'sections': [{
                    'section_id': section_id,
                    'start_elevation': up_elev,
                    'end_elevation': down_elev,
                    'length': length,
                    'bed_width': 3.0 + (q_max / 2),
                    'max_depth': 2.0 + (q_max / 5)
                }]
            })
        
        logger.info(f"Created {len(channels)} channels from {len(edges)} connections")
        return channels
    
    def parse_km_marker(self, km_str: str) -> float:
        """Parse kilometer marker like '0+300' to float"""
        if pd.isna(km_str) or km_str == 'nan':
            return None
        
        km_str = str(km_str).strip()
        if '+' in km_str:
            parts = km_str.split('+')
            km = float(parts[0])
            meters = float(parts[1]) / 1000 if len(parts) > 1 else 0
            return km + meters
        else:
            try:
                return float(km_str)
            except:
                return None
    
    def generate_enhanced_migration_sql(self, nodes, channels, gates, zones) -> str:
        """Generate SQL migration script with channel connections"""
        sql = [
            "-- Gravity Optimizer Real Network Data Migration V2",
            "-- Generated from Flow Monitoring Service data with channel connections",
            f"-- Date: {datetime.now().isoformat()}",
            "",
            "BEGIN;",
            "",
            "-- Clear existing test data",
            "TRUNCATE gravity.hydraulic_nodes CASCADE;",
            "TRUNCATE gravity.channels CASCADE;",
            "TRUNCATE gravity.channel_sections CASCADE;",
            "TRUNCATE gravity.gates CASCADE;",
            "TRUNCATE gravity.zones CASCADE;",
            "",
            "-- Insert hydraulic nodes",
        ]
        
        for node in nodes:
            sql.append(
                f"INSERT INTO gravity.hydraulic_nodes (node_id, name, elevation, location, water_demand, priority) "
                f"VALUES ('{node['node_id']}', '{node['name']}', {node['elevation']:.2f}, "
                f"ST_SetSRID(ST_MakePoint({node['lon']}, {node['lat']}), 4326), "
                f"{node['water_demand']:.4f}, {node['priority']});"
            )
        
        sql.extend(["", "-- Insert channels with connections"])
        for channel in channels:
            # Insert main channel
            sql.append(
                f"INSERT INTO gravity.channels (channel_id, name, channel_type, "
                f"upstream_gate_id, total_length, avg_bed_slope, capacity, geometry) "
                f"VALUES ('{channel['channel_id']}', '{channel['name']}', '{channel['channel_type']}', "
                f"'{channel['upstream_gate_id']}', {channel['total_length']:.2f}, "
                f"{channel['avg_bed_slope']:.6f}, {channel['capacity']:.2f}, "
                f"ST_SetSRID(ST_MakeLine(ST_MakePoint(101.0, 14.0), ST_MakePoint(101.1, 14.1)), 4326));"
            )
            
            # Insert channel sections
            for section in channel['sections']:
                sql.append(
                    f"INSERT INTO gravity.channel_sections (section_id, channel_id, "
                    f"start_elevation, end_elevation, length, bed_width, side_slope, "
                    f"manning_n, max_depth, section_order, geometry) "
                    f"VALUES ('{section['section_id']}', '{channel['channel_id']}', "
                    f"{section['start_elevation']:.2f}, {section['end_elevation']:.2f}, "
                    f"{section['length']:.2f}, {section['bed_width']:.2f}, 1.5, "
                    f"0.018, {section['max_depth']:.2f}, 1, "
                    f"ST_SetSRID(ST_MakeLine(ST_MakePoint(101.0, 14.0), ST_MakePoint(101.1, 14.1)), 4326));"
                )
        
        sql.extend(["", "-- Insert gates with upstream/downstream connections"])
        for gate in gates:
            # Find upstream and downstream channels
            upstream_channel = next((c['channel_id'] for c in channels 
                                   if c['downstream_gate_id'] == gate['gate_id']), 'NULL')
            downstream_channel = next((c['channel_id'] for c in channels 
                                     if c['upstream_gate_id'] == gate['gate_id']), 'NULL')
            
            # Format NULL properly for SQL
            upstream_sql = f"'{upstream_channel}'" if upstream_channel != 'NULL' else 'NULL'
            downstream_sql = f"'{downstream_channel}'" if downstream_channel != 'NULL' else 'NULL'
            
            sql.append(
                f"INSERT INTO gravity.gates (gate_id, gate_type, location, elevation, "
                f"max_opening, current_opening, upstream_channel_id, downstream_channel_id) "
                f"VALUES ('{gate['gate_id']}', '{gate['gate_type']}', "
                f"ST_SetSRID(ST_MakePoint({gate['lon']}, {gate['lat']}), 4326), "
                f"{gate['elevation']:.2f}, {gate['max_opening']}, {gate['current_opening']}, "
                f"{upstream_sql}, {downstream_sql});"
            )
        
        sql.extend(["", "-- Insert zones"])
        for zone in zones:
            sql.append(
                f"INSERT INTO gravity.zones (zone_id, name, min_elevation, max_elevation, area_hectares, boundary) "
                f"VALUES ('{zone['zone_id']}', '{zone['name']}', {zone['min_elevation']:.2f}, "
                f"{zone['max_elevation']:.2f}, {zone['area_hectares']}, "
                f"ST_SetSRID(ST_MakePolygon(ST_MakeLine(ARRAY["
                f"ST_MakePoint(101.0, 14.0), ST_MakePoint(101.1, 14.0), "
                f"ST_MakePoint(101.1, 14.1), ST_MakePoint(101.0, 14.1), "
                f"ST_MakePoint(101.0, 14.0)])), 4326));"
            )
        
        sql.extend(["", "-- Add source connections"])
        sql.append(
            "-- Connect source reservoir to outlet gate\n"
            "INSERT INTO gravity.channels (channel_id, name, channel_type, "
            "upstream_gate_id, total_length, avg_bed_slope, capacity, geometry) "
            "VALUES ('CH_000', 'Source to Outlet Channel', 'main', "
            "NULL, 300.0, 0.01, 11.2, "
            "ST_SetSRID(ST_MakeLine(ST_MakePoint(101.0, 14.0), ST_MakePoint(101.0, 14.01)), 4326));"
        )
        
        sql.extend(["", "COMMIT;"])
        
        return "\n".join(sql)
    
    def run(self):
        """Execute the enhanced ETL pipeline"""
        logger.info("Starting Enhanced Flow Monitoring data port...")
        
        # Load data with edges
        logger.info("Loading network structure with edges...")
        gates, edges = self.load_network_with_edges()
        
        logger.info("Loading canal geometry...")
        canal_df = self.load_canal_geometry()
        
        # Use original interpolation for nodes
        from port_flow_monitoring_data import FlowMonitoringDataPorter
        original_porter = FlowMonitoringDataPorter(
            self.flow_monitoring_path, 
            self.gravity_optimizer_path
        )
        
        # Create full network structure
        network = {'gates': gates}
        elevations = original_porter.interpolate_elevations(network)
        nodes = original_porter.create_hydraulic_nodes(network, elevations)
        gates_list = original_porter.create_gates(network, elevations)
        zones = original_porter.create_zones(elevations)
        
        # Create channels from edges
        logger.info("Creating channels from network connections...")
        channels = self.create_channels_from_edges(edges, gates, elevations)
        
        # Generate enhanced SQL
        logger.info("Generating enhanced migration SQL...")
        sql = self.generate_enhanced_migration_sql(nodes, channels, gates_list, zones)
        
        # Save outputs
        output_dir = self.gravity_optimizer_path / 'scripts' / 'migrations'
        output_dir.mkdir(exist_ok=True)
        
        sql_file = output_dir / 'import_real_network_v2.sql'
        with open(sql_file, 'w') as f:
            f.write(sql)
        
        # Save enhanced data
        data_file = output_dir / 'network_data_v2.json'
        with open(data_file, 'w') as f:
            json.dump({
                'nodes': nodes,
                'channels': channels,
                'gates': gates_list,
                'zones': zones,
                'edges': edges,
                'elevations': elevations
            }, f, indent=2)
        
        logger.info(f"Enhanced migration SQL saved to: {sql_file}")
        logger.info(f"Enhanced network data saved to: {data_file}")
        
        # Summary statistics
        logger.info("\n=== Enhanced Import Summary ===")
        logger.info(f"Nodes: {len(nodes)}")
        logger.info(f"Channels: {len(channels)}")
        logger.info(f"Channel Sections: {sum(len(c['sections']) for c in channels)}")
        logger.info(f"Gates: {len(gates_list)} ({sum(1 for g in gates_list if g['gate_type'] == 'automated')} automated)")
        logger.info(f"Zones: {len(zones)}")
        logger.info(f"Network Connections: {len(edges)}")


if __name__ == "__main__":
    # Paths relative to project root
    flow_monitoring_path = "/Users/subhajlimanond/dev/munbon2-backend/services/flow-monitoring"
    gravity_optimizer_path = "/Users/subhajlimanond/dev/munbon2-backend/services/gravity-optimizer"
    
    porter = EnhancedFlowMonitoringDataPorter(flow_monitoring_path, gravity_optimizer_path)
    porter.run()