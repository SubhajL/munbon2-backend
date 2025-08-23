"""Mock scheduler service endpoints"""
from datetime import datetime, timedelta, time
from typing import Dict, List, Optional
import random
from fastapi import APIRouter, Query, HTTPException
from enum import Enum

router = APIRouter()

class ScheduleStatus(str, Enum):
    SCHEDULED = "scheduled"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    PAUSED = "paused"

class ScheduleType(str, Enum):
    IRRIGATION = "irrigation"
    MAINTENANCE = "maintenance"
    ROTATION = "rotation"
    EMERGENCY = "emergency"

# Mock schedule data
MOCK_SCHEDULES = [
    {
        "schedule_id": "SCH-001",
        "type": ScheduleType.IRRIGATION,
        "section_id": "S1",
        "name": "Morning Irrigation - Section 1",
        "start_time": "06:00",
        "duration_minutes": 180,
        "water_volume_m3": 5000,
        "frequency": "daily",
        "days_of_week": [1, 2, 3, 4, 5, 6, 7],
        "status": ScheduleStatus.ACTIVE,
        "created_by": "System",
        "created_at": "2024-01-01T00:00:00Z"
    },
    {
        "schedule_id": "SCH-002",
        "type": ScheduleType.IRRIGATION,
        "section_id": "S2",
        "name": "Evening Irrigation - Section 2",
        "start_time": "17:00",
        "duration_minutes": 120,
        "water_volume_m3": 3500,
        "frequency": "daily",
        "days_of_week": [1, 3, 5, 7],
        "status": ScheduleStatus.SCHEDULED,
        "created_by": "Operator1",
        "created_at": "2024-01-05T00:00:00Z"
    }
]

@router.get("/api/v1/schedules")
async def get_schedules(
    section_id: Optional[str] = Query(None),
    schedule_type: Optional[ScheduleType] = Query(None),
    status: Optional[ScheduleStatus] = Query(None),
    date: Optional[str] = Query(None)
):
    """Get irrigation schedules"""
    print(f"[Mock Scheduler] GET schedules - section: {section_id}, type: {schedule_type}, status: {status}")
    
    schedules = MOCK_SCHEDULES.copy()
    
    # Apply filters
    if section_id:
        schedules = [s for s in schedules if s["section_id"] == section_id]
    if schedule_type:
        schedules = [s for s in schedules if s["type"] == schedule_type]
    if status:
        schedules = [s for s in schedules if s["status"] == status]
    
    # Add execution info for today
    target_date = datetime.utcnow().date() if not date else datetime.fromisoformat(date.replace('Z', '+00:00')).date()
    
    enriched_schedules = []
    for schedule in schedules:
        enriched = schedule.copy()
        
        # Calculate next execution
        start_hour, start_minute = map(int, schedule["start_time"].split(":"))
        next_execution = datetime.combine(target_date, time(start_hour, start_minute))
        
        if datetime.utcnow() > next_execution:
            next_execution += timedelta(days=1)
        
        enriched["next_execution"] = next_execution.isoformat()
        enriched["executions_today"] = 1 if target_date.isoweekday() in schedule["days_of_week"] else 0
        
        enriched_schedules.append(enriched)
    
    return {
        "total_schedules": len(enriched_schedules),
        "active_schedules": len([s for s in enriched_schedules if s["status"] == ScheduleStatus.ACTIVE]),
        "schedules": enriched_schedules,
        "query_date": target_date.isoformat()
    }

@router.post("/api/v1/schedules")
async def create_schedule(schedule_data: Dict):
    """Create a new irrigation schedule"""
    print(f"[Mock Scheduler] POST create schedule: {schedule_data}")
    
    # Validate required fields
    required_fields = ["type", "section_id", "name", "start_time", "duration_minutes"]
    for field in required_fields:
        if field not in schedule_data:
            raise HTTPException(status_code=400, detail=f"{field} is required")
    
    new_schedule = {
        "schedule_id": f"SCH-{int(datetime.utcnow().timestamp())}",
        "status": ScheduleStatus.SCHEDULED,
        "created_at": datetime.utcnow().isoformat(),
        "created_by": schedule_data.get("created_by", "API"),
        **schedule_data
    }
    
    MOCK_SCHEDULES.append(new_schedule)
    
    return {
        "success": True,
        "schedule": new_schedule,
        "message": "Schedule created successfully"
    }

@router.put("/api/v1/schedules/{schedule_id}")
async def update_schedule(schedule_id: str, updates: Dict):
    """Update an existing schedule"""
    print(f"[Mock Scheduler] PUT update schedule {schedule_id}: {updates}")
    
    schedule = next((s for s in MOCK_SCHEDULES if s["schedule_id"] == schedule_id), None)
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    
    # Update fields
    for key, value in updates.items():
        if key in schedule:
            schedule[key] = value
    
    schedule["updated_at"] = datetime.utcnow().isoformat()
    
    return {
        "success": True,
        "schedule": schedule,
        "message": "Schedule updated successfully"
    }

@router.delete("/api/v1/schedules/{schedule_id}")
async def delete_schedule(schedule_id: str):
    """Delete a schedule"""
    print(f"[Mock Scheduler] DELETE schedule {schedule_id}")
    
    schedule = next((s for s in MOCK_SCHEDULES if s["schedule_id"] == schedule_id), None)
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    
    MOCK_SCHEDULES.remove(schedule)
    
    return {
        "success": True,
        "message": f"Schedule {schedule_id} deleted successfully"
    }

@router.get("/api/v1/schedules/{schedule_id}/executions")
async def get_schedule_executions(
    schedule_id: str,
    start_date: str,
    end_date: str
):
    """Get execution history for a schedule"""
    print(f"[Mock Scheduler] GET executions for schedule {schedule_id}")
    
    schedule = next((s for s in MOCK_SCHEDULES if s["schedule_id"] == schedule_id), None)
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    
    try:
        start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        end = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format")
    
    # Generate mock execution history
    executions = []
    current = start
    
    while current <= end:
        if current.date().isoweekday() in schedule.get("days_of_week", []):
            start_hour, start_minute = map(int, schedule["start_time"].split(":"))
            execution_start = current.replace(hour=start_hour, minute=start_minute)
            execution_end = execution_start + timedelta(minutes=schedule["duration_minutes"])
            
            executions.append({
                "execution_id": f"EXE-{int(execution_start.timestamp())}",
                "schedule_id": schedule_id,
                "start_time": execution_start.isoformat(),
                "end_time": execution_end.isoformat(),
                "status": "completed" if execution_end < datetime.utcnow() else "scheduled",
                "actual_duration_minutes": schedule["duration_minutes"] + random.randint(-5, 5),
                "actual_volume_m3": schedule.get("water_volume_m3", 0) * (0.95 + random.uniform(0, 0.1)),
                "notes": ""
            })
        
        current += timedelta(days=1)
    
    return {
        "schedule_id": schedule_id,
        "period": {
            "start": start_date,
            "end": end_date
        },
        "total_executions": len(executions),
        "completed": len([e for e in executions if e["status"] == "completed"]),
        "executions": executions
    }

@router.post("/api/v1/schedules/{schedule_id}/execute")
async def execute_schedule_now(schedule_id: str):
    """Execute a schedule immediately"""
    print(f"[Mock Scheduler] POST execute schedule {schedule_id} now")
    
    schedule = next((s for s in MOCK_SCHEDULES if s["schedule_id"] == schedule_id), None)
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    
    execution = {
        "execution_id": f"EXE-{int(datetime.utcnow().timestamp())}",
        "schedule_id": schedule_id,
        "start_time": datetime.utcnow().isoformat(),
        "status": "executing",
        "triggered_by": "manual",
        "estimated_end_time": (datetime.utcnow() + timedelta(minutes=schedule["duration_minutes"])).isoformat()
    }
    
    return {
        "success": True,
        "execution": execution,
        "message": f"Schedule {schedule_id} execution started"
    }

@router.get("/api/v1/schedules/conflicts")
async def check_schedule_conflicts(
    section_id: str,
    start_time: str,
    duration_minutes: int
):
    """Check for scheduling conflicts"""
    print(f"[Mock Scheduler] GET check conflicts for section {section_id}")
    
    # Find schedules for the section
    section_schedules = [s for s in MOCK_SCHEDULES if s["section_id"] == section_id]
    
    conflicts = []
    proposed_start = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
    proposed_end = proposed_start + timedelta(minutes=duration_minutes)
    
    for schedule in section_schedules:
        # Check if there's time overlap
        sched_hour, sched_minute = map(int, schedule["start_time"].split(":"))
        sched_start = proposed_start.replace(hour=sched_hour, minute=sched_minute)
        sched_end = sched_start + timedelta(minutes=schedule["duration_minutes"])
        
        if (proposed_start < sched_end and proposed_end > sched_start):
            conflicts.append({
                "schedule_id": schedule["schedule_id"],
                "schedule_name": schedule["name"],
                "conflict_type": "time_overlap",
                "existing_time": f"{schedule['start_time']} - {sched_end.strftime('%H:%M')}",
                "severity": "high"
            })
    
    return {
        "has_conflicts": len(conflicts) > 0,
        "conflict_count": len(conflicts),
        "conflicts": conflicts,
        "recommendation": "Adjust timing to avoid conflicts" if conflicts else "No conflicts found"
    }

@router.get("/api/v1/schedules/calendar/{section_id}")
async def get_schedule_calendar(
    section_id: str,
    year: int = Query(datetime.utcnow().year),
    month: int = Query(datetime.utcnow().month)
):
    """Get calendar view of schedules for a section"""
    print(f"[Mock Scheduler] GET calendar for section {section_id}, {year}-{month}")
    
    # Get schedules for section
    section_schedules = [s for s in MOCK_SCHEDULES if s["section_id"] == section_id]
    
    # Generate calendar data
    calendar_data = []
    days_in_month = 31 if month in [1, 3, 5, 7, 8, 10, 12] else 30 if month in [4, 6, 9, 11] else 28
    
    for day in range(1, days_in_month + 1):
        date = datetime(year, month, day)
        day_schedules = []
        
        for schedule in section_schedules:
            if date.isoweekday() in schedule.get("days_of_week", []):
                day_schedules.append({
                    "schedule_id": schedule["schedule_id"],
                    "name": schedule["name"],
                    "time": schedule["start_time"],
                    "duration": schedule["duration_minutes"],
                    "type": schedule["type"]
                })
        
        calendar_data.append({
            "date": date.date().isoformat(),
            "day_of_week": date.strftime("%A"),
            "schedules": day_schedules
        })
    
    return {
        "section_id": section_id,
        "year": year,
        "month": month,
        "calendar": calendar_data
    }