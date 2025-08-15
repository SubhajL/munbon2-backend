from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from enum import Enum


class ChannelType(str, Enum):
    MAIN = "main"
    LATERAL = "lateral"
    SUBLATERAL = "sublateral"
    FIELD = "field"


class GateType(str, Enum):
    AUTOMATED = "automated"
    MANUAL = "manual"


class Gate(BaseModel):
    gate_id: str
    gate_type: GateType
    location: Dict[str, float] = Field(..., description="Location coordinates {lat, lon}")
    elevation: float = Field(..., description="Gate sill elevation in MSL meters")
    max_opening: float = Field(1.0, description="Maximum gate opening in meters")
    current_opening: float = Field(0.0, description="Current gate opening (0-1)")
    upstream_channel_id: Optional[str] = None
    downstream_channel_id: Optional[str] = None


class ChannelSection(BaseModel):
    section_id: str
    channel_id: str
    start_point: Dict[str, float] = Field(..., description="Start coordinates {lat, lon}")
    end_point: Dict[str, float] = Field(..., description="End coordinates {lat, lon}")
    start_elevation: float = Field(..., description="Bed elevation at start in MSL meters")
    end_elevation: float = Field(..., description="Bed elevation at end in MSL meters")
    length: float = Field(..., description="Section length in meters")
    bed_width: float = Field(..., description="Bottom width in meters")
    side_slope: float = Field(1.5, description="Side slope (H:V)")
    manning_n: float = Field(0.025, description="Manning's roughness coefficient")
    max_depth: float = Field(..., description="Maximum channel depth in meters")


class Channel(BaseModel):
    channel_id: str
    name: str
    channel_type: ChannelType
    sections: List[ChannelSection] = []
    upstream_gate_id: Optional[str] = None
    downstream_gates: List[str] = []
    total_length: float = Field(0.0, description="Total channel length in meters")
    avg_bed_slope: float = Field(..., description="Average bed slope")
    capacity: float = Field(..., description="Design capacity in m³/s")


class FlowCondition(BaseModel):
    channel_id: str
    section_id: Optional[str] = None
    flow_rate: float = Field(..., description="Flow rate in m³/s")
    flow_depth: float = Field(..., description="Flow depth in meters")
    flow_velocity: float = Field(..., description="Average velocity in m/s")
    froude_number: float = Field(..., description="Froude number")
    water_surface_elevation: float = Field(..., description="Water surface elevation in MSL meters")
    energy_head: float = Field(..., description="Total energy head in meters")
    
    @property
    def is_subcritical(self) -> bool:
        return self.froude_number < 1.0
    
    @property
    def is_supercritical(self) -> bool:
        return self.froude_number > 1.0


class HydraulicNode(BaseModel):
    node_id: str
    name: str
    elevation: float
    connected_channels: List[str] = []
    gates: List[str] = []
    water_demand: float = Field(0.0, description="Water demand at node in m³/s")
    priority: int = Field(1, description="Priority level (1=highest)")


class NetworkTopology(BaseModel):
    nodes: List[HydraulicNode]
    channels: List[Channel]
    gates: List[Gate]
    source_node_id: str
    
    def get_downstream_nodes(self, node_id: str) -> List[str]:
        """Get all downstream nodes from a given node"""
        downstream = []
        node = next((n for n in self.nodes if n.node_id == node_id), None)
        if node:
            for channel_id in node.connected_channels:
                channel = next((c for c in self.channels if c.channel_id == channel_id), None)
                if channel and channel.upstream_gate_id in node.gates:
                    # Find downstream node
                    for other_node in self.nodes:
                        if any(g in channel.downstream_gates for g in other_node.gates):
                            downstream.append(other_node.node_id)
        return downstream