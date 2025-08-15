"""
Minimal Scheduler Service for Testing
Works without heavy optimization dependencies
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import os
import json

# Create FastAPI app
app = FastAPI(
    title="Munbon Scheduler Service (Minimal)",
    description="Weekly batch scheduler for irrigation operations",
    version="1.0.0-minimal",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mock data storage (in-memory for testing)
schedules_db = {}
demands_db = {}
operations_db = {}
teams_db = {
    "Team_A": {
        "name": "Field Team Alpha",
        "leader": "Somchai Jaidee",
        "status": "active",
        "location": {"lat": 14.8234, "lon": 103.1567}
    },
    "Team_B": {
        "name": "Field Team Bravo", 
        "leader": "Prasert Suksri",
        "status": "active",
        "location": {"lat": 14.8456, "lon": 103.1234}
    }
}

# Pydantic models
class DemandSubmission(BaseModel):
    week: str
    sections: List[Dict[str, Any]]

class ScheduleOperation(BaseModel):
    gate_id: str
    action: str
    target_opening_m: float
    scheduled_time: datetime

class OperationReport(BaseModel):
    operation_id: str
    status: str
    actual_opening_m: Optional[float] = None
    notes: Optional[str] = None
    timestamp: datetime

class TeamLocation(BaseModel):
    lat: float
    lon: float
    timestamp: datetime

# Root endpoints
@app.get("/")
async def root():
    return {
        "service": "Munbon Scheduler Service",
        "version": "1.0.0-minimal",
        "status": "operational",
        "docs": "/docs"
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "scheduler",
        "version": "1.0.0-minimal",
        "dependencies": {
            "database": "connected",
            "redis": "connected",
            "mock_server": "available"
        }
    }

@app.get("/ready")
async def readiness_check():
    return {
        "status": "ready",
        "database": "connected",
        "redis": "connected"
    }

# Schedule Management Endpoints
@app.get("/api/v1/schedule/week/{week}")
async def get_weekly_schedule(week: str):
    if week not in schedules_db:
        # Generate mock schedule
        schedules_db[week] = {
            "week": week,
            "status": "draft",
            "operations": [
                {
                    "day": "Tuesday",
                    "team": "Team_A",
                    "gates": ["Source->M(0,0)", "M(0,0)->M(0,2)"],
                    "total_operations": 2,
                    "estimated_hours": 3
                },
                {
                    "day": "Thursday",
                    "team": "Team_B",
                    "gates": ["M(0,2)->Zone_2", "M(0,5)->Zone_5"],
                    "total_operations": 2,
                    "estimated_hours": 3.5
                }
            ],
            "total_volume_m3": 125000,
            "optimization_score": 0.87
        }
    return schedules_db[week]

@app.post("/api/v1/schedule/week/{week}/generate")
async def generate_weekly_schedule(week: str):
    # Simulate schedule generation
    schedule = {
        "week": week,
        "status": "generated",
        "operations": [],
        "total_volume_m3": 0,
        "optimization_score": 0.85,
        "generated_at": datetime.utcnow().isoformat()
    }
    
    # Add some mock operations
    if week in demands_db:
        total_demand = sum(s["demand_m3"] for s in demands_db[week]["sections"])
        schedule["total_volume_m3"] = total_demand
        schedule["operations"] = [
            {
                "day": "Tuesday",
                "team": "Team_A",
                "gates": ["Source->M(0,0)", "M(0,0)->M(0,2)"],
                "total_operations": 2
            }
        ]
    
    schedules_db[week] = schedule
    return {"schedule_id": f"SCH-{week}", "status": "generated", "schedule": schedule}

@app.put("/api/v1/schedule/week/{week}/status")
async def update_schedule_status(week: str, status: str):
    if week not in schedules_db:
        raise HTTPException(status_code=404, detail="Schedule not found")
    
    schedules_db[week]["status"] = status
    if status == "approved":
        schedules_db[week]["approved_at"] = datetime.utcnow().isoformat()
    
    return {"week": week, "status": status, "updated": True}

@app.get("/api/v1/schedule/current")
async def get_current_schedule():
    # Get current week
    current_week = datetime.now().strftime("%Y-W%U")
    
    for week, schedule in schedules_db.items():
        if schedule.get("status") == "approved":
            return schedule
    
    raise HTTPException(status_code=404, detail="No approved schedule found")

@app.get("/api/v1/schedule/conflicts/{week}")
async def check_schedule_conflicts(week: str):
    # Mock conflict checking
    return {
        "week": week,
        "conflicts": [],
        "warnings": ["Gate M(0,2) scheduled for maintenance on Thursday"],
        "feasible": True
    }

# Demand Processing Endpoints
@app.post("/api/v1/scheduler/demands")
async def submit_demands(demands: DemandSubmission):
    week = demands.week
    demands_db[week] = demands.dict()
    
    # Generate schedule ID
    schedule_id = f"SCH-{week}-{len(demands_db)}"
    
    return {
        "schedule_id": schedule_id,
        "status": "processing",
        "conflicts": [],
        "estimated_completion": (datetime.utcnow() + timedelta(minutes=5)).isoformat()
    }

@app.get("/api/v1/scheduler/demands/week/{week}")
async def get_weekly_demands(week: str):
    if week not in demands_db:
        # Return mock demands
        return {
            "week": week,
            "sections": [
                {
                    "section_id": "Zone_2_Section_A",
                    "demand_m3": 15000,
                    "crop": "rice",
                    "priority": 9
                }
            ],
            "total_demand_m3": 15000,
            "status": "aggregated"
        }
    return demands_db[week]

@app.post("/api/v1/scheduler/demands/validate")
async def validate_demands(demands: DemandSubmission):
    # Mock validation
    total_demand = sum(s.get("demand_m3", 0) for s in demands.sections)
    
    return {
        "valid": True,
        "total_demand_m3": total_demand,
        "capacity_available": True,
        "warnings": []
    }

# Field Operations Endpoints
@app.get("/api/v1/field-ops/instructions/{team}")
async def get_field_instructions(team: str):
    if team not in teams_db:
        raise HTTPException(status_code=404, detail="Team not found")
    
    return {
        "team": team,
        "date": datetime.utcnow().date().isoformat(),
        "instructions": [
            {
                "gate_id": "M(0,0)->M(0,2)",
                "location": {"lat": 14.8234, "lon": 103.1567},
                "action": "adjust",
                "target_opening_m": 1.5,
                "current_opening_m": 1.2,
                "physical_markers": "3 notches from top",
                "photo_required": True,
                "sequence": 1
            }
        ],
        "total_gates": 1,
        "estimated_hours": 1.5
    }

@app.post("/api/v1/field-ops/instructions/download/{team}")
async def download_offline_package(team: str):
    if team not in teams_db:
        raise HTTPException(status_code=404, detail="Team not found")
    
    # Create offline package
    package = {
        "team": team,
        "generated_at": datetime.utcnow().isoformat(),
        "valid_until": (datetime.utcnow() + timedelta(days=7)).isoformat(),
        "instructions": [],
        "gate_locations": {},
        "maps": []
    }
    
    return package

@app.put("/api/v1/field-ops/operations/{operation_id}/report")
async def submit_operation_report(operation_id: str, report: OperationReport):
    operations_db[operation_id] = report.dict()
    return {
        "operation_id": operation_id,
        "received": True,
        "status": report.status
    }

@app.post("/api/v1/field-ops/teams/{team}/location")
async def update_team_location(team: str, location: TeamLocation):
    if team not in teams_db:
        raise HTTPException(status_code=404, detail="Team not found")
    
    teams_db[team]["location"] = {"lat": location.lat, "lon": location.lon}
    teams_db[team]["last_update"] = location.timestamp.isoformat()
    
    return {"team": team, "location_updated": True}

@app.get("/api/v1/field-ops/teams/status")
async def get_teams_status():
    return {
        "teams": teams_db,
        "active_teams": len([t for t in teams_db.values() if t["status"] == "active"]),
        "timestamp": datetime.utcnow().isoformat()
    }

# Run the application
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("SERVICE_PORT", "3021"))
    uvicorn.run(app, host="0.0.0.0", port=port)