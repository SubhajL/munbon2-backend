#!/usr/bin/env python3
"""
Gate Calibration Loader
Loads K1/K2 calibration values from the extracted SCADA data
"""

import json
import os
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class GateCalibrationData:
    """Gate calibration data"""
    gate_id: str
    k1: float
    k2: float
    source: str  # "field_measurement" or "default"
    confidence: float
    shape: Optional[str] = None
    width_m: Optional[float] = None
    height_m: Optional[float] = None
    
class GateCalibrationLoader:
    """Loads and provides gate K1/K2 calibration values"""
    
    def __init__(self, calibration_file: Optional[str] = None):
        """Initialize with calibration file path"""
        if calibration_file is None:
            # Default path
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            calibration_file = os.path.join(base_dir, 'config', 'gate_calibrations.json')
            
        self.calibration_file = calibration_file
        self.calibrations = {}
        self.gate_id_mapping = {}
        self._load_calibrations()
        self._setup_gate_id_mapping()
        
    def _load_calibrations(self):
        """Load calibrations from JSON file"""
        try:
            with open(self.calibration_file, 'r') as f:
                data = json.load(f)
                
            logger.info(f"Loaded calibrations for {data['metadata']['total_gates']} gates")
            logger.info(f"Gates with K1/K2: {data['metadata']['gates_with_k1_k2']}")
            
            self.calibrations = data['gates']
            
        except FileNotFoundError:
            logger.warning(f"Calibration file not found: {self.calibration_file}")
            self.calibrations = {}
        except Exception as e:
            logger.error(f"Error loading calibrations: {e}")
            self.calibrations = {}
            
    def _setup_gate_id_mapping(self):
        """Setup mapping between different gate ID formats"""
        # Map standardized IDs to Excel IDs
        self.gate_id_mapping = {
            # Remove spaces for standardization
            "M(0,0)": "M(0,0)",
            "M(0,1)": "M(0,1)", 
            "M(0,2)": "M(0,2)",
            "M(0,3)": "M(0,3)",
            "M(0,4)": "M(0,4)",
            "M(0,5)": "M(0,5)",
            "M(0,6)": "M(0,6)",
            "M(0,7)": "M(0,7)",
            "M(0,8)": "M(0,8)",
            "M(0,9)": "M(0,9)",
            "M(0,10)": "M(0,10)",
            "M(0,11)": "M(0,11)",
            "M(0,12)": "M(0,12)",
            # Zone 6 gates - note the space in Excel format
            "M(0,1;1,0)": "M (0,1; 1,0)",
            "M(0,1;1,1)": "M (0,1; 1,1)",
            "M(0,1;1,2)": "M (0,1; 1,2)",
            "M(0,1;1,3)": "M (0,1; 1,3)",
            "M(0,1;1,4)": "M (0,1; 1,4)",
            "M(0,1;1,0;1,0)": "M(0,1; 1,0; 1,0)",
            "M(0,1;1,1;1,0)": "M(0,1; 1,1; 1,0)",
            "M(0,1;1,1;1,1)": "M(0,1; 1,1; 1,1)",
            "M(0,1;1,1;1,2)": "M(0,1; 1,1; 1,2)",
            "M(0,1;1,1;1,3)": "M(0,1; 1,1; 1,3)",
            "M(0,1;1,1;1,4)": "M(0,1; 1,1; 1,4)",
            "M(0,1;1,1;1,2;1,0)": "M(0,1; 1,1; 1,2; 1,0)",
            # Zone 3 gates
            "M(0,3;1,0)": "M (0,3; 1,0)",
            "M(0,3;1,1)": "M (0,3; 1,1)",
            # Zone 4 gates
            "M(0,12;1,0)": "M (0,12; 1,0)",
            "M(0,12;1,2)": "M (0,12; 1,2)",
            # Add more mappings as needed
        }
        
    def get_calibration(self, gate_id: str) -> Optional[GateCalibrationData]:
        """Get calibration data for a gate"""
        # Try standardized ID first
        excel_id = self.gate_id_mapping.get(gate_id, gate_id)
        
        # Check if we have data for this gate
        if excel_id in self.calibrations:
            gate_data = self.calibrations[excel_id]
            
            if gate_data.get('has_calibration', False):
                # Use actual K1/K2 from Excel
                return GateCalibrationData(
                    gate_id=gate_id,
                    k1=gate_data['k1'],
                    k2=gate_data['k2'],
                    source="field_measurement",
                    confidence=0.95,  # High confidence for measured values
                    shape=gate_data.get('shape'),
                    width_m=gate_data.get('width_m'),
                    height_m=gate_data.get('height_m')
                )
            else:
                # No K1/K2, use defaults based on gate properties
                return self._get_default_calibration(gate_id, gate_data)
        
        # No data at all, use generic defaults
        return self._get_generic_default(gate_id)
        
    def _get_default_calibration(self, gate_id: str, gate_data: dict) -> GateCalibrationData:
        """Get default calibration based on gate size and shape"""
        shape = gate_data.get('shape', 'rectangular')
        
        if shape == 'circular':
            height = gate_data.get('height_m', 1.0)
            if height >= 1.0:
                k1, k2 = 1.40, -3.50  # Large circular
            elif height >= 0.6:
                k1, k2 = 1.30, -3.00  # Medium circular
            else:
                k1, k2 = 1.20, -2.50  # Small circular
        else:  # rectangular
            width = gate_data.get('width_m', 2.0)
            if width >= 3.0:
                k1, k2 = 1.20, -1.30  # Large rectangular
            elif width >= 1.5:
                k1, k2 = 1.10, -1.80  # Medium rectangular
            else:
                k1, k2 = 0.95, -2.00  # Small rectangular
                
        return GateCalibrationData(
            gate_id=gate_id,
            k1=k1,
            k2=k2,
            source="default_by_size",
            confidence=0.80,
            shape=shape,
            width_m=gate_data.get('width_m'),
            height_m=gate_data.get('height_m')
        )
        
    def _get_generic_default(self, gate_id: str) -> GateCalibrationData:
        """Get generic default calibration when no data available"""
        logger.warning(f"No calibration data for gate {gate_id}, using generic default")
        
        return GateCalibrationData(
            gate_id=gate_id,
            k1=1.10,
            k2=-1.80,
            source="generic_default",
            confidence=0.60
        )
        
    def get_all_calibrated_gates(self) -> Dict[str, Tuple[float, float]]:
        """Get all gates that have actual K1/K2 calibrations"""
        calibrated = {}
        
        for excel_id, gate_data in self.calibrations.items():
            if gate_data.get('has_calibration', False):
                # Find standardized ID
                std_id = excel_id
                for std, excel in self.gate_id_mapping.items():
                    if excel == excel_id:
                        std_id = std
                        break
                        
                calibrated[std_id] = (gate_data['k1'], gate_data['k2'])
                
        return calibrated
        
    def print_calibration_summary(self):
        """Print summary of calibrations"""
        print("\n=== Gate Calibration Summary ===")
        
        calibrated_gates = self.get_all_calibrated_gates()
        print(f"\nGates with field-measured K1/K2: {len(calibrated_gates)}")
        
        for gate_id, (k1, k2) in sorted(calibrated_gates.items()):
            print(f"  {gate_id}: K1={k1:.4f}, K2={k2:.4f}")
            
        print(f"\nTotal gates in system: {len(self.calibrations)}")
        print(f"Gates using defaults: {len(self.calibrations) - len(calibrated_gates)}")


# Example usage
if __name__ == "__main__":
    loader = GateCalibrationLoader()
    loader.print_calibration_summary()
    
    # Test Zone 6 gates
    print("\n=== Zone 6 Path Calibrations ===")
    zone6_gates = [
        "M(0,0)",
        "M(0,1)",
        "M(0,1;1,0)",
        "M(0,1;1,1)",
        "M(0,1;1,1;1,0)",
        "M(0,1;1,1;1,1)",
        "M(0,1;1,1;1,2)",
        "M(0,1;1,1;1,2;1,0)"
    ]
    
    for gate_id in zone6_gates:
        cal = loader.get_calibration(gate_id)
        if cal:
            print(f"{gate_id}: K1={cal.k1:.4f}, K2={cal.k2:.4f} ({cal.source})")
        else:
            print(f"{gate_id}: No calibration data")