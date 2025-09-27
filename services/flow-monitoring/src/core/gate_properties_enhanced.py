#!/usr/bin/env python3
"""
Enhanced Gate Properties Module with Circular Gate Support
Incorporates SCADA Excel specifications including circular gates and drop structures
"""

from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
import numpy as np
import pandas as pd
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class GateShape(Enum):
    """Gate opening shape types"""
    RECTANGULAR = "rectangular"
    CIRCULAR = "circular"
    

class GateControlType(Enum):
    """Gate control types"""
    AUTOMATIC = "automatic"      # Can move to L1, L2, L3, L4 positions
    MANUAL = "manual"           # Requires job order form
    

class FlowRegime(Enum):
    """Flow conditions through gate"""
    FREE_FLOW = "free_flow"
    SUBMERGED_FLOW = "submerged_flow"
    CRITICAL_FLOW = "critical_flow"     # At drop structures
    WEIR_FLOW = "weir_flow"
    NO_FLOW = "no_flow"


@dataclass
class CalibrationCoefficients:
    """Gate-specific calibration coefficients"""
    k1: float
    k2: float
    confidence: float  # R² value
    source: str = "field_measurement"  # or "default"
    last_updated: Optional[datetime] = None
    

@dataclass
class DiscreteControlLevels:
    """Discrete opening positions for automatic gates"""
    l1: float = 0.0  # Closed position
    l2: Optional[float] = None
    l3: Optional[float] = None
    l4: Optional[float] = None
    l5: Optional[float] = None  # Only for M(0,2)
    
    def get_available_openings(self) -> List[float]:
        """Get list of available opening positions"""
        openings = [self.l1]
        for level in [self.l2, self.l3, self.l4, self.l5]:
            if level is not None:
                openings.append(level)
        return sorted(openings)
    
    def get_nearest_level(self, target_opening: float) -> float:
        """Find nearest available discrete level"""
        openings = self.get_available_openings()
        if not openings:
            return 0.0
        
        # Find nearest level
        distances = [abs(target_opening - level) for level in openings]
        nearest_idx = np.argmin(distances)
        return openings[nearest_idx]


@dataclass
class GatePropertiesEnhanced:
    """Enhanced gate properties with circular gate support"""
    gate_id: str
    shape: GateShape
    control_type: GateControlType
    
    # Dimensions
    width_m: Optional[float] = None  # For rectangular gates
    diameter_m: Optional[float] = None  # For circular gates
    height_m: float = 0.0  # Max height for rectangular, equals diameter for circular
    
    # Hydraulic properties
    sill_elevation_m: float = 0.0
    drop_height_m: float = 0.0
    max_flow_m3s: Optional[float] = None
    
    # Calibration
    calibration: Optional[CalibrationCoefficients] = None
    
    # Control levels (for automatic gates)
    control_levels: Optional[DiscreteControlLevels] = None
    
    # Location
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    zone: Optional[int] = None
    
    def __post_init__(self):
        """Validate and set derived properties"""
        if self.shape == GateShape.CIRCULAR:
            if self.diameter_m is None and self.height_m > 0:
                self.diameter_m = self.height_m
            self.width_m = None  # Ensure width is None for circular
        else:  # RECTANGULAR
            self.diameter_m = None  # Ensure diameter is None for rectangular
            
    @property
    def area_full(self) -> float:
        """Full open area of gate"""
        if self.shape == GateShape.CIRCULAR:
            return np.pi * (self.diameter_m / 2) ** 2
        else:
            return self.width_m * self.height_m
            
    @property
    def has_drop_structure(self) -> bool:
        """Check if gate has drop structure"""
        return self.drop_height_m > 0
        
    @property
    def is_automatic(self) -> bool:
        """Check if gate is automatic control"""
        return self.control_type == GateControlType.AUTOMATIC
        
    def get_flow_area(self, opening_m: float) -> float:
        """Calculate flow area for given opening"""
        if opening_m <= 0:
            return 0.0
            
        if self.shape == GateShape.CIRCULAR:
            # Circular gate with vertical slide
            R = self.diameter_m / 2
            if opening_m >= self.diameter_m:
                return self.area_full
                
            # Calculate segment area
            h = opening_m
            if h > R:  # More than half open
                # Calculate area of circle minus top segment
                h_top = self.diameter_m - h
                theta_top = 2 * np.arccos((R - h_top) / R)
                area_top = R**2 * (theta_top - np.sin(theta_top)) / 2
                return self.area_full - area_top
            else:  # Less than half open
                theta = 2 * np.arccos((R - h) / R)
                return R**2 * (theta - np.sin(theta)) / 2
        else:
            # Rectangular gate
            return self.width_m * min(opening_m, self.height_m)
            
    def get_wetted_perimeter(self, opening_m: float) -> float:
        """Calculate wetted perimeter for given opening"""
        if opening_m <= 0:
            return 0.0
            
        if self.shape == GateShape.CIRCULAR:
            R = self.diameter_m / 2
            if opening_m >= self.diameter_m:
                return np.pi * self.diameter_m
                
            # Calculate arc length
            h = min(opening_m, self.diameter_m)
            theta = 2 * np.arccos((R - h) / R)
            return R * theta
        else:
            # Rectangular gate
            h = min(opening_m, self.height_m)
            return self.width_m + 2 * h


class GatePropertiesManager:
    """Manages gate properties loaded from SCADA Excel"""
    
    def __init__(self):
        self.gates: Dict[str, GatePropertiesEnhanced] = {}
        self.default_calibrations = {
            # Rectangular gates
            ("rectangular", "large"): CalibrationCoefficients(1.20, -1.30, 0.95, "default"),
            ("rectangular", "medium"): CalibrationCoefficients(1.10, -1.80, 0.93, "default"),
            ("rectangular", "small"): CalibrationCoefficients(0.95, -2.00, 0.90, "default"),
            # Circular gates
            ("circular", "large"): CalibrationCoefficients(1.40, -3.50, 0.92, "default"),
            ("circular", "medium"): CalibrationCoefficients(1.30, -3.00, 0.90, "default"),
            ("circular", "small"): CalibrationCoefficients(1.20, -2.50, 0.88, "default"),
        }
        
    def load_from_excel(self, excel_path: str) -> None:
        """Load gate properties from SCADA Excel file"""
        try:
            df = pd.read_excel(excel_path)
            logger.info(f"Loading {len(df)} gates from Excel")
            
            for idx, row in df.iterrows():
                if pd.isna(row.get('Gate Valve')):
                    continue
                    
                gate_id = str(row['Gate Valve'])
                
                # Determine shape
                width = row.get('width (m)')
                shape = GateShape.CIRCULAR if width == 'C' else GateShape.RECTANGULAR
                
                # Determine control type
                l1 = row.get('l1 (m)')
                control_type = GateControlType.AUTOMATIC if l1 == 0 else GateControlType.MANUAL
                
                # Create gate properties
                gate = GatePropertiesEnhanced(
                    gate_id=gate_id,
                    shape=shape,
                    control_type=control_type,
                    height_m=float(row.get('height (m)', 0)) if pd.notna(row.get('height (m)')) else 0,
                    sill_elevation_m=float(row.get('sill_level (m)', 0)) if pd.notna(row.get('sill_level (m)')) else 0,
                    drop_height_m=float(row.get('drop_level (m)', 0)) if pd.notna(row.get('drop_level (m)')) else 0,
                    max_flow_m3s=float(row.get('q_max (m^3/s)')) if pd.notna(row.get('q_max (m^3/s)')) else None,
                    latitude=float(row.get('Latitude')) if pd.notna(row.get('Latitude')) else None,
                    longitude=float(row.get('Longitude')) if pd.notna(row.get('Longitude')) else None,
                    zone=int(row.get('Zone')) if pd.notna(row.get('Zone')) else None
                )
                
                # Set width for rectangular gates
                if shape == GateShape.RECTANGULAR and pd.notna(width) and width != 'C':
                    gate.width_m = float(width)
                
                # Load calibration if available
                if pd.notna(row.get('k1')) and pd.notna(row.get('k2')):
                    gate.calibration = CalibrationCoefficients(
                        k1=float(row['k1']),
                        k2=float(row['k2']),
                        confidence=float(row.get('r2', 0.95)),
                        source="field_measurement"
                    )
                else:
                    # Assign default calibration
                    gate.calibration = self._get_default_calibration(gate)
                
                # Load control levels for automatic gates
                if control_type == GateControlType.AUTOMATIC:
                    gate.control_levels = DiscreteControlLevels(
                        l1=0.0,  # Always 0 for automatic gates
                        l2=float(row['l2 (m)']) if pd.notna(row.get('l2 (m)')) else None,
                        l3=float(row['l3 (m)']) if pd.notna(row.get('l3 (m)')) else None,
                        l4=float(row['l4 (m)']) if pd.notna(row.get('l4 (m)')) else None,
                        l5=float(row['l5 (m)']) if pd.notna(row.get('l5 (m)')) and gate_id == 'M(0,2)' else None
                    )
                
                self.gates[gate_id] = gate
                
            logger.info(f"Loaded {len(self.gates)} gates successfully")
            self._log_summary()
            
        except Exception as e:
            logger.error(f"Error loading gates from Excel: {e}")
            raise
            
    def _get_default_calibration(self, gate: GatePropertiesEnhanced) -> CalibrationCoefficients:
        """Get default calibration based on gate type and size"""
        # Determine size category
        if gate.shape == GateShape.CIRCULAR:
            size = "large" if gate.diameter_m >= 1.0 else "medium" if gate.diameter_m >= 0.6 else "small"
        else:
            size = "large" if gate.width_m >= 3.0 else "medium" if gate.width_m >= 1.5 else "small"
            
        key = (gate.shape.value, size)
        return self.default_calibrations.get(key, CalibrationCoefficients(1.0, -1.5, 0.9, "default"))
        
    def _log_summary(self) -> None:
        """Log summary of loaded gates"""
        automatic_gates = [g for g in self.gates.values() if g.is_automatic]
        manual_gates = [g for g in self.gates.values() if not g.is_automatic]
        circular_gates = [g for g in self.gates.values() if g.shape == GateShape.CIRCULAR]
        drop_gates = [g for g in self.gates.values() if g.has_drop_structure]
        
        logger.info(f"Gate Summary:")
        logger.info(f"  Total gates: {len(self.gates)}")
        logger.info(f"  Automatic: {len(automatic_gates)}")
        logger.info(f"  Manual: {len(manual_gates)}")
        logger.info(f"  Circular: {len(circular_gates)}")
        logger.info(f"  With drops: {len(drop_gates)}")
        
    def get_gate(self, gate_id: str) -> Optional[GatePropertiesEnhanced]:
        """Get gate properties by ID"""
        return self.gates.get(gate_id)
        
    def get_automatic_gates(self) -> List[GatePropertiesEnhanced]:
        """Get all automatic control gates"""
        return [g for g in self.gates.values() if g.is_automatic]
        
    def get_manual_gates(self) -> List[GatePropertiesEnhanced]:
        """Get all manual gates requiring job orders"""
        return [g for g in self.gates.values() if not g.is_automatic]
        
    def get_gates_by_zone(self, zone: int) -> List[GatePropertiesEnhanced]:
        """Get all gates in a specific zone"""
        return [g for g in self.gates.values() if g.zone == zone]