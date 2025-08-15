#!/usr/bin/env python3
"""
Validate gravity flow feasibility for the imported network
Ensures all zones can receive water by gravity with adequate head
"""

import json
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GravityFlowValidator:
    """Validates that water can flow by gravity to all zones"""
    
    def __init__(self, network_data_path: str):
        # Load network data
        with open(network_data_path, 'r') as f:
            self.data = json.load(f)
        
        self.nodes = {n['node_id']: n for n in self.data['nodes']}
        self.channels = {c['channel_id']: c for c in self.data['channels']}
        self.gates = {g['gate_id']: g for g in self.data['gates']}
        self.zones = {z['zone_id']: z for z in self.data['zones']}
        self.elevations = self.data['elevations']
        
        # Physical constants
        self.GRAVITY = 9.81
        self.MIN_VELOCITY = 0.3  # m/s to prevent sedimentation
        self.MAX_VELOCITY = 2.0  # m/s to prevent erosion
        self.MIN_DEPTH = 0.3     # m minimum operational depth
        self.SAFETY_FACTOR = 1.2  # 20% safety margin
        
    def calculate_head_loss(self, flow_rate: float, channel: Dict, length: float) -> float:
        """Calculate head loss using Manning's equation"""
        # Extract channel properties
        n = channel.get('manning_n', 0.018)
        b = channel.get('bed_width', 3.0)
        d = channel.get('depth', 2.0)
        s = channel.get('avg_bed_slope', 0.0002)
        m = channel.get('side_slope', 1.5)  # Side slope (H:V)
        
        # Estimate flow depth using iterative method
        # For trapezoidal channel: A = y(b + my), P = b + 2y√(1+m²)
        y = d * 0.7  # Initial guess at 70% full
        
        for _ in range(10):  # Newton-Raphson iterations
            A = y * (b + m * y)
            P = b + 2 * y * np.sqrt(1 + m**2)
            R = A / P
            
            # Manning's equation: Q = (1/n) * A * R^(2/3) * S^(1/2)
            Q_calc = (1/n) * A * (R**(2/3)) * (s**0.5)
            
            if abs(Q_calc - flow_rate) < 0.01:
                break
                
            # Adjust depth
            if Q_calc < flow_rate:
                y *= 1.1
            else:
                y *= 0.9
        
        # Calculate velocity
        V = flow_rate / A if A > 0 else 0
        
        # Head loss = friction slope * length
        # For uniform flow, friction slope ≈ bed slope
        # Additional losses for bends, structures, etc.
        friction_loss = s * length
        minor_losses = 0.1 * (V**2) / (2 * self.GRAVITY)  # 10% for minor losses
        
        total_loss = friction_loss + minor_losses
        
        return total_loss, V, y
    
    def trace_flow_path(self, source_node: str, target_zone: str) -> Tuple[List[str], float]:
        """Trace flow path from source to zone and calculate total head loss"""
        # Simplified path finding - in reality would use network topology
        # For now, assume direct path with typical losses
        
        source_elev = self.nodes[source_node]['elevation']
        zone_data = self.zones[target_zone]
        target_elev = zone_data['max_elevation']
        
        # Estimate path length based on zone number
        zone_num = int(target_zone.split('_')[1])
        path_length = zone_num * 6000  # Approximate 6km per zone
        
        # Typical flow rate for zone
        zone_demand = zone_data['area_hectares'] * 0.002  # m³/s per hectare
        
        # Calculate losses along path
        typical_channel = {
            'manning_n': 0.018,
            'bed_width': 10.0 - zone_num,  # Channels get smaller
            'depth': 3.0 - zone_num * 0.3,
            'avg_bed_slope': 0.00015,
            'side_slope': 1.5
        }
        
        head_loss, velocity, depth = self.calculate_head_loss(
            zone_demand, typical_channel, path_length
        )
        
        # Apply safety factor
        head_loss *= self.SAFETY_FACTOR
        
        return ['source', f'intermediate_{zone_num}', target_zone], head_loss
    
    def validate_zone_delivery(self, zone_id: str) -> Dict:
        """Validate that a zone can receive water by gravity"""
        zone = self.zones[zone_id]
        source_elev = self.nodes['source']['elevation']
        
        # Trace path and calculate losses
        path, head_loss = self.trace_flow_path('source', zone_id)
        
        # Available head
        available_head = source_elev - zone['max_elevation']
        
        # Required head (losses + minimum depth)
        required_head = head_loss + self.MIN_DEPTH
        
        # Feasibility check
        feasible = available_head > required_head
        margin = available_head - required_head
        
        return {
            'zone_id': zone_id,
            'zone_name': zone['name'],
            'feasible': feasible,
            'source_elevation': source_elev,
            'zone_max_elevation': zone['max_elevation'],
            'zone_min_elevation': zone['min_elevation'],
            'available_head': available_head,
            'required_head': required_head,
            'head_loss': head_loss,
            'safety_margin': margin,
            'path': path,
            'critical': margin < 0.5  # Less than 0.5m margin
        }
    
    def validate_gate_operations(self) -> List[Dict]:
        """Validate gate elevations and operational ranges"""
        issues = []
        
        for gate_id, gate in self.gates.items():
            gate_elev = gate['elevation']
            
            # Check if gate is below source
            if gate_elev > self.nodes['source']['elevation']:
                issues.append({
                    'gate_id': gate_id,
                    'issue': 'Gate elevation above source',
                    'gate_elevation': gate_elev,
                    'source_elevation': self.nodes['source']['elevation']
                })
            
            # Check minimum operational depth
            if gate_id in self.nodes:
                node = self.nodes[gate_id]
                if node['elevation'] + self.MIN_DEPTH > gate_elev:
                    issues.append({
                        'gate_id': gate_id,
                        'issue': 'Insufficient operational depth',
                        'required_level': node['elevation'] + self.MIN_DEPTH,
                        'gate_elevation': gate_elev
                    })
        
        return issues
    
    def validate_channel_velocities(self) -> List[Dict]:
        """Check that velocities are within acceptable range"""
        velocity_issues = []
        
        for channel_id, channel in self.channels.items():
            # Use design discharge
            flow_rate = channel.get('capacity', 10.0)
            
            # Calculate velocity
            _, velocity, depth = self.calculate_head_loss(
                flow_rate, channel, 100  # Just for velocity calc
            )
            
            if velocity < self.MIN_VELOCITY:
                velocity_issues.append({
                    'channel_id': channel_id,
                    'issue': 'Velocity too low - sedimentation risk',
                    'velocity': velocity,
                    'min_required': self.MIN_VELOCITY
                })
            elif velocity > self.MAX_VELOCITY:
                velocity_issues.append({
                    'channel_id': channel_id,
                    'issue': 'Velocity too high - erosion risk',
                    'velocity': velocity,
                    'max_allowed': self.MAX_VELOCITY
                })
        
        return velocity_issues
    
    def generate_report(self) -> Dict:
        """Generate comprehensive validation report"""
        report = {
            'timestamp': str(Path(__file__).stat().st_mtime),
            'network_summary': {
                'total_nodes': len(self.nodes),
                'total_channels': len(self.channels),
                'total_gates': len(self.gates),
                'automated_gates': sum(1 for g in self.gates.values() if g['gate_type'] == 'automated'),
                'total_zones': len(self.zones),
                'elevation_range': {
                    'min': min(self.elevations.values()),
                    'max': max(self.elevations.values()),
                    'source': self.nodes['source']['elevation']
                }
            },
            'zone_validation': {},
            'gate_issues': [],
            'velocity_issues': [],
            'overall_feasibility': True
        }
        
        # Validate each zone
        logger.info("Validating zone deliveries...")
        for zone_id in self.zones:
            validation = self.validate_zone_delivery(zone_id)
            report['zone_validation'][zone_id] = validation
            
            if not validation['feasible']:
                report['overall_feasibility'] = False
                logger.warning(f"Zone {zone_id} is not feasible by gravity!")
        
        # Validate gates
        logger.info("Validating gate operations...")
        report['gate_issues'] = self.validate_gate_operations()
        
        # Validate velocities
        logger.info("Validating channel velocities...")
        report['velocity_issues'] = self.validate_channel_velocities()
        
        # Summary statistics
        feasible_zones = sum(1 for v in report['zone_validation'].values() if v['feasible'])
        critical_zones = sum(1 for v in report['zone_validation'].values() if v.get('critical', False))
        
        report['summary'] = {
            'feasible_zones': feasible_zones,
            'infeasible_zones': len(self.zones) - feasible_zones,
            'critical_zones': critical_zones,
            'gate_issues_count': len(report['gate_issues']),
            'velocity_issues_count': len(report['velocity_issues']),
            'recommendation': 'System is feasible' if report['overall_feasibility'] else 'System needs modification'
        }
        
        return report
    
    def print_summary(self, report: Dict):
        """Print validation summary"""
        print("\n" + "="*60)
        print("GRAVITY FLOW VALIDATION REPORT")
        print("="*60)
        
        print(f"\nNetwork Summary:")
        print(f"  - Nodes: {report['network_summary']['total_nodes']}")
        print(f"  - Gates: {report['network_summary']['total_gates']} ({report['network_summary']['automated_gates']} automated)")
        print(f"  - Zones: {report['network_summary']['total_zones']}")
        print(f"  - Elevation range: {report['network_summary']['elevation_range']['min']:.1f}m - {report['network_summary']['elevation_range']['max']:.1f}m")
        
        print(f"\nZone Feasibility:")
        for zone_id, validation in report['zone_validation'].items():
            status = "✓ FEASIBLE" if validation['feasible'] else "✗ INFEASIBLE"
            margin = validation['safety_margin']
            critical = " [CRITICAL]" if validation.get('critical') else ""
            
            print(f"  {validation['zone_name']}: {status} (margin: {margin:.2f}m){critical}")
            if not validation['feasible']:
                print(f"    Required head: {validation['required_head']:.2f}m")
                print(f"    Available head: {validation['available_head']:.2f}m")
        
        if report['gate_issues']:
            print(f"\nGate Issues: {len(report['gate_issues'])}")
            for issue in report['gate_issues'][:5]:  # Show first 5
                print(f"  - {issue['gate_id']}: {issue['issue']}")
        
        if report['velocity_issues']:
            print(f"\nVelocity Issues: {len(report['velocity_issues'])}")
            for issue in report['velocity_issues'][:5]:  # Show first 5
                print(f"  - {issue['channel_id']}: {issue['issue']} ({issue['velocity']:.2f} m/s)")
        
        print(f"\n{'='*60}")
        print(f"OVERALL ASSESSMENT: {report['summary']['recommendation'].upper()}")
        print(f"{'='*60}\n")


def main():
    """Run validation"""
    # Path to network data from ETL
    network_data_path = "/Users/subhajlimanond/dev/munbon2-backend/services/gravity-optimizer/scripts/migrations/network_data.json"
    
    # Check if data exists
    if not Path(network_data_path).exists():
        logger.error(f"Network data not found at {network_data_path}")
        logger.info("Please run port_flow_monitoring_data.py first")
        return
    
    # Run validation
    validator = GravityFlowValidator(network_data_path)
    report = validator.generate_report()
    
    # Save report
    report_path = Path(network_data_path).parent / "validation_report.json"
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    logger.info(f"Validation report saved to: {report_path}")
    
    # Print summary
    validator.print_summary(report)


if __name__ == "__main__":
    main()