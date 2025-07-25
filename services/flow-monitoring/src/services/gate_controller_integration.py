"""
Gate Controller Integration Service
Integrates the water gate controller with flow monitoring
"""

import json
import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import asyncio
from pathlib import Path

from ..schemas.flow import FlowData, FlowAnalytics
from ..schemas.sensor import SensorData
from ..db.connections import DatabaseManager
from .flow_service import FlowService


class GateControllerIntegration:
    """Integration between water gate controller and flow monitoring"""
    
    def __init__(self, db_manager: DatabaseManager, flow_service: FlowService):
        self.db = db_manager
        self.flow_service = flow_service
        self.scada_file = None
        self.gate_network = None
        self.canal_geometry = None
        
    async def load_scada_configuration(self, scada_file: str):
        """Load SCADA configuration from Excel file"""
        self.scada_file = scada_file
        
        # Load gate network structure
        df = pd.read_excel(scada_file, sheet_name=0, header=1)
        
        self.gate_network = {
            'gates': {},
            'edges': [],
            'zones': {}
        }
        
        # Extract gate information
        for idx, row in df.iterrows():
            if pd.notna(row.get('Gate Valve')):
                gate_id = row['Gate Valve']
                
                gate_info = {
                    'id': gate_id,
                    'canal': row.get('Canal Name', ''),
                    'zone': row.get('Zone', 0),
                    'km': row.get('km', 0),
                    'q_max': row.get('q_max (m^3/s)', 0),
                    'velocity': row.get('ความเร็วน้ำจากการทดลอง (m/s)', 1.0),
                    'distance_m': row.get('ระยะทาง (เมตร)', 0),
                    'area_rai': row.get('Area (Rais)', 0),
                    'required_volume': row.get('Required Daily Volume (m3)', 0),
                    'indices': {
                        'i': row.get('i', 0),
                        'j': row.get('j', 0),
                        'k': row.get('k'),
                        'l': row.get('l'),
                        'm': row.get('m'),
                        'n': row.get('n')
                    }
                }
                
                self.gate_network['gates'][gate_id] = gate_info
                
                # Group by zone
                zone = str(gate_info['zone'])
                if zone not in self.gate_network['zones']:
                    self.gate_network['zones'][zone] = []
                self.gate_network['zones'][zone].append(gate_id)
        
        # Build edges (connections between gates)
        await self._build_network_edges()
        
        # Store in database
        await self._store_gate_configuration()
        
    async def _build_network_edges(self):
        """Build network edges from gate indices"""
        gates = self.gate_network['gates']
        
        # Main canal (LMC) progression
        lmc_gates = sorted([g for g, info in gates.items() 
                          if info['canal'] == 'LMC'],
                          key=lambda x: gates[x]['indices']['j'])
        
        for i in range(len(lmc_gates) - 1):
            self.gate_network['edges'].append({
                'from': lmc_gates[i],
                'to': lmc_gates[i + 1],
                'type': 'main_canal'
            })
        
        # Branch connections
        for gate_id, info in gates.items():
            if pd.notna(info['indices']['k']):  # Has branch
                # Find parent gate
                parent_indices = [info['indices']['i'], info['indices']['j']]
                parent_id = f"M({','.join(map(str, map(int, parent_indices)))})"
                
                if parent_id in gates:
                    self.gate_network['edges'].append({
                        'from': parent_id,
                        'to': gate_id,
                        'type': 'branch'
                    })
    
    async def _store_gate_configuration(self):
        """Store gate configuration in database"""
        async with self.db.postgres_pool.acquire() as conn:
            # Create tables if not exist
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS gate_configurations (
                    gate_id VARCHAR(50) PRIMARY KEY,
                    canal VARCHAR(50),
                    zone INTEGER,
                    km FLOAT,
                    q_max FLOAT,
                    velocity FLOAT,
                    distance_m FLOAT,
                    area_rai FLOAT,
                    indices JSONB,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS gate_network_edges (
                    id SERIAL PRIMARY KEY,
                    from_gate VARCHAR(50),
                    to_gate VARCHAR(50),
                    edge_type VARCHAR(20),
                    UNIQUE(from_gate, to_gate)
                )
            """)
            
            # Insert gate configurations
            for gate_id, info in self.gate_network['gates'].items():
                await conn.execute("""
                    INSERT INTO gate_configurations 
                    (gate_id, canal, zone, km, q_max, velocity, distance_m, area_rai, indices)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    ON CONFLICT (gate_id) DO UPDATE SET
                        canal = EXCLUDED.canal,
                        zone = EXCLUDED.zone,
                        km = EXCLUDED.km,
                        q_max = EXCLUDED.q_max,
                        velocity = EXCLUDED.velocity,
                        distance_m = EXCLUDED.distance_m,
                        area_rai = EXCLUDED.area_rai,
                        indices = EXCLUDED.indices,
                        updated_at = CURRENT_TIMESTAMP
                """, gate_id, info['canal'], info['zone'], info['km'],
                    info['q_max'], info['velocity'], info['distance_m'],
                    info['area_rai'], json.dumps(info['indices']))
            
            # Insert edges
            for edge in self.gate_network['edges']:
                await conn.execute("""
                    INSERT INTO gate_network_edges (from_gate, to_gate, edge_type)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (from_gate, to_gate) DO NOTHING
                """, edge['from'], edge['to'], edge['type'])
    
    async def load_canal_geometry(self, geometry_file: str):
        """Load canal geometry from JSON file"""
        with open(geometry_file, 'r') as f:
            self.canal_geometry = json.load(f)
        
        # Store in database
        async with self.db.postgres_pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS canal_geometry (
                    section_id VARCHAR(100) PRIMARY KEY,
                    from_node VARCHAR(50),
                    to_node VARCHAR(50),
                    geometry JSONB,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            for section in self.canal_geometry.get('canal_sections', []):
                section_id = f"{section['from_node']}__{section['to_node']}"
                await conn.execute("""
                    INSERT INTO canal_geometry (section_id, from_node, to_node, geometry)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (section_id) DO UPDATE SET
                        geometry = EXCLUDED.geometry,
                        updated_at = CURRENT_TIMESTAMP
                """, section_id, section['from_node'], section['to_node'],
                    json.dumps(section['geometry']))
    
    async def calculate_travel_time(self, from_gate: str, to_gate: str, 
                                  flow_rate: float) -> float:
        """Calculate water travel time between gates"""
        if to_gate not in self.gate_network['gates']:
            return 0.0
        
        gate_info = self.gate_network['gates'][to_gate]
        distance = gate_info.get('distance_m', 0)
        
        if distance == 0:
            return 0.0
        
        # Check for detailed geometry
        velocity = gate_info.get('velocity', 1.0)
        
        if self.canal_geometry:
            # Look for specific canal section
            for section in self.canal_geometry.get('canal_sections', []):
                if (section['from_node'] == from_gate and 
                    section['to_node'] == to_gate):
                    velocity = self._calculate_velocity_manning(
                        flow_rate, section['geometry']
                    )
                    break
        
        travel_time = distance / velocity if velocity > 0 else 0
        return travel_time
    
    def _calculate_velocity_manning(self, flow_rate: float, 
                                  geometry: Dict) -> float:
        """Calculate velocity using Manning's equation"""
        cs = geometry.get('cross_section', {})
        hp = geometry.get('hydraulic_params', {})
        
        if cs.get('type') == 'trapezoidal':
            import math
            
            # Simplified calculation
            y = cs.get('depth_m', 2) * 0.7  # 70% full
            b = cs.get('bottom_width_m', 5)
            m = cs.get('side_slope', 1.0)
            
            area = y * (b + m * y)
            wetted_perimeter = b + 2 * y * math.sqrt(1 + m**2)
            R = area / wetted_perimeter
            
            n = hp.get('manning_n', 0.035)
            S = hp.get('bed_slope', 0.0001)
            
            velocity = (1/n) * (R**(2/3)) * (S**0.5)
            
            # Adjust to match flow rate
            if area > 0 and abs(area * velocity - flow_rate) > 0.1:
                velocity = flow_rate / area
            
            return max(velocity, 0.1)
        
        return 1.0  # Default velocity
    
    async def run_gate_optimization(self, start_time: datetime = None):
        """Run gate operation optimization with flow monitoring"""
        if start_time is None:
            start_time = datetime.now()
        
        # Get current gate requirements
        gates_needing_water = []
        async with self.db.postgres_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT gate_id, q_max, area_rai 
                FROM gate_configurations 
                WHERE zone IS NOT NULL
                ORDER BY zone, km
            """)
            
            for row in rows:
                # Get required volume from latest sensor data or SCADA
                required_volume = await self._get_required_volume(row['gate_id'])
                if required_volume > 0:
                    gates_needing_water.append({
                        'gate_id': row['gate_id'],
                        'q_max': row['q_max'],
                        'required_volume': required_volume
                    })
        
        # Run optimization algorithm
        operations = await self._optimize_gate_operations(
            gates_needing_water, start_time
        )
        
        # Store optimization results
        await self._store_optimization_results(operations)
        
        return operations
    
    async def _get_required_volume(self, gate_id: str) -> float:
        """Get required water volume for a gate"""
        # Check if there's a sensor reading
        sensor_data = await self.flow_service.get_latest_sensor_data(gate_id)
        if sensor_data and hasattr(sensor_data, 'required_volume'):
            return sensor_data.required_volume
        
        # Otherwise use SCADA configuration
        gate_info = self.gate_network['gates'].get(gate_id, {})
        return gate_info.get('required_volume', 0)
    
    async def _optimize_gate_operations(self, gates_needing_water: List[Dict],
                                      start_time: datetime) -> List[Dict]:
        """Optimize gate operations considering travel time"""
        operations = []
        water_arrival_times = {'S': 0}  # Source has immediate water
        current_time = start_time
        step = 1
        
        while gates_needing_water:
            # Calculate optimal flow distribution
            flow_distribution = await self._calculate_flow_distribution(
                gates_needing_water, water_arrival_times
            )
            
            if not flow_distribution:
                break
            
            # Calculate fill times with travel delays
            operation_times = []
            for gate in flow_distribution:
                gate_id = gate['gate_id']
                flow_rate = gate['flow_rate']
                
                # Get travel time to this gate
                parent = await self._get_parent_gate(gate_id)
                travel_time = await self.calculate_travel_time(
                    parent, gate_id, flow_rate
                )
                
                # Update arrival time
                if parent in water_arrival_times:
                    arrival_time = water_arrival_times[parent] + travel_time
                    water_arrival_times[gate_id] = max(
                        water_arrival_times.get(gate_id, 0),
                        arrival_time
                    )
                
                # Calculate fill time
                fill_time = gate['required_volume'] / (flow_rate * 3600)  # hours
                total_time = water_arrival_times.get(gate_id, 0) / 3600 + fill_time
                
                operation_times.append({
                    'gate_id': gate_id,
                    'flow_rate': flow_rate,
                    'fill_time': fill_time,
                    'arrival_delay': water_arrival_times.get(gate_id, 0) / 3600,
                    'total_time': total_time
                })
            
            # Find minimum operation time
            min_time = min(op['total_time'] for op in operation_times)
            
            # Create operation record
            operation = {
                'step': step,
                'start_time': current_time,
                'duration_hours': min_time,
                'gates': operation_times,
                'water_arrival_times': water_arrival_times.copy()
            }
            operations.append(operation)
            
            # Update remaining volumes
            for gate in gates_needing_water[:]:
                gate_op = next((op for op in operation_times 
                              if op['gate_id'] == gate['gate_id']), None)
                if gate_op:
                    delivered = gate_op['flow_rate'] * min_time * 3600
                    gate['required_volume'] -= delivered
                    if gate['required_volume'] <= 0:
                        gates_needing_water.remove(gate)
            
            # Update time
            current_time += timedelta(hours=min_time)
            step += 1
        
        return operations
    
    async def _calculate_flow_distribution(self, gates: List[Dict],
                                         arrival_times: Dict) -> List[Dict]:
        """Calculate optimal flow distribution to gates"""
        # Simplified distribution - proportional to requirements
        total_required = sum(g['required_volume'] for g in gates)
        
        distribution = []
        for gate in gates:
            # Check if water has arrived
            gate_id = gate['gate_id']
            if gate_id in arrival_times or await self._is_source_connected(gate_id):
                flow_rate = min(
                    gate['q_max'],
                    gate['required_volume'] / 3600  # Target 1 hour fill
                )
                
                distribution.append({
                    'gate_id': gate_id,
                    'flow_rate': flow_rate,
                    'required_volume': gate['required_volume']
                })
        
        return distribution
    
    async def _get_parent_gate(self, gate_id: str) -> str:
        """Get parent gate in the network"""
        async with self.db.postgres_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT from_gate 
                FROM gate_network_edges 
                WHERE to_gate = $1
                LIMIT 1
            """, gate_id)
            
            return row['from_gate'] if row else 'S'
    
    async def _is_source_connected(self, gate_id: str) -> bool:
        """Check if gate is connected to source"""
        # Simplified - check if can reach source
        visited = set()
        to_check = [gate_id]
        
        while to_check:
            current = to_check.pop()
            if current == 'S':
                return True
            
            if current in visited:
                continue
            
            visited.add(current)
            parent = await self._get_parent_gate(current)
            if parent:
                to_check.append(parent)
        
        return False
    
    async def _store_optimization_results(self, operations: List[Dict]):
        """Store optimization results in database"""
        async with self.db.postgres_pool.acquire() as conn:
            # Create results table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS gate_optimization_results (
                    id SERIAL PRIMARY KEY,
                    run_id UUID DEFAULT gen_random_uuid(),
                    step INTEGER,
                    start_time TIMESTAMP,
                    duration_hours FLOAT,
                    operations JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Store each operation
            run_id = await conn.fetchval("SELECT gen_random_uuid()")
            
            for op in operations:
                await conn.execute("""
                    INSERT INTO gate_optimization_results 
                    (run_id, step, start_time, duration_hours, operations)
                    VALUES ($1, $2, $3, $4, $5)
                """, run_id, op['step'], op['start_time'], 
                    op['duration_hours'], json.dumps(op))
        
        # Also store in InfluxDB for time-series analysis
        for op in operations:
            for gate in op['gates']:
                await self.db.influxdb.write_point(
                    measurement="gate_operations",
                    tags={
                        "gate_id": gate['gate_id'],
                        "run_id": str(run_id)
                    },
                    fields={
                        "flow_rate": gate['flow_rate'],
                        "fill_time": gate['fill_time'],
                        "arrival_delay": gate['arrival_delay']
                    },
                    timestamp=op['start_time']
                )
    
    async def validate_gate_operations(self, operations: List[Dict]) -> Dict:
        """Validate gate operations against constraints"""
        validation_results = {
            'valid': True,
            'warnings': [],
            'errors': []
        }
        
        for op in operations:
            for gate in op['gates']:
                gate_id = gate['gate_id']
                gate_info = self.gate_network['gates'].get(gate_id, {})
                
                # Check flow rate constraints
                if gate['flow_rate'] > gate_info.get('q_max', float('inf')):
                    validation_results['errors'].append(
                        f"Gate {gate_id}: Flow rate {gate['flow_rate']} exceeds maximum {gate_info['q_max']}"
                    )
                    validation_results['valid'] = False
                
                # Check velocity constraints
                velocity = gate_info.get('velocity', 1.0)
                if velocity > 3.0:  # High velocity warning
                    validation_results['warnings'].append(
                        f"Gate {gate_id}: High velocity {velocity} m/s may cause erosion"
                    )
        
        return validation_results
    
    async def export_operations_schedule(self, operations: List[Dict], 
                                       output_file: str):
        """Export operations schedule to Excel"""
        schedule_data = []
        
        for op in operations:
            for gate in op['gates']:
                schedule_data.append({
                    'Step': op['step'],
                    'Start Time': op['start_time'],
                    'Duration (hours)': op['duration_hours'],
                    'Gate ID': gate['gate_id'],
                    'Flow Rate (m³/s)': gate['flow_rate'],
                    'Fill Time (hours)': gate['fill_time'],
                    'Arrival Delay (hours)': gate['arrival_delay'],
                    'Total Time (hours)': gate['total_time']
                })
        
        df = pd.DataFrame(schedule_data)
        df.to_excel(output_file, index=False)
        
        return output_file