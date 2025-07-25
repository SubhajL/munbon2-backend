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
    return {
        "section_id": section_id,
        "period": "2024-W03",
        "delivered_m3": random.randint(12000, 18000),
        "losses_m3": random.randint(500, 1500),
        "efficiency": random.uniform(0.85, 0.95),
        "deficit_m3": random.randint(0, 2000)
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