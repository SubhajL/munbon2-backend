"""
Centralized Mock Data Management
Provides consistent mock data across all service endpoints
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, date, timedelta
import random
import asyncio
from collections import defaultdict
import json

class MockDataManager:
    """Centralized mock data management for all services"""
    
    def __init__(self):
        self.version = "1.0"
        self.last_reset = datetime.utcnow()
        
        # Core data structures
        self.sections = {}
        self.plots = {}
        self.water_levels = {}
        self.demands = {}
        self.gates = {}
        self.schedules = {}
        self.sensor_readings = defaultdict(list)
        self.weather_data = {}
        self.awd_status = {}
        
        # Initialize with sample data
        self._initialize_sample_data()
    
    async def initialize(self):
        """Async initialization if needed"""
        # Could load from files, etc.
        pass
    
    async def reset(self):
        """Reset all data to initial state"""
        self.__init__()
        self.last_reset = datetime.utcnow()
    
    def _initialize_sample_data(self):
        """Initialize with realistic sample data"""
        self._create_sections()
        self._create_plots()
        self._create_gates()
        self._create_water_levels()
        self._create_weather_data()
        self._create_awd_status()
    
    def _create_sections(self):
        """Create sample sections"""
        zones = [2, 3, 5, 6, 7, 8]
        
        for zone in zones:
            for section in ['A', 'B', 'C', 'D']:
                section_id = f"Zone_{zone}_Section_{section}"
                self.sections[section_id] = {
                    "section_id": section_id,
                    "zone": zone,
                    "area_hectares": random.uniform(100, 200),
                    "area_rai": random.uniform(625, 1250),
                    "crop_type": "rice" if zone in [2, 3] else "sugarcane",
                    "soil_type": random.choice(["clay", "loam", "sandy_loam"]),
                    "elevation_m": 220 - (zone * 0.5),
                    "delivery_gate": f"M(0,{2 if zone in [2,3] else 5})->Zone_{zone}",
                    "created_at": datetime.utcnow().isoformat()
                }
    
    def _create_plots(self):
        """Create sample plots within sections"""
        for section_id, section in self.sections.items():
            zone = section['zone']
            section_letter = section_id.split('_')[-1]
            
            for plot_num in range(1, 6):  # 5 plots per section
                plot_id = f"Z{zone}S{section_letter}P{plot_num}"
                self.plots[plot_id] = {
                    "plot_id": plot_id,
                    "section_id": section_id,
                    "zone": zone,
                    "plot_number": plot_num,
                    "area_rai": random.uniform(15, 30),
                    "crop_type": section['crop_type'],
                    "planting_date": (datetime.now() - timedelta(days=random.randint(20, 60))).date().isoformat(),
                    "expected_harvest_date": (datetime.now() + timedelta(days=random.randint(60, 120))).date().isoformat(),
                    "farmer_id": f"F{zone:02d}{section_letter}{plot_num:02d}",
                    "status": "active",
                    "elevation_m": section['elevation_m'] + random.uniform(-0.5, 0.5)
                }
    
    def _create_gates(self):
        """Create sample gates"""
        gate_configs = [
            {"id": "Source->M(0,0)", "type": "automated", "width_m": 3.0},
            {"id": "M(0,0)->M(0,2)", "type": "manual", "width_m": 2.5},
            {"id": "M(0,2)->Zone_2", "type": "automated", "width_m": 2.0},
            {"id": "M(0,2)->Zone_3", "type": "automated", "width_m": 2.0},
            {"id": "M(0,0)->M(0,5)", "type": "manual", "width_m": 2.5},
            {"id": "M(0,5)->Zone_5", "type": "automated", "width_m": 1.8},
            {"id": "M(0,5)->Zone_6", "type": "automated", "width_m": 1.8},
        ]
        
        for config in gate_configs:
            gate_id = config["id"]
            self.gates[gate_id] = {
                "gate_id": gate_id,
                "type": config["type"],
                "state": random.choice(["open", "partial", "closed"]),
                "opening_m": random.uniform(0.5, 2.0),
                "flow_m3s": random.uniform(1.0, 5.0),
                "mode": "auto" if config["type"] == "automated" else "manual",
                "width_m": config["width_m"],
                "calibration_k1": 0.61,
                "calibration_k2": -0.12,
                "last_updated": datetime.utcnow().isoformat()
            }
    
    def _create_water_levels(self):
        """Create sample water level data"""
        # Current water levels by section
        for section_id in self.sections:
            base_level = random.uniform(1.8, 2.5)
            self.water_levels[section_id] = {
                "section_id": section_id,
                "current_level_m": base_level,
                "avg_level_7d": base_level + random.uniform(-0.2, 0.2),
                "trend": random.choice(["rising", "falling", "stable"]),
                "last_reading": datetime.utcnow().isoformat(),
                "data_source": random.choice(["sensor", "manual", "combined"]),
                "confidence_score": random.uniform(0.7, 1.0),
                "thresholds": {
                    "critical_low": 0.5,
                    "warning_low": 1.0,
                    "optimal": 2.0,
                    "warning_high": 3.0,
                    "critical_high": 3.5
                }
            }
            
            # Historical readings for past 7 days
            for days_ago in range(7):
                reading_date = datetime.now() - timedelta(days=days_ago)
                variation = random.uniform(-0.3, 0.3)
                
                self.sensor_readings[section_id].append({
                    "sensor_id": f"WL-{section_id[-4:]}",
                    "section_id": section_id,
                    "water_level_m": base_level + variation,
                    "reading_timestamp": reading_date.isoformat(),
                    "voltage": 3.3 + random.uniform(-0.1, 0.1),
                    "rssi": random.randint(-80, -40),
                    "quality_score": random.uniform(0.8, 1.0)
                })
    
    def _create_weather_data(self):
        """Create sample weather data"""
        locations = ["Khon Kaen", "Nakhon Ratchasima", "Munbon Project Area"]
        
        for location in locations:
            self.weather_data[location] = {
                "location": location,
                "current": {
                    "temperature_c": random.uniform(25, 35),
                    "humidity_percent": random.uniform(60, 85),
                    "wind_speed_ms": random.uniform(1, 5),
                    "rainfall_mm": 0 if random.random() > 0.3 else random.uniform(0, 20),
                    "et0_mm": random.uniform(4, 6),
                    "timestamp": datetime.utcnow().isoformat()
                },
                "forecast_7d": [
                    {
                        "date": (datetime.now() + timedelta(days=i)).date().isoformat(),
                        "temp_min_c": random.uniform(22, 27),
                        "temp_max_c": random.uniform(30, 37),
                        "rainfall_mm": 0 if random.random() > 0.4 else random.uniform(0, 30),
                        "et0_mm": random.uniform(3.5, 6.5)
                    }
                    for i in range(1, 8)
                ],
                "historical_avg": {
                    "monthly_rainfall_mm": [80, 60, 40, 20, 150, 180, 200, 220, 250, 180, 60, 40],
                    "monthly_et0_mm": [150, 160, 180, 200, 180, 160, 150, 150, 140, 150, 140, 140]
                }
            }
    
    def _create_awd_status(self):
        """Create AWD (Alternate Wetting and Drying) status"""
        for section_id in self.sections:
            if self.sections[section_id]['crop_type'] == 'rice':
                self.awd_status[section_id] = {
                    "section_id": section_id,
                    "awd_enabled": random.choice([True, False]),
                    "current_phase": random.choice(["wetting", "drying", "critical"]),
                    "moisture_level_percent": random.uniform(20, 80),
                    "days_since_last_irrigation": random.randint(0, 7),
                    "recommended_action": random.choice(["irrigate_now", "wait_2_days", "monitor_closely"]),
                    "water_savings_percent": random.uniform(15, 30) if random.choice([True, False]) else 0,
                    "last_updated": datetime.utcnow().isoformat()
                }
    
    def get_water_level(self, section_id: str, include_history: bool = False) -> Optional[Dict]:
        """Get water level data for a section"""
        if section_id not in self.water_levels:
            return None
        
        data = self.water_levels[section_id].copy()
        
        if include_history:
            data["history"] = self.sensor_readings.get(section_id, [])
        
        # Add realistic daily variation
        variation = random.uniform(-0.1, 0.1)
        data["current_level_m"] = max(0, data["current_level_m"] + variation)
        
        return data
    
    def get_demand_for_section(self, section_id: str, date: date) -> Dict:
        """Get or create demand for a section on a specific date"""
        key = f"{section_id}_{date.isoformat()}"
        
        if key not in self.demands:
            section = self.sections.get(section_id, {})
            area_rai = section.get('area_rai', 100)
            crop_type = section.get('crop_type', 'rice')
            
            # Base demand calculation
            if crop_type == 'rice':
                base_demand_mm = random.uniform(5, 8)
            else:
                base_demand_mm = random.uniform(3, 5)
            
            base_demand_m3 = base_demand_mm * area_rai * 1.6
            
            # Apply water level adjustment
            water_level = self.get_water_level(section_id)
            if water_level:
                current_level = water_level['current_level_m']
                thresholds = water_level['thresholds']
                
                # Simple adjustment logic
                if current_level < thresholds['warning_low']:
                    adjustment_factor = 0.7
                elif current_level > thresholds['warning_high']:
                    adjustment_factor = 0.9
                else:
                    adjustment_factor = 1.0
            else:
                adjustment_factor = 1.0
            
            self.demands[key] = {
                "section_id": section_id,
                "date": date.isoformat(),
                "base_demand_m3": base_demand_m3,
                "adjustment_factor": adjustment_factor,
                "adjusted_demand_m3": base_demand_m3 * adjustment_factor,
                "crop_type": crop_type,
                "area_rai": area_rai,
                "priority": random.choice(["high", "medium", "low"]),
                "created_at": datetime.utcnow().isoformat()
            }
        
        return self.demands[key]
    
    def create_schedule(self, demands: List[Dict], week: str) -> Dict:
        """Create irrigation schedule from demands"""
        schedule_id = f"SCH-{week}-{datetime.utcnow().timestamp()}"
        
        total_demand = sum(d.get('adjusted_demand_m3', 0) for d in demands)
        
        # Group by delivery gate
        gate_demands = defaultdict(list)
        for demand in demands:
            section = self.sections.get(demand['section_id'], {})
            gate = section.get('delivery_gate', 'unknown')
            gate_demands[gate].append(demand)
        
        # Create gate operations
        operations = []
        for gate, gate_demand_list in gate_demands.items():
            gate_total = sum(d.get('adjusted_demand_m3', 0) for d in gate_demand_list)
            flow_rate = gate_total / (8 * 3600)  # 8-hour delivery window
            
            operations.append({
                "gate_id": gate,
                "action": "open",
                "target_opening_m": min(2.0, flow_rate / 2),  # Simple calculation
                "target_flow_m3s": flow_rate,
                "scheduled_time": f"{week}T08:00:00",
                "duration_hours": 8,
                "sections_served": [d['section_id'] for d in gate_demand_list]
            })
        
        schedule = {
            "schedule_id": schedule_id,
            "week": week,
            "total_demand_m3": total_demand,
            "section_count": len(demands),
            "operations": operations,
            "status": "pending",
            "created_at": datetime.utcnow().isoformat()
        }
        
        self.schedules[schedule_id] = schedule
        return schedule
    
    def get_crop_calendar(self, area_id: str, crop_type: str) -> Dict:
        """Get crop calendar for an area"""
        if crop_type == "rice":
            growth_stages = [
                {"week": 1, "stage": "seedling", "kc": 1.05, "water_need": "low"},
                {"week": 4, "stage": "tillering", "kc": 1.1, "water_need": "medium"},
                {"week": 8, "stage": "panicle_initiation", "kc": 1.2, "water_need": "high"},
                {"week": 11, "stage": "flowering", "kc": 1.35, "water_need": "critical"},
                {"week": 14, "stage": "grain_filling", "kc": 1.1, "water_need": "medium"},
                {"week": 16, "stage": "maturity", "kc": 0.7, "water_need": "low"}
            ]
            duration_weeks = 16
        else:  # sugarcane
            growth_stages = [
                {"week": 1, "stage": "germination", "kc": 0.4, "water_need": "medium"},
                {"week": 12, "stage": "tillering", "kc": 0.7, "water_need": "high"},
                {"week": 28, "stage": "grand_growth", "kc": 1.25, "water_need": "critical"},
                {"week": 40, "stage": "ripening", "kc": 0.75, "water_need": "low"},
                {"week": 48, "stage": "maturity", "kc": 0.6, "water_need": "minimal"}
            ]
            duration_weeks = 48
        
        planting_date = datetime.now() - timedelta(days=random.randint(20, 60))
        harvest_date = planting_date + timedelta(weeks=duration_weeks)
        
        return {
            "area_id": area_id,
            "area_type": "plot" if area_id.startswith("Z") else "section",
            "crop_type": crop_type,
            "planting_date": planting_date.isoformat(),
            "expected_harvest_date": harvest_date.isoformat(),
            "season": "dry" if planting_date.month in [11, 12, 1, 2, 3, 4] else "wet",
            "year": planting_date.year,
            "growth_stages": growth_stages,
            "total_weeks": duration_weeks
        }


# Singleton instance
_instance = None

def get_mock_data_manager() -> MockDataManager:
    """Get singleton instance of mock data manager"""
    global _instance
    if _instance is None:
        _instance = MockDataManager()
    return _instance