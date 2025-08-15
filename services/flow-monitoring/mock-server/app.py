"""
Mock API Server for Flow Monitoring Service Development
Enables parallel development of Instances 16, 17, and 18
Run on port 3099 to avoid conflicts with actual services
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
import random
import uvicorn

app = FastAPI(title="Flow Monitoring Mock Server", version="1.0.0")

# Enable CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared Type Definitions (matching shared_types.py)
class GateState(BaseModel):
    gate_id: str
    type: str  # "automated" | "manual"
    opening_m: float
    flow_m3s: float
    last_updated: datetime
    mode: Optional[str] = "auto"  # "auto" | "manual" | "transition"

class SectionDemand(BaseModel):
    section_id: str
    zone: int
    demand_m3: float
    priority: int
    crop_type: str
    delivery_window: Dict[str, datetime]

class ScheduleOperation(BaseModel):
    gate_id: str
    action: str  # "open" | "close" | "adjust"
    target_opening_m: float
    scheduled_time: datetime
    team_assigned: Optional[str]

class HydraulicVerification(BaseModel):
    proposed_operations: List[ScheduleOperation]
    constraints: Dict[str, Any]

# Mock data storage
gates_db = {
    "Source->M(0,0)": {
        "type": "automated",
        "state": "open",
        "opening_m": 1.8,
        "flow_m3s": 4.5,
        "mode": "auto",
        "width_m": 3.0,
        "calibration_k1": 0.61,
        "calibration_k2": -0.12
    },
    "M(0,0)->M(0,2)": {
        "type": "manual",
        "state": "partial",
        "opening_m": 1.2,
        "flow_m3s": 2.8,
        "mode": "manual",
        "width_m": 2.5,
        "calibration_k1": 0.58,
        "calibration_k2": -0.10
    },
    "M(0,2)->Zone_2": {
        "type": "automated",
        "state": "open",
        "opening_m": 1.5,
        "flow_m3s": 2.8,
        "mode": "auto",
        "width_m": 2.0,
        "calibration_k1": 0.60,
        "calibration_k2": -0.11
    }
}

water_levels_db = {
    "M(0,0)": {"level_m": 219.2, "trend": "stable"},
    "M(0,2)": {"level_m": 218.9, "trend": "rising"},
    "Zone_2": {"level_m": 218.5, "trend": "stable"}
}

schedules_db = {}
demands_db = {}

# Health check endpoint
@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "services": {
            "core_monitoring": "mocked",
            "scheduler": "mocked",
            "ros_gis_integration": "mocked",
            "sensor_management": "mocked",
            "water_accounting": "mocked",
            "gravity_optimizer": "mocked"
        },
        "timestamp": datetime.utcnow()
    }

# Instance 16 Mock Endpoints (Core Monitoring)
@app.get("/api/v1/gates/state")
async def get_gates_state():
    """Mock endpoint for Instance 16 - gate states"""
    gates = {}
    for gate_id, data in gates_db.items():
        gates[gate_id] = {
            "type": data["type"],
            "state": data["state"],
            "opening_m": data["opening_m"],
            "flow_m3s": data["flow_m3s"],
            "mode": data["mode"],
            "last_updated": datetime.utcnow()
        }
    return {"gates": gates}

@app.post("/api/v1/hydraulics/verify-schedule")
async def verify_schedule(verification: HydraulicVerification):
    """Mock endpoint for Instance 16 - schedule verification"""
    # Simulate hydraulic verification
    feasible = random.choice([True, True, True, False])  # 75% success
    warnings = []
    
    if not feasible:
        warnings.append("Insufficient water supply for proposed schedule")
    
    # Calculate expected water levels
    water_levels = {}
    for node, data in water_levels_db.items():
        variation = random.uniform(-0.3, 0.3)
        water_levels[node] = round(data["level_m"] + variation, 2)
    
    return {
        "feasible": feasible,
        "water_levels": water_levels,
        "warnings": warnings,
        "computation_time_ms": random.randint(100, 500)
    }

@app.put("/api/v1/gates/manual/{gate_id}/state")
async def update_manual_gate(gate_id: str, state: Dict[str, Any]):
    """Mock endpoint for Instance 17 -> 16 communication"""
    if gate_id not in gates_db:
        raise HTTPException(status_code=404, detail=f"Gate {gate_id} not found")
    
    gates_db[gate_id]["opening_m"] = state["opening_m"]
    gates_db[gate_id]["flow_m3s"] = state["opening_m"] * 2.5  # Simple mock calculation
    gates_db[gate_id]["mode"] = "manual"
    
    return {
        "gate_id": gate_id,
        "updated": True,
        "new_state": gates_db[gate_id]
    }

@app.get("/api/v1/network/water-levels")
async def get_water_levels():
    """Mock endpoint for current water levels"""
    return {
        "levels": water_levels_db,
        "timestamp": datetime.utcnow()
    }

# Instance 17 Mock Endpoints (Scheduler)
@app.get("/api/v1/schedule/week/{week}")
async def get_weekly_schedule(week: str):
    """Mock endpoint for Instance 17 - weekly schedule"""
    if week not in schedules_db:
        # Generate mock schedule
        schedules_db[week] = {
            "week": week,
            "operations": [
                {
                    "day": "Tuesday",
                    "team": "Team_A",
                    "gates": ["Source->M(0,0)", "M(0,0)->M(0,2)"],
                    "volumes": {"Zone_2": 75000, "Zone_5": 50000}
                },
                {
                    "day": "Thursday",
                    "team": "Team_B",
                    "gates": ["M(0,2)->Zone_2", "M(0,5)->Zone_5"],
                    "volumes": {"Zone_2": 80000, "Zone_5": 55000}
                }
            ],
            "status": "approved"
        }
    
    return schedules_db[week]

@app.post("/api/v1/scheduler/demands")
async def submit_demands(demands: Dict[str, Any]):
    """Mock endpoint for Instance 18 -> 17 communication"""
    week = demands["week"]
    demands_db[week] = demands
    
    # Generate schedule based on demands
    schedule_id = f"SCH-{week}-{random.randint(1000, 9999)}"
    
    return {
        "schedule_id": schedule_id,
        "status": "processing",
        "conflicts": [],
        "estimated_completion": datetime.utcnow() + timedelta(minutes=5)
    }

@app.get("/api/v1/field-ops/instructions/{team}")
async def get_field_instructions(team: str):
    """Mock endpoint for field team instructions"""
    return {
        "team": team,
        "date": datetime.utcnow().date(),
        "instructions": [
            {
                "gate_id": "M(0,0)->M(0,2)",
                "location": {"lat": 14.8234, "lon": 103.1567},
                "action": "adjust",
                "target_opening_m": 1.5,
                "current_opening_m": 1.2,
                "physical_markers": "3 notches from top",
                "photo_required": True
            }
        ]
    }

# Instance 18 Mock Endpoints (ROS/GIS Integration)
@app.get("/api/v1/demands/week/{week}")
async def get_weekly_demands(week: str):
    """Mock endpoint for Instance 18 - aggregated demands"""
    if week not in demands_db:
        # Generate mock demands
        demands_db[week] = {
            "week": week,
            "sections": [
                {
                    "section_id": "Zone_2_Section_A",
                    "demand_m3": 15000,
                    "crop": "rice",
                    "growth_stage": "flowering",
                    "priority": 9,
                    "delivery_point": "M(0,2)->Zone_2"
                },
                {
                    "section_id": "Zone_2_Section_B",
                    "demand_m3": 12000,
                    "crop": "rice",
                    "growth_stage": "vegetative",
                    "priority": 7,
                    "delivery_point": "M(0,2)->Zone_2"
                },
                {
                    "section_id": "Zone_5_Section_A",
                    "demand_m3": 18000,
                    "crop": "sugarcane",
                    "growth_stage": "tillering",
                    "priority": 8,
                    "delivery_point": "M(0,5)->Zone_5"
                }
            ]
        }
    
    return demands_db[week]

@app.post("/api/v1/performance/feedback")
async def submit_performance_feedback(feedback: Dict[str, Any]):
    """Mock endpoint for delivery performance feedback"""
    return {
        "received": True,
        "sections_updated": len(feedback.get("sections", [])),
        "efficiency_avg": random.uniform(0.85, 0.95)
    }

# Instance 13 Mock Endpoints (Sensor Management)
@app.get("/api/v1/sensors/mobile/status")
async def get_mobile_sensors():
    """Mock endpoint for mobile sensor status"""
    return {
        "sensors": [
            {
                "sensor_id": "WL-001",
                "type": "water_level",
                "current_location": {"lat": 14.8234, "lon": 103.1567},
                "section": "Zone_2_Section_A",
                "battery_percent": 87,
                "last_reading": {
                    "value": 218.5,
                    "unit": "m",
                    "timestamp": datetime.utcnow() - timedelta(minutes=5)
                }
            },
            {
                "sensor_id": "SM-001",
                "type": "soil_moisture",
                "current_location": {"lat": 14.8456, "lon": 103.1234},
                "section": "Zone_5_Section_B",
                "battery_percent": 65,
                "last_reading": {
                    "value": 32.5,
                    "unit": "%",
                    "timestamp": datetime.utcnow() - timedelta(minutes=10)
                }
            }
        ]
    }

# Instance 14 Mock Endpoints (Water Accounting)
@app.get("/api/v1/accounting/section/{section_id}")
async def get_section_accounting(section_id: str):
    """Mock endpoint for section water accounting"""
    # Generate realistic accounting data
    delivered = random.randint(12000, 18000)
    losses = random.randint(500, 1500)
    demanded = delivered + losses + random.randint(0, 2000)
    efficiency = (delivered - losses) / delivered if delivered > 0 else 0
    
    return {
        "section_id": section_id,
        "period": f"2024-W{datetime.now().isocalendar()[1]}",
        "delivered_m3": delivered,
        "losses_m3": losses,
        "efficiency": round(efficiency, 3),
        "deficit_m3": max(0, demanded - delivered),
        "water_balance": {
            "inflow_m3": delivered + losses,
            "outflow_m3": delivered,
            "seepage_loss_m3": int(losses * 0.6),
            "evaporation_loss_m3": int(losses * 0.3),
            "operational_loss_m3": int(losses * 0.1)
        }
    }

@app.get("/api/v1/accounting/sections")
async def list_sections(zone: Optional[int] = None):
    """List all sections with accounting status"""
    sections = []
    for i in range(1, 6):
        for j in range(1, 4):
            section_id = f"SEC-Z{i}-{j:03d}"
            delivered = random.randint(10000, 20000)
            sections.append({
                "section_id": section_id,
                "zone": i,
                "area_hectares": random.randint(50, 200),
                "current_status": random.choice(["active", "completed", "scheduled"]),
                "last_delivery": {
                    "date": (datetime.now() - timedelta(days=random.randint(1, 7))).isoformat(),
                    "volume_m3": delivered,
                    "efficiency": random.uniform(0.85, 0.95)
                }
            })
    
    if zone:
        sections = [s for s in sections if s["zone"] == zone]
    
    return {"sections": sections, "total": len(sections)}

@app.get("/api/v1/accounting/balance/{section_id}")
async def get_water_balance(section_id: str, start_date: Optional[str] = None, end_date: Optional[str] = None):
    """Get water balance over time period"""
    if not start_date:
        start_date = (datetime.now() - timedelta(days=7)).isoformat()
    if not end_date:
        end_date = datetime.now().isoformat()
    
    # Generate daily balance data
    daily_data = []
    current = datetime.fromisoformat(start_date.replace('Z', '+00:00') if 'Z' in start_date else start_date)
    end = datetime.fromisoformat(end_date.replace('Z', '+00:00') if 'Z' in end_date else end_date)
    
    while current <= end:
        delivered = random.randint(1500, 2500)
        losses = random.randint(50, 150)
        daily_data.append({
            "date": current.date().isoformat(),
            "inflow_m3": delivered + losses,
            "delivered_m3": delivered,
            "losses_m3": losses,
            "efficiency": round((delivered - losses) / delivered if delivered > 0 else 0, 3)
        })
        current += timedelta(days=1)
    
    return {
        "section_id": section_id,
        "period": {"start": start_date, "end": end_date},
        "daily_balance": daily_data,
        "summary": {
            "total_inflow_m3": sum(d["inflow_m3"] for d in daily_data),
            "total_delivered_m3": sum(d["delivered_m3"] for d in daily_data),
            "total_losses_m3": sum(d["losses_m3"] for d in daily_data),
            "average_efficiency": round(sum(d["efficiency"] for d in daily_data) / len(daily_data), 3)
        }
    }

# Additional Water Accounting Endpoints
@app.post("/api/v1/delivery/complete")
async def complete_delivery(delivery_data: Dict[str, Any]):
    """Process completed delivery"""
    section_id = delivery_data.get("section_id", "SEC-Z1-001")
    flow_readings = delivery_data.get("flow_readings", [])
    
    # Calculate volume from flow readings
    total_volume = sum(f.get("flow_rate_m3s", 0) * 3600 for f in flow_readings)  # Assuming hourly readings
    losses = total_volume * random.uniform(0.02, 0.05)  # 2-5% losses
    
    return {
        "delivery_id": f"DEL-{random.randint(1000, 9999)}",
        "section_id": section_id,
        "status": "completed",
        "summary": {
            "total_volume_m3": round(total_volume, 2),
            "delivered_volume_m3": round(total_volume - losses, 2),
            "transit_losses_m3": round(losses, 2),
            "efficiency": round((total_volume - losses) / total_volume if total_volume > 0 else 0, 3),
            "duration_hours": len(flow_readings)
        },
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/v1/delivery/status/{delivery_id}")
async def get_delivery_status(delivery_id: str):
    """Get delivery status"""
    return {
        "delivery_id": delivery_id,
        "status": random.choice(["in_progress", "completed", "scheduled"]),
        "section_id": f"SEC-Z{random.randint(1, 5)}-{random.randint(1, 3):03d}",
        "progress_percentage": random.randint(60, 100),
        "estimated_completion": (datetime.now() + timedelta(hours=random.randint(1, 4))).isoformat()
    }

@app.post("/api/v1/delivery/validate-flow-data")
async def validate_flow_data(flow_data: Dict[str, Any]):
    """Validate flow readings"""
    readings = flow_data.get("readings", [])
    issues = []
    
    # Mock validation logic
    for i, reading in enumerate(readings):
        if reading.get("flow_rate_m3s", 0) > 10:
            issues.append({"index": i, "issue": "Flow rate exceeds maximum capacity"})
        if reading.get("quality", 1) < 0.8:
            issues.append({"index": i, "issue": "Low data quality"})
    
    return {
        "valid": len(issues) == 0,
        "total_readings": len(readings),
        "issues": issues,
        "data_completeness": random.uniform(0.95, 1.0)
    }

@app.get("/api/v1/efficiency/report")
async def get_efficiency_report(period: Optional[str] = None):
    """Generate efficiency report"""
    if not period:
        period = f"2024-W{datetime.now().isocalendar()[1]}"
    
    sections = []
    for i in range(1, 6):
        for j in range(1, 3):
            efficiency = random.uniform(0.75, 0.95)
            sections.append({
                "section_id": f"SEC-Z{i}-{j:03d}",
                "efficiency": round(efficiency, 3),
                "classification": "excellent" if efficiency > 0.9 else "good" if efficiency > 0.8 else "needs_improvement",
                "delivered_m3": random.randint(10000, 20000),
                "losses_m3": random.randint(500, 2000)
            })
    
    return {
        "period": period,
        "sections": sections,
        "system_average": round(sum(s["efficiency"] for s in sections) / len(sections), 3),
        "benchmark": 0.85,
        "recommendations": [
            "Inspect gates in Zone 3 for leakage",
            "Consider canal lining in sections with high seepage"
        ]
    }

@app.get("/api/v1/efficiency/trends/{section_id}")
async def get_efficiency_trends(section_id: str, weeks: int = 4):
    """Get efficiency trends"""
    trends = []
    current_week = datetime.now().isocalendar()[1]
    
    for i in range(weeks):
        week_num = current_week - i
        efficiency = random.uniform(0.8, 0.95) + (i * 0.01)  # Slight improvement over time
        trends.append({
            "week": f"2024-W{week_num}",
            "efficiency": round(min(efficiency, 0.95), 3),
            "delivered_m3": random.randint(12000, 18000),
            "losses_m3": random.randint(500, 1500)
        })
    
    trends.reverse()  # Chronological order
    
    return {
        "section_id": section_id,
        "trends": trends,
        "improvement_rate": round((trends[-1]["efficiency"] - trends[0]["efficiency"]) / trends[0]["efficiency"] * 100, 2),
        "status": "improving" if trends[-1]["efficiency"] > trends[0]["efficiency"] else "stable"
    }

@app.get("/api/v1/efficiency/benchmarks")
async def get_efficiency_benchmarks():
    """Get system benchmarks"""
    return {
        "benchmarks": {
            "excellent": 0.90,
            "good": 0.80,
            "acceptable": 0.70,
            "poor": 0.60
        },
        "current_performance": {
            "system_average": 0.85,
            "best_section": {"id": "SEC-Z2-001", "efficiency": 0.94},
            "worst_section": {"id": "SEC-Z4-003", "efficiency": 0.72}
        },
        "targets": {
            "2024": 0.85,
            "2025": 0.87,
            "2026": 0.90
        }
    }

@app.post("/api/v1/efficiency/calculate-losses")
async def calculate_transit_losses(loss_data: Dict[str, Any]):
    """Calculate transit losses"""
    volume = loss_data.get("volume_m3", 10000)
    distance_km = loss_data.get("distance_km", 5)
    canal_type = loss_data.get("canal_type", "earthen")
    weather = loss_data.get("weather_conditions", {})
    
    # Mock loss calculations
    seepage_rate = 0.02 if canal_type == "concrete" else 0.05
    evap_rate = 0.001 * weather.get("temperature", 30) / 30
    
    seepage = volume * seepage_rate * distance_km / 10
    evaporation = volume * evap_rate * loss_data.get("transit_hours", 4)
    operational = volume * 0.005  # 0.5% operational losses
    
    return {
        "total_loss_m3": round(seepage + evaporation + operational, 2),
        "breakdown": {
            "seepage_m3": round(seepage, 2),
            "evaporation_m3": round(evaporation, 2),
            "operational_m3": round(operational, 2)
        },
        "loss_percentage": round((seepage + evaporation + operational) / volume * 100, 2),
        "confidence_interval": {
            "lower": round((seepage + evaporation + operational) * 0.9, 2),
            "upper": round((seepage + evaporation + operational) * 1.1, 2)
        }
    }

@app.get("/api/v1/deficits/week/{week}/{year}")
async def get_weekly_deficits(week: int, year: int):
    """Get weekly deficit summary"""
    deficits = []
    
    for zone in range(1, 6):
        for section in range(1, 3):
            section_id = f"SEC-Z{zone}-{section:03d}"
            demand = random.randint(15000, 25000)
            delivered = random.randint(12000, 23000)
            deficit = max(0, demand - delivered)
            
            deficits.append({
                "section_id": section_id,
                "zone": zone,
                "demand_m3": demand,
                "delivered_m3": delivered,
                "deficit_m3": deficit,
                "deficit_percentage": round(deficit / demand * 100 if demand > 0 else 0, 1),
                "stress_level": "severe" if deficit / demand > 0.3 else "moderate" if deficit / demand > 0.15 else "mild" if deficit / demand > 0.05 else "none"
            })
    
    return {
        "week": f"{year}-W{week:02d}",
        "deficits": deficits,
        "summary": {
            "total_deficit_m3": sum(d["deficit_m3"] for d in deficits),
            "sections_affected": len([d for d in deficits if d["deficit_m3"] > 0]),
            "critical_sections": len([d for d in deficits if d["stress_level"] in ["moderate", "severe"]])
        }
    }

@app.post("/api/v1/deficits/update")
async def update_deficit_tracking(deficit_data: Dict[str, Any]):
    """Update deficit tracking"""
    return {
        "status": "updated",
        "section_id": deficit_data.get("section_id"),
        "deficit_record": {
            "week": deficit_data.get("week"),
            "deficit_m3": deficit_data.get("deficit_m3"),
            "carry_forward_m3": deficit_data.get("carry_forward_m3", 0),
            "recovery_planned": deficit_data.get("recovery_planned", False)
        }
    }

@app.get("/api/v1/deficits/carry-forward/{section_id}")
async def get_carry_forward_status(section_id: str):
    """Get carry-forward deficit status"""
    deficits = []
    current_week = datetime.now().isocalendar()[1]
    
    for i in range(4):  # Last 4 weeks
        week = current_week - i
        deficit = random.randint(0, 2000) if i < 2 else 0
        deficits.append({
            "week": f"2024-W{week:02d}",
            "deficit_m3": deficit,
            "age_weeks": i,
            "priority_score": deficit * (4 - i) / 4 if deficit > 0 else 0
        })
    
    total_carry_forward = sum(d["deficit_m3"] for d in deficits)
    
    return {
        "section_id": section_id,
        "carry_forward_deficits": deficits,
        "total_carry_forward_m3": total_carry_forward,
        "recovery_priority": "high" if total_carry_forward > 5000 else "medium" if total_carry_forward > 2000 else "low",
        "recommended_allocation_m3": min(total_carry_forward * 1.2, 8000)
    }

@app.post("/api/v1/deficits/recovery-plan")
async def generate_recovery_plan(recovery_data: Dict[str, Any]):
    """Generate deficit recovery plan"""
    section_id = recovery_data.get("section_id")
    deficit_m3 = recovery_data.get("deficit_m3", 5000)
    
    # Mock recovery plan
    daily_capacity = random.randint(1500, 2500)
    days_needed = int(deficit_m3 / daily_capacity) + 1
    
    return {
        "section_id": section_id,
        "recovery_plan": {
            "total_deficit_m3": deficit_m3,
            "daily_allocation_m3": daily_capacity,
            "days_required": days_needed,
            "start_date": datetime.now().date().isoformat(),
            "end_date": (datetime.now() + timedelta(days=days_needed)).date().isoformat(),
            "strategy": "gradual_recovery",
            "constraints": [
                "Limited by canal capacity",
                "Must coordinate with downstream users"
            ]
        },
        "success_probability": 0.85
    }

@app.get("/api/v1/deficits/stress-assessment")
async def get_stress_assessment():
    """System-wide stress assessment"""
    zones = []
    
    for zone in range(1, 6):
        sections_in_zone = []
        for section in range(1, 4):
            stress = random.choice(["none", "mild", "moderate", "severe"])
            sections_in_zone.append({
                "section_id": f"SEC-Z{zone}-{section:03d}",
                "stress_level": stress,
                "deficit_percentage": 0 if stress == "none" else 10 if stress == "mild" else 20 if stress == "moderate" else 35
            })
        
        zones.append({
            "zone": zone,
            "sections": sections_in_zone,
            "zone_stress": max(sections_in_zone, key=lambda x: ["none", "mild", "moderate", "severe"].index(x["stress_level"]))["stress_level"]
        })
    
    system_stress_counts = {
        "none": sum(1 for z in zones for s in z["sections"] if s["stress_level"] == "none"),
        "mild": sum(1 for z in zones for s in z["sections"] if s["stress_level"] == "mild"),
        "moderate": sum(1 for z in zones for s in z["sections"] if s["stress_level"] == "moderate"),
        "severe": sum(1 for z in zones for s in z["sections"] if s["stress_level"] == "severe")
    }
    
    return {
        "assessment_date": datetime.now().isoformat(),
        "zones": zones,
        "system_summary": system_stress_counts,
        "recommendations": [
            "Prioritize water delivery to severe stress sections",
            "Consider temporary crop adjustment in moderate stress areas",
            "Monitor mild stress sections for escalation"
        ]
    }

# Instance 15 Mock Endpoints (Gravity Optimizer)
@app.post("/api/v1/gravity/optimize-flow")
async def optimize_gravity_flow(request: Dict[str, Any]):
    """Mock endpoint for gravity flow optimization"""
    return {
        "optimal_gates": {
            "Source->M(0,0)": {"opening_m": 2.1, "flow_m3s": 5.2},
            "M(0,0)->M(0,2)": {"opening_m": 1.8, "flow_m3s": 3.5}
        },
        "energy_head_m": 221.5,
        "friction_losses_m": 2.3,
        "delivery_time_hours": 4.5
    }

# WebSocket mock for real-time updates
from fastapi import WebSocket
import json

@app.websocket("/ws/monitoring")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            # Send mock updates every 5 seconds
            await websocket.send_json({
                "type": "water_level_update",
                "data": {
                    "node": "M(0,2)",
                    "level_m": round(218.9 + random.uniform(-0.1, 0.1), 2),
                    "timestamp": datetime.utcnow().isoformat()
                }
            })
            await websocket.receive_text()  # Keep connection alive
    except:
        pass

if __name__ == "__main__":
    print("Starting Flow Monitoring Mock Server on port 3099...")
    print("This enables parallel development of all Flow Monitoring instances")
    print("\nAvailable endpoints:")
    print("- Health: http://localhost:3099/health")
    print("- API Docs: http://localhost:3099/docs")
    uvicorn.run(app, host="0.0.0.0", port=3099)