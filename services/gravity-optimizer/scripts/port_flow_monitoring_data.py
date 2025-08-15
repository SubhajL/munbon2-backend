#!/usr/bin/env python3
"""
Port Flow Monitoring canal network data to Gravity Optimizer schema
Extracts real canal network topology, geometry, and elevations
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


class FlowMonitoringDataPorter:
    """ETL pipeline to port Flow Monitoring data to Gravity Optimizer"""
    
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
        
        # Zone boundaries based on Flow Monitoring data
        self.zone_boundaries = {
            0: ['M(0,1)'],  # Special zone
            1: ['M(0,0)', 'M(0,2)', 'M(0,3)', 'M(0,4)'],
            2: ['M(0,5)', 'M(0,6)', 'M(0,7)', 'M(0,8)', 'M(0,9)', 'M(0,10)'],
            3: ['M(0,11)', 'M(0,12)', 'M(0,13)'],
            4: ['M(0,14)', 'M(0,15)', 'M(0,16)'],
            5: ['M(0,17)', 'M(0,18)', 'M(0,19)'],
            6: ['M(0,20)', 'M(0,21)', 'M(0,22)']
        }
        
    def load_network_structure(self) -> Dict:
        """Load network structure from Flow Monitoring JSON"""
        network_file = self.flow_monitoring_path / 'src' / 'munbon_network_complete.json'
        with open(network_file, 'r') as f:
            return json.load(f)
    
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
                        'lining': row.get('หมายเหตุ', 'concrete')
                    })
                except (ValueError, TypeError) as e:
                    logger.warning(f"Skipping row {idx}: {e}")
                    
        return pd.DataFrame(canal_data)
    
    def interpolate_elevations(self, network: Dict) -> Dict[str, float]:
        """Interpolate missing node elevations based on canal slopes"""
        all_elevations = self.known_elevations.copy()
        
        # Get all nodes
        all_nodes = set(network['gates'].keys())
        all_nodes.add('Source')
        
        # Build connectivity graph
        connections = {}
        for gate_id, gate_data in network['gates'].items():
            # Parse gate connections from naming convention
            # M(0,0) connects Source to first node
            # M(0,1) connects M(0,0) to next, etc.
            connections[gate_id] = gate_data
        
        # Use BFS to propagate elevations downstream
        from collections import deque
        
        visited = set()
        queue = deque([('Source', 221.0)])
        
        while queue:
            node, elevation = queue.popleft()
            if node in visited:
                continue
                
            visited.add(node)
            all_elevations[node] = elevation
            
            # Find downstream nodes
            for gate_id, gate_data in network['gates'].items():
                if gate_id == node or gate_id.startswith(node + ';'):
                    # Estimate elevation drop based on typical slopes
                    # Main canal: 0.0001 (1m per 10km)
                    # Lateral: 0.0002 (2m per 10km)
                    distance = 1000  # Default 1km between gates
                    slope = 0.00015  # Average slope
                    
                    next_elevation = elevation - (distance * slope)
                    
                    # Check if we have a known elevation
                    if gate_id in self.known_elevations:
                        next_elevation = self.known_elevations[gate_id]
                    
                    if gate_id not in visited:
                        queue.append((gate_id, next_elevation))
        
        return all_elevations
    
    def create_hydraulic_nodes(self, network: Dict, elevations: Dict[str, float]) -> List[Dict]:
        """Create hydraulic nodes for gravity schema"""
        nodes = []
        
        # Add source node
        nodes.append({
            'node_id': 'source',
            'name': 'Main Reservoir',
            'elevation': 221.0,
            'lon': 101.0,  # Placeholder coordinates
            'lat': 14.0,
            'water_demand': 0.0,
            'priority': 1
        })
        
        # Add gate nodes
        for gate_id, gate_data in network['gates'].items():
            zone = gate_data.get('zone', 0)
            
            # Determine water demand based on zone and gate position
            demand = 0.0
            if zone > 0:  # Delivery gates
                # Estimate demand based on area
                area_rai = gate_data.get('area_rai', 0)
                if isinstance(area_rai, (int, float)) and not np.isnan(area_rai):
                    # Assume 1000 m³/rai/season, distributed over gates
                    demand = area_rai * 1000 / (120 * 24 * 3600)  # Convert to m³/s
            
            nodes.append({
                'node_id': gate_id,
                'name': f"{gate_data['canal']} Gate {gate_id}",
                'elevation': elevations.get(gate_id, 216.0),
                'lon': 101.0 + gate_data.get('order', 0) * 0.001,  # Spread out for visualization
                'lat': 14.0 + zone * 0.01,
                'water_demand': demand,
                'priority': min(zone + 1, 5) if zone > 0 else 1
            })
        
        return nodes
    
    def create_channels(self, canal_df: pd.DataFrame, network: Dict) -> List[Dict]:
        """Create channel sections for gravity schema"""
        channels = []
        
        # Group consecutive canal sections
        for idx, row in canal_df.iterrows():
            if row['length_m'] > 0:
                channel_id = f"canal_{idx:03d}"
                
                # Determine channel type based on capacity
                if row.get('q_max', 0) > 8:
                    channel_type = 'main'
                elif row.get('q_max', 0) > 4:
                    channel_type = 'lateral'
                else:
                    channel_type = 'sublateral'
                
                channels.append({
                    'channel_id': channel_id,
                    'name': f"Canal Section {row['start_km']} to {row['end_km']}",
                    'channel_type': channel_type,
                    'total_length': row['length_m'],
                    'avg_bed_slope': row['bed_slope'],
                    'capacity': row.get('q_max', 10.0),
                    'bed_width': row.get('bed_width', 3.0),
                    'depth': row.get('depth', 2.0),
                    'manning_n': row['manning_n'],
                    'side_slope': 1.5,  # Standard trapezoidal
                    'sections': []  # Will be populated separately
                })
        
        return channels
    
    def create_gates(self, network: Dict, elevations: Dict[str, float]) -> List[Dict]:
        """Create gate entries for gravity schema"""
        gates = []
        
        # Identify automated gates (first 20 control gates)
        automated_gates = []
        for gate_id, gate_data in sorted(network['gates'].items()):
            if gate_data.get('zone', 0) > 0 and len(automated_gates) < 20:
                automated_gates.append(gate_id)
        
        for gate_id, gate_data in network['gates'].items():
            gate_type = 'automated' if gate_id in automated_gates else 'manual'
            
            gates.append({
                'gate_id': gate_id,
                'gate_type': gate_type,
                'elevation': elevations.get(gate_id, 216.0),
                'max_opening': 1.0,  # Normalized
                'current_opening': 0.0,
                'width_m': 2.5,  # Default dimensions
                'height_m': 2.5,
                'lon': 101.0 + network['gates'][gate_id].get('order', 0) * 0.001,
                'lat': 14.0 + gate_data.get('zone', 0) * 0.01
            })
        
        return gates
    
    def create_zones(self, elevations: Dict[str, float]) -> List[Dict]:
        """Create irrigation zones with elevation ranges"""
        zones = []
        
        for zone_id, node_list in self.zone_boundaries.items():
            if zone_id == 0:
                continue  # Skip special zone
                
            # Calculate elevation range for zone
            zone_elevations = [elevations.get(node, 216.0) for node in node_list 
                             if node in elevations]
            
            if zone_elevations:
                min_elev = min(zone_elevations) - 1.0  # Account for field elevation
                max_elev = max(zone_elevations)
                avg_elev = np.mean(zone_elevations)
            else:
                # Default elevations based on zone number
                base = 219.0 - zone_id * 0.5
                min_elev = base - 1.0
                max_elev = base
                avg_elev = base - 0.5
            
            zones.append({
                'zone_id': f'zone_{zone_id}',
                'name': f'Irrigation Zone {zone_id}',
                'min_elevation': min_elev,
                'max_elevation': max_elev,
                'avg_elevation': avg_elev,
                'area_hectares': len(node_list) * 500,  # Estimate
                'priority': zone_id
            })
        
        return zones
    
    def generate_migration_sql(self, nodes, channels, gates, zones) -> str:
        """Generate SQL migration script"""
        sql = [
            "-- Gravity Optimizer Real Network Data Migration",
            "-- Generated from Flow Monitoring Service data",
            f"-- Date: {datetime.now().isoformat()}",
            "",
            "BEGIN;",
            "",
            "-- Clear existing test data",
            "TRUNCATE gravity.hydraulic_nodes CASCADE;",
            "TRUNCATE gravity.channels CASCADE;",
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
        
        sql.extend(["", "-- Insert channels"])
        for channel in channels:
            sql.append(
                f"INSERT INTO gravity.channels (channel_id, name, channel_type, total_length, "
                f"avg_bed_slope, capacity, geometry) "
                f"VALUES ('{channel['channel_id']}', '{channel['name']}', '{channel['channel_type']}', "
                f"{channel['total_length']:.2f}, {channel['avg_bed_slope']:.6f}, {channel['capacity']:.2f}, "
                f"ST_SetSRID(ST_MakeLine(ST_MakePoint(101.0, 14.0), ST_MakePoint(101.1, 14.1)), 4326));"
            )
        
        sql.extend(["", "-- Insert gates"])
        for gate in gates:
            sql.append(
                f"INSERT INTO gravity.gates (gate_id, gate_type, location, elevation, max_opening, current_opening) "
                f"VALUES ('{gate['gate_id']}', '{gate['gate_type']}', "
                f"ST_SetSRID(ST_MakePoint({gate['lon']}, {gate['lat']}), 4326), "
                f"{gate['elevation']:.2f}, {gate['max_opening']}, {gate['current_opening']});"
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
        
        sql.extend(["", "COMMIT;"])
        
        return "\n".join(sql)
    
    def run(self):
        """Execute the ETL pipeline"""
        logger.info("Starting Flow Monitoring data port...")
        
        # Load data
        logger.info("Loading network structure...")
        network = self.load_network_structure()
        
        logger.info("Loading canal geometry...")
        canal_df = self.load_canal_geometry()
        
        # Process data
        logger.info("Interpolating elevations...")
        elevations = self.interpolate_elevations(network)
        
        logger.info("Creating hydraulic nodes...")
        nodes = self.create_hydraulic_nodes(network, elevations)
        
        logger.info("Creating channels...")
        channels = self.create_channels(canal_df, network)
        
        logger.info("Creating gates...")
        gates = self.create_gates(network, elevations)
        
        logger.info("Creating zones...")
        zones = self.create_zones(elevations)
        
        # Generate outputs
        logger.info("Generating migration SQL...")
        sql = self.generate_migration_sql(nodes, channels, gates, zones)
        
        # Save outputs
        output_dir = self.gravity_optimizer_path / 'scripts' / 'migrations'
        output_dir.mkdir(exist_ok=True)
        
        sql_file = output_dir / 'import_real_network.sql'
        with open(sql_file, 'w') as f:
            f.write(sql)
        
        # Save intermediate data for validation
        data_file = output_dir / 'network_data.json'
        with open(data_file, 'w') as f:
            json.dump({
                'nodes': nodes,
                'channels': channels,
                'gates': gates,
                'zones': zones,
                'elevations': elevations
            }, f, indent=2)
        
        logger.info(f"Migration SQL saved to: {sql_file}")
        logger.info(f"Network data saved to: {data_file}")
        
        # Summary statistics
        logger.info("\n=== Import Summary ===")
        logger.info(f"Nodes: {len(nodes)}")
        logger.info(f"Channels: {len(channels)}")
        logger.info(f"Gates: {len(gates)} ({sum(1 for g in gates if g['gate_type'] == 'automated')} automated)")
        logger.info(f"Zones: {len(zones)}")
        logger.info(f"Elevation range: {min(elevations.values()):.1f}m - {max(elevations.values()):.1f}m")


if __name__ == "__main__":
    # Paths relative to project root
    flow_monitoring_path = "/Users/subhajlimanond/dev/munbon2-backend/services/flow-monitoring"
    gravity_optimizer_path = "/Users/subhajlimanond/dev/munbon2-backend/services/gravity-optimizer"
    
    porter = FlowMonitoringDataPorter(flow_monitoring_path, gravity_optimizer_path)
    porter.run()