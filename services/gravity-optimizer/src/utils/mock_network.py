"""Mock network topology for testing and development"""

from typing import List
from ..models.channel import (
    NetworkTopology, HydraulicNode, Channel, ChannelSection,
    Gate, GateType, ChannelType
)


def create_mock_network() -> NetworkTopology:
    """Create a mock network topology for testing"""
    
    # Create nodes
    nodes = [
        HydraulicNode(
            node_id="source",
            name="Main Source",
            elevation=221.0,
            connected_channels=["main_channel"],
            gates=["source_gate"],
            water_demand=0,
            priority=1
        )
    ]
    
    # Add zone nodes
    for i in range(1, 7):
        zone_node = HydraulicNode(
            node_id=f"zone_{i}_node",
            name=f"Zone {i} Distribution Node",
            elevation=220.0 - i * 1.0,  # Decreasing elevation
            connected_channels=[f"lateral_{i}"],
            gates=[f"gate_{j}" for j in range((i-1)*3+1, i*3+1)],
            water_demand=20.0,  # 20 m³/s per zone
            priority=1 if i <= 3 else 2
        )
        nodes.append(zone_node)
    
    # Create channels
    channels = []
    
    # Main channel
    main_sections = []
    for i in range(5):
        section = ChannelSection(
            section_id=f"main_sec_{i}",
            channel_id="main_channel",
            start_point={"lat": 14.0 + i*0.01, "lon": 101.0},
            end_point={"lat": 14.0 + (i+1)*0.01, "lon": 101.0},
            start_elevation=221.0 - i*0.5,
            end_elevation=221.0 - (i+1)*0.5,
            length=2000.0,
            bed_width=20.0,
            side_slope=1.5,
            manning_n=0.025,
            max_depth=3.0
        )
        main_sections.append(section)
    
    main_channel = Channel(
        channel_id="main_channel",
        name="Main Canal",
        channel_type=ChannelType.MAIN,
        sections=main_sections,
        upstream_gate_id="source_gate",
        downstream_gates=["gate_1", "gate_4", "gate_7", "gate_10", "gate_13", "gate_16"],
        total_length=10000.0,
        avg_bed_slope=0.00015,
        capacity=150.0
    )
    channels.append(main_channel)
    
    # Lateral channels for each zone
    for i in range(1, 7):
        lateral_sections = []
        for j in range(3):
            section = ChannelSection(
                section_id=f"lateral_{i}_sec_{j}",
                channel_id=f"lateral_{i}",
                start_point={"lat": 14.0 + i*0.01, "lon": 101.0 + j*0.01},
                end_point={"lat": 14.0 + i*0.01, "lon": 101.0 + (j+1)*0.01},
                start_elevation=220.0 - i*1.0 - j*0.2,
                end_elevation=220.0 - i*1.0 - (j+1)*0.2,
                length=1500.0,
                bed_width=10.0,
                side_slope=1.5,
                manning_n=0.03,
                max_depth=2.0
            )
            lateral_sections.append(section)
        
        lateral = Channel(
            channel_id=f"lateral_{i}",
            name=f"Lateral Canal Zone {i}",
            channel_type=ChannelType.LATERAL,
            sections=lateral_sections,
            upstream_gate_id=f"gate_{(i-1)*3+1}",
            downstream_gates=[f"gate_{(i-1)*3+j}" for j in range(2, 4)],
            total_length=4500.0,
            avg_bed_slope=0.00013,
            capacity=30.0
        )
        channels.append(lateral)
    
    # Create gates
    gates = []
    
    # Source gate
    source_gate = Gate(
        gate_id="source_gate",
        gate_type=GateType.MANUAL,
        location={"lat": 14.0, "lon": 101.0},
        elevation=221.0,
        max_opening=3.0,
        current_opening=0.5,
        upstream_channel_id=None,
        downstream_channel_id="main_channel"
    )
    gates.append(source_gate)
    
    # Automated gates (20 total)
    gate_count = 0
    for i in range(1, 7):
        for j in range(1, 4):
            if gate_count < 20:
                gate = Gate(
                    gate_id=f"gate_{gate_count+1}",
                    gate_type=GateType.AUTOMATED,
                    location={"lat": 14.0 + i*0.01, "lon": 101.0 + j*0.005},
                    elevation=220.0 - i*1.0,
                    max_opening=2.0,
                    current_opening=0.0,
                    upstream_channel_id="main_channel" if j == 1 else f"lateral_{i}",
                    downstream_channel_id=f"lateral_{i}"
                )
                gates.append(gate)
                gate_count += 1
    
    # Add manual gates for the remaining
    for i in range(21, 31):
        gate = Gate(
            gate_id=f"gate_{i}",
            gate_type=GateType.MANUAL,
            location={"lat": 14.0 + (i%6)*0.01, "lon": 101.0 + (i//6)*0.01},
            elevation=218.0,
            max_opening=1.5,
            current_opening=0.3,
            upstream_channel_id=f"lateral_{(i-21)//5+1}",
            downstream_channel_id=None
        )
        gates.append(gate)
    
    return NetworkTopology(
        nodes=nodes,
        channels=channels,
        gates=gates,
        source_node_id="source"
    )