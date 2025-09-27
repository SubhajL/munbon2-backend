#!/usr/bin/env python3
"""
Gate ID Standardization Utility
Ensures consistent gate notation across the Flow Monitoring service

Standard Format: M(i,j;k,l;m,n)
- No spaces after M
- Semicolons separate hierarchy levels
- Commas separate indices within a level
- No spaces around punctuation
"""

import re
from typing import Dict, List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class GateIDStandardizer:
    """Standardizes gate ID notation across the system"""
    
    # Regex patterns for different gate ID formats
    PATTERNS = [
        # Pattern 1: M (0,1; 1,0) - space after M
        r'M\s+\(([0-9,;\s]+)\)',
        # Pattern 2: M(0,1; 1,0) - standard format
        r'M\(([0-9,;\s]+)\)',
        # Pattern 3: M(0,1;1,0) - no spaces around semicolons
        r'M\(([0-9,;]+)\)',
    ]
    
    @staticmethod
    def standardize(gate_id: str) -> str:
        """
        Standardize a gate ID to the canonical format
        
        Examples:
            M (0,1; 1,0) -> M(0,1;1,0)
            M(0,1; 1,0)  -> M(0,1;1,0)
            M(0,1;1,0)   -> M(0,1;1,0)
        """
        if not gate_id:
            return gate_id
            
        # Remove all spaces
        standardized = gate_id.replace(" ", "")
        
        # Ensure proper format
        if standardized.startswith("M(") and standardized.endswith(")"):
            return standardized
        elif standardized.startswith("M") and "(" in standardized:
            # Extract the content within parentheses
            match = re.search(r'M.*\(([^)]+)\)', gate_id)
            if match:
                content = match.group(1).replace(" ", "")
                return f"M({content})"
        
        # If no match, return original (might be a different type of ID)
        return gate_id
    
    @staticmethod
    def parse_gate_id(gate_id: str) -> Optional[Dict[str, List[int]]]:
        """
        Parse a gate ID into its hierarchical components
        
        Returns:
            Dictionary with levels as keys and index lists as values
            Example: M(0,1;1,0;1,2) -> {
                'level_0': [0, 1],
                'level_1': [1, 0],
                'level_2': [1, 2]
            }
        """
        standardized = GateIDStandardizer.standardize(gate_id)
        
        # Extract content within parentheses
        match = re.match(r'M\(([^)]+)\)', standardized)
        if not match:
            return None
            
        content = match.group(1)
        levels = content.split(';')
        
        result = {}
        for i, level in enumerate(levels):
            indices = [int(idx.strip()) for idx in level.split(',') if idx.strip().isdigit()]
            if indices:
                result[f'level_{i}'] = indices
                
        return result
    
    @staticmethod
    def get_gate_hierarchy(gate_id: str) -> List[str]:
        """
        Get the hierarchical path of gates leading to this gate
        
        Example:
            M(0,1;1,1;1,2;1,0) returns:
            ['M(0,0)', 'M(0,1)', 'M(0,1;1,0)', 'M(0,1;1,1)', 
             'M(0,1;1,1;1,0)', 'M(0,1;1,1;1,2)', 'M(0,1;1,1;1,2;1,0)']
        """
        parsed = GateIDStandardizer.parse_gate_id(gate_id)
        if not parsed:
            return []
            
        hierarchy = ['M(0,0)']  # Always start from the dam
        
        # Build up the hierarchy
        levels = sorted(parsed.keys())
        current_path = []
        
        for level in levels:
            indices = parsed[level]
            if level == 'level_0':
                # First level
                if indices[0] == 0 and len(indices) > 1:
                    hierarchy.append(f"M(0,{indices[1]})")
                    current_path = [0, indices[1]]
            else:
                # Subsequent levels
                level_num = int(level.split('_')[1])
                # Add intermediate gates
                for i in range(0, len(indices), 2):
                    if i + 1 < len(indices):
                        sub_path = current_path + indices[:i+2]
                        hierarchy.append(GateIDStandardizer._build_gate_id(sub_path))
                
                current_path.extend(indices)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_hierarchy = []
        for gate in hierarchy:
            if gate not in seen:
                seen.add(gate)
                unique_hierarchy.append(gate)
                
        return unique_hierarchy
    
    @staticmethod
    def _build_gate_id(indices: List[int]) -> str:
        """Build a gate ID from a list of indices"""
        if len(indices) <= 2:
            return f"M({','.join(map(str, indices))})"
        
        # Group indices by pairs for each level
        levels = []
        for i in range(0, len(indices), 2):
            if i + 1 < len(indices):
                levels.append(f"{indices[i]},{indices[i+1]}")
            elif i < len(indices):
                levels.append(str(indices[i]))
        
        return f"M({';'.join(levels)})"
    
    @staticmethod
    def create_mapping_table() -> Dict[str, str]:
        """
        Create a mapping table for common gate variations
        Used for backward compatibility
        """
        # Common gates in the system
        common_gates = [
            "M(0,0)", "M(0,1)", "M(0,2)", "M(0,3)",
            "M(0,1;1,0)", "M(0,1;1,1)", "M(0,1;1,2)",
            "M(0,1;1,1;1,0)", "M(0,1;1,1;1,1)", "M(0,1;1,1;1,2)",
            "M(0,1;1,1;1,2;1,0)"  # FTO 337 Rai
        ]
        
        mapping = {}
        for gate in common_gates:
            # Add variations with spaces
            mapping[gate.replace("M(", "M (")] = gate
            mapping[gate.replace(";", "; ")] = gate
            mapping[gate.replace(",", ", ")] = gate
            
        return mapping


# Utility functions for direct use
def standardize_gate_id(gate_id: str) -> str:
    """Convenience function to standardize a single gate ID"""
    return GateIDStandardizer.standardize(gate_id)


def standardize_gate_list(gate_ids: List[str]) -> List[str]:
    """Standardize a list of gate IDs"""
    return [GateIDStandardizer.standardize(gid) for gid in gate_ids]


def get_zone_6_fto337_path() -> List[str]:
    """Get the standardized path to Zone 6 FTO 337 Rai"""
    return [
        "M(0,0)",           # Dam/Outlet
        "M(0,1)",           # LMC Start
        "M(0,1;1,0)",       # RMC Start/Zone 6 Entry
        "M(0,1;1,1)",       # RMC Gate 2+600
        "M(0,1;1,1;1,0)",   # 4L-RMC Start
        "M(0,1;1,1;1,1)",   # 4L-RMC Gate 0+750
        "M(0,1;1,1;1,2)",   # 4L-RMC Gate 1+850
        "M(0,1;1,1;1,2;1,0)" # FTO 337 Rai
    ]


if __name__ == "__main__":
    # Test standardization
    test_cases = [
        "M (0,1; 1,0)",
        "M(0,1; 1,0)",
        "M(0,1;1,0)",
        "M (0,1; 1,1; 1,2; 1,0)",
        "M(0,1;1,1;1,2;1,0)"
    ]
    
    print("Gate ID Standardization Tests:")
    print("-" * 50)
    for test in test_cases:
        standardized = standardize_gate_id(test)
        print(f"{test:<25} -> {standardized}")
    
    print("\nZone 6 FTO 337 Rai Path:")
    print("-" * 50)
    for i, gate in enumerate(get_zone_6_fto337_path()):
        print(f"{i+1}. {gate}")