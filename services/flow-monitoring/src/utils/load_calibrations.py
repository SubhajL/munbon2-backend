#!/usr/bin/env python3
"""
Utility to load gate calibrations from JSON file
"""

import json
import logging
from typing import Dict, List
from datetime import datetime
from pathlib import Path

from ..core.calibrated_gate_hydraulics import (
    CalibratedGateHydraulics, 
    GateCalibration, 
    GateProperties,
    GateType
)

logger = logging.getLogger(__name__)


def load_calibrations_from_json(json_file: str, hydraulics: CalibratedGateHydraulics) -> Dict[str, any]:
    """
    Load gate calibrations and properties from JSON file
    
    Args:
        json_file: Path to JSON file containing calibrations
        hydraulics: CalibratedGateHydraulics instance to populate
        
    Returns:
        Dictionary with loading statistics
    """
    
    # Read JSON file
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    calibrations_loaded = 0
    properties_loaded = 0
    errors = []
    
    # Load calibrations
    for cal_data in data.get('calibrations', []):
        try:
            # Parse calibration date if provided
            cal_date = None
            if 'calibration_date' in cal_data:
                try:
                    cal_date = datetime.fromisoformat(cal_data['calibration_date'])
                except:
                    pass
            
            # Create calibration object
            calibration = GateCalibration(
                gate_id=cal_data['gate_id'],
                K1=float(cal_data['K1']),
                K2=float(cal_data['K2']),
                calibration_date=cal_date,
                calibration_method=cal_data.get('calibration_method', 'field_measurement'),
                flow_range_tested=tuple(cal_data.get('flow_range_tested', [0.0, 0.0])),
                confidence=float(cal_data.get('confidence', 0.9)),
                notes=cal_data.get('notes', '')
            )
            
            # Add to hydraulics system
            hydraulics.add_gate_calibration(calibration)
            calibrations_loaded += 1
            
        except Exception as e:
            error_msg = f"Error loading calibration for {cal_data.get('gate_id', 'unknown')}: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
    
    # Load gate properties
    for prop_data in data.get('gate_properties', []):
        try:
            # Determine gate type
            gate_type_str = prop_data.get('gate_type', 'slide_gate')
            gate_type = GateType.SLIDE_GATE  # Default
            
            # Map string to enum
            type_mapping = {
                'slide_gate': GateType.SLIDE_GATE,
                'sluice_gate': GateType.SLUICE_GATE,
                'radial_gate': GateType.RADIAL_GATE,
                'butterfly_valve': GateType.BUTTERFLY_VALVE,
                'check_gate': GateType.CHECK_GATE,
                'weir_gate': GateType.WEIR_GATE
            }
            
            if gate_type_str in type_mapping:
                gate_type = type_mapping[gate_type_str]
            
            # Create gate properties object
            properties = GateProperties(
                gate_id=prop_data['gate_id'],
                gate_type=gate_type,
                width_m=float(prop_data.get('width_m', 3.0)),
                height_m=float(prop_data.get('height_m', 2.5)),
                sill_elevation_m=float(prop_data.get('sill_elevation_m', 0.0)),
                has_drop_structure=bool(prop_data.get('has_drop_structure', False)),
                drop_height_m=float(prop_data.get('drop_height_m', 0.0)),
                drop_type=prop_data.get('drop_type', 'none'),
                max_opening_m=float(prop_data.get('max_opening_m', 0.0)) or None,
                min_opening_m=float(prop_data.get('min_opening_m', 0.0))
            )
            
            # Add to hydraulics system
            hydraulics.add_gate_properties(properties)
            properties_loaded += 1
            
        except Exception as e:
            error_msg = f"Error loading properties for {prop_data.get('gate_id', 'unknown')}: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
    
    # Return statistics
    return {
        'calibrations_loaded': calibrations_loaded,
        'properties_loaded': properties_loaded,
        'errors': errors,
        'metadata': data.get('metadata', {}),
        'success': len(errors) == 0
    }


def load_calibrations_from_directory(directory: str, hydraulics: CalibratedGateHydraulics) -> Dict[str, any]:
    """
    Load all calibration JSON files from a directory
    
    Args:
        directory: Path to directory containing calibration JSON files
        hydraulics: CalibratedGateHydraulics instance to populate
        
    Returns:
        Dictionary with combined loading statistics
    """
    
    dir_path = Path(directory)
    if not dir_path.exists():
        return {
            'error': f"Directory {directory} does not exist",
            'success': False
        }
    
    total_calibrations = 0
    total_properties = 0
    all_errors = []
    files_processed = 0
    
    # Process all JSON files in directory
    for json_file in dir_path.glob('*.json'):
        logger.info(f"Loading calibrations from {json_file}")
        
        try:
            result = load_calibrations_from_json(str(json_file), hydraulics)
            total_calibrations += result['calibrations_loaded']
            total_properties += result['properties_loaded']
            all_errors.extend(result['errors'])
            files_processed += 1
            
        except Exception as e:
            error_msg = f"Failed to process {json_file}: {str(e)}"
            logger.error(error_msg)
            all_errors.append(error_msg)
    
    return {
        'files_processed': files_processed,
        'calibrations_loaded': total_calibrations,
        'properties_loaded': total_properties,
        'errors': all_errors,
        'success': len(all_errors) == 0
    }


# Example usage in main application startup
def initialize_calibrations(hydraulics: CalibratedGateHydraulics, config_dir: str = "config/calibrations"):
    """
    Initialize calibrations during application startup
    """
    logger.info(f"Initializing gate calibrations from {config_dir}")
    
    # Try to load from directory
    result = load_calibrations_from_directory(config_dir, hydraulics)
    
    if result['success']:
        logger.info(f"Successfully loaded {result['calibrations_loaded']} calibrations "
                   f"and {result['properties_loaded']} gate properties")
    else:
        logger.warning(f"Calibration loading completed with {len(result['errors'])} errors")
        for error in result['errors'][:5]:  # Show first 5 errors
            logger.warning(f"  - {error}")
    
    return result