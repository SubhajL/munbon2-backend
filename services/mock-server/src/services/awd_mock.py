"""
AWD Service Mock Endpoints
Provides mock AWD (Alternate Wetting and Drying) control and monitoring
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Dict, Optional, List
from datetime import datetime, date, timedelta
import random

from data import get_mock_data_manager

router = APIRouter()
mock_data = get_mock_data_manager()


# Request/Response Models
class AWDControlRequest(BaseModel):
    sectionId: str
    action: str  # "enable", "disable", "adjust"
    targetMoisturePercent: Optional[float] = None
    dryingDays: Optional[int] = None
    autoControl: bool = True


class AWDThresholdUpdate(BaseModel):
    sectionId: str
    criticalLow: float
    reIrrigationPoint: float
    saturatedLevel: float


class AWDScheduleRequest(BaseModel):
    sectionId: str
    scheduleType: str  # "auto", "manual"
    dryingPeriodDays: int = 5
    wettingPeriodDays: int = 3


# Endpoints
@router.get("/api/v1/awd/plots/{plot_id}/status")
async def get_plot_awd_status(plot_id: str):
    """Get AWD status for a specific plot"""
    
    # Mock AWD status for plot
    is_active = random.choice([True, True, False])  # 2/3 chance of being active
    
    if not is_active:
        return {
            "plot_id": plot_id,
            "is_active": False,
            "irrigation_interval_days": 0,
            "soil_moisture_threshold": 0,
            "ponding_depth_cm": 0
        }
    
    # Generate AWD parameters
    irrigation_interval = random.choice([5, 7, 10])
    
    return {
        "plot_id": plot_id,
        "is_active": True,
        "irrigation_interval_days": irrigation_interval,
        "soil_moisture_threshold": random.uniform(0.6, 0.8),
        "ponding_depth_cm": random.choice([3, 5, 7]),
        "current_moisture_percent": random.uniform(20, 80),
        "days_since_irrigation": random.randint(0, irrigation_interval),
        "next_irrigation_date": (datetime.now() + timedelta(days=random.randint(1, 5))).date().isoformat(),
        "water_savings_estimate": {
            "percent": 15 if irrigation_interval <= 5 else (25 if irrigation_interval <= 7 else 30),
            "volume_m3": random.uniform(100, 500)
        }
    }


@router.get("/api/v1/awd/status/{section_id}")
async def get_awd_status(section_id: str):
    """Get current AWD status for a section"""
    
    section = mock_data.sections.get(section_id)
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")
    
    # Only rice fields can have AWD
    if section.get('crop_type') != 'rice':
        return {
            "status": "success",
            "data": {
                "section_id": section_id,
                "awd_applicable": False,
                "reason": "AWD only applicable for rice cultivation"
            }
        }
    
    awd_status = mock_data.awd_status.get(section_id)
    if not awd_status:
        # Create default AWD status
        awd_status = {
            "section_id": section_id,
            "awd_enabled": False,
            "current_phase": "monitoring",
            "moisture_level_percent": random.uniform(40, 60),
            "days_since_last_irrigation": 0,
            "recommended_action": "monitor",
            "water_savings_percent": 0,
            "last_updated": datetime.utcnow().isoformat()
        }
        mock_data.awd_status[section_id] = awd_status
    
    # Add sensor data if available
    sensor_data = []
    if section_id in mock_data.sensor_readings:
        recent_readings = sorted(
            mock_data.sensor_readings[section_id][-10:],
            key=lambda x: x['reading_timestamp'],
            reverse=True
        )
        
        for reading in recent_readings[:5]:
            sensor_data.append({
                "sensor_id": f"AWD-{section_id[-4:]}",
                "moisture_percent": random.uniform(20, 80),
                "depth_cm": 15,
                "timestamp": reading['reading_timestamp'],
                "quality": "good"
            })
    
    # Calculate recommendations
    moisture = awd_status['moisture_level_percent']
    if moisture < 20:
        recommendation = "irrigate_immediately"
        urgency = "critical"
    elif moisture < 30:
        recommendation = "irrigate_within_24h"
        urgency = "high"
    elif moisture < 40:
        recommendation = "plan_irrigation"
        urgency = "medium"
    else:
        recommendation = "continue_monitoring"
        urgency = "low"
    
    return {
        "status": "success",
        "data": {
            **awd_status,
            "thresholds": {
                "critical_low": 20,
                "re_irrigation": 30,
                "field_capacity": 70,
                "saturated": 100
            },
            "recommendation": {
                "action": recommendation,
                "urgency": urgency,
                "estimated_days_until_irrigation": max(0, int((moisture - 30) / 5))
            },
            "sensor_readings": sensor_data,
            "growth_stage": _get_growth_stage_for_awd(section_id),
            "water_savings": {
                "current_cycle_percent": random.uniform(15, 25),
                "season_total_percent": random.uniform(20, 30),
                "volume_saved_m3": random.uniform(500, 2000)
            }
        }
    }


@router.post("/api/v1/awd/control")
async def control_awd(request: AWDControlRequest):
    """Control AWD system for a section"""
    
    section = mock_data.sections.get(request.sectionId)
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")
    
    if section.get('crop_type') != 'rice':
        raise HTTPException(
            status_code=400, 
            detail="AWD control only available for rice fields"
        )
    
    # Get or create AWD status
    awd_status = mock_data.awd_status.get(request.sectionId, {
        "section_id": request.sectionId,
        "awd_enabled": False,
        "current_phase": "monitoring",
        "moisture_level_percent": 50,
        "days_since_last_irrigation": 0,
        "recommended_action": "monitor",
        "water_savings_percent": 0
    })
    
    # Process control action
    if request.action == "enable":
        awd_status["awd_enabled"] = True
        awd_status["current_phase"] = "drying"
        awd_status["auto_control"] = request.autoControl
        message = "AWD system enabled"
    elif request.action == "disable":
        awd_status["awd_enabled"] = False
        awd_status["current_phase"] = "monitoring"
        message = "AWD system disabled"
    elif request.action == "adjust":
        if request.targetMoisturePercent:
            awd_status["target_moisture"] = request.targetMoisturePercent
        if request.dryingDays:
            awd_status["drying_period_days"] = request.dryingDays
        message = "AWD parameters adjusted"
    else:
        raise HTTPException(status_code=400, detail="Invalid action")
    
    awd_status["last_updated"] = datetime.utcnow().isoformat()
    mock_data.awd_status[request.sectionId] = awd_status
    
    return {
        "status": "success",
        "data": {
            "section_id": request.sectionId,
            "action": request.action,
            "message": message,
            "current_status": awd_status,
            "estimated_water_savings": _calculate_water_savings(awd_status)
        }
    }


@router.get("/api/v1/awd/recommendations")
async def get_awd_recommendations(
    zone: Optional[int] = Query(None),
    onlyEnabled: bool = Query(False),
    urgency: Optional[str] = Query(None)
):
    """Get AWD recommendations for multiple sections"""
    
    recommendations = []
    
    for section_id, section in mock_data.sections.items():
        # Filter by zone if specified
        if zone and section['zone'] != zone:
            continue
        
        # Only rice fields
        if section.get('crop_type') != 'rice':
            continue
        
        # Get AWD status
        awd_status = mock_data.awd_status.get(section_id)
        
        # Filter by enabled status
        if onlyEnabled and (not awd_status or not awd_status.get('awd_enabled')):
            continue
        
        # Create recommendation
        moisture = awd_status.get('moisture_level_percent', 50) if awd_status else 50
        
        if moisture < 20:
            rec_urgency = "critical"
            action = "irrigate_immediately"
        elif moisture < 30:
            rec_urgency = "high"
            action = "irrigate_within_24h"
        elif moisture < 40:
            rec_urgency = "medium"
            action = "plan_irrigation"
        else:
            rec_urgency = "low"
            action = "continue_monitoring"
        
        # Filter by urgency if specified
        if urgency and rec_urgency != urgency:
            continue
        
        recommendations.append({
            "section_id": section_id,
            "zone": section['zone'],
            "awd_enabled": awd_status.get('awd_enabled', False) if awd_status else False,
            "current_moisture_percent": moisture,
            "current_phase": awd_status.get('current_phase', 'monitoring') if awd_status else 'monitoring',
            "recommendation": {
                "action": action,
                "urgency": rec_urgency,
                "days_until_irrigation": max(0, int((moisture - 30) / 5))
            },
            "area_rai": section['area_rai'],
            "potential_water_savings_m3": section['area_rai'] * 1.6 * random.uniform(3, 5)
        })
    
    # Sort by urgency
    urgency_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    recommendations.sort(key=lambda x: urgency_order.get(x['recommendation']['urgency'], 4))
    
    return {
        "status": "success",
        "data": {
            "total_sections": len(recommendations),
            "recommendations": recommendations,
            "summary": {
                "critical": sum(1 for r in recommendations if r['recommendation']['urgency'] == 'critical'),
                "high": sum(1 for r in recommendations if r['recommendation']['urgency'] == 'high'),
                "medium": sum(1 for r in recommendations if r['recommendation']['urgency'] == 'medium'),
                "low": sum(1 for r in recommendations if r['recommendation']['urgency'] == 'low')
            }
        }
    }


@router.post("/api/v1/awd/thresholds")
async def update_awd_thresholds(request: AWDThresholdUpdate):
    """Update AWD thresholds for a section"""
    
    section = mock_data.sections.get(request.sectionId)
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")
    
    # Store thresholds
    thresholds_key = f"awd_thresholds_{request.sectionId}"
    mock_data.awd_status[thresholds_key] = {
        "section_id": request.sectionId,
        "critical_low": request.criticalLow,
        "re_irrigation_point": request.reIrrigationPoint,
        "saturated_level": request.saturatedLevel,
        "updated_at": datetime.utcnow().isoformat()
    }
    
    return {
        "status": "success",
        "data": {
            "section_id": request.sectionId,
            "thresholds": {
                "critical_low": request.criticalLow,
                "re_irrigation_point": request.reIrrigationPoint,
                "saturated_level": request.saturatedLevel
            },
            "message": "AWD thresholds updated successfully"
        }
    }


@router.get("/api/v1/awd/history/{section_id}")
async def get_awd_history(
    section_id: str,
    days: int = Query(7, le=30)
):
    """Get AWD history for a section"""
    
    section = mock_data.sections.get(section_id)
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")
    
    # Generate mock history
    history = []
    
    for i in range(days):
        date_val = datetime.now() - timedelta(days=days-i-1)
        base_moisture = 60 - (i * 2)  # Simulate drying
        
        # Add irrigation events
        if base_moisture < 30:
            base_moisture = 70  # Reset after irrigation
            irrigation_event = True
        else:
            irrigation_event = False
        
        history.append({
            "date": date_val.date().isoformat(),
            "avg_moisture_percent": base_moisture + random.uniform(-5, 5),
            "min_moisture_percent": base_moisture - 10,
            "max_moisture_percent": base_moisture + 10,
            "irrigation_applied": irrigation_event,
            "water_applied_m3": random.uniform(500, 800) if irrigation_event else 0,
            "phase": "wetting" if irrigation_event else "drying",
            "readings_count": random.randint(20, 30)
        })
    
    # Calculate statistics
    irrigation_events = sum(1 for h in history if h['irrigation_applied'])
    total_water = sum(h['water_applied_m3'] for h in history)
    
    return {
        "status": "success",
        "data": {
            "section_id": section_id,
            "period": {
                "start_date": history[0]['date'],
                "end_date": history[-1]['date'],
                "days": days
            },
            "history": history,
            "statistics": {
                "irrigation_events": irrigation_events,
                "total_water_applied_m3": total_water,
                "avg_drying_days": days / (irrigation_events + 1) if irrigation_events > 0 else days,
                "water_savings_percent": random.uniform(20, 30),
                "avg_moisture_percent": sum(h['avg_moisture_percent'] for h in history) / len(history)
            }
        }
    }


@router.post("/api/v1/awd/schedule")
async def create_awd_schedule(request: AWDScheduleRequest):
    """Create AWD irrigation schedule"""
    
    section = mock_data.sections.get(request.sectionId)
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")
    
    # Generate schedule
    schedule_entries = []
    current_date = datetime.now().date()
    
    for cycle in range(4):  # 4 cycles
        # Drying period
        drying_start = current_date + timedelta(days=cycle * (request.dryingPeriodDays + request.wettingPeriodDays))
        drying_end = drying_start + timedelta(days=request.dryingPeriodDays)
        
        # Irrigation event
        irrigation_date = drying_end
        
        schedule_entries.append({
            "cycle": cycle + 1,
            "drying_start": drying_start.isoformat(),
            "drying_end": drying_end.isoformat(),
            "irrigation_date": irrigation_date.isoformat(),
            "expected_moisture_at_irrigation": 25 + random.uniform(-5, 5),
            "irrigation_amount_m3": section['area_rai'] * 1.6 * random.uniform(5, 7),
            "status": "scheduled"
        })
    
    # Store schedule
    schedule_id = f"AWD-SCH-{request.sectionId}-{datetime.now().timestamp()}"
    schedule = {
        "schedule_id": schedule_id,
        "section_id": request.sectionId,
        "schedule_type": request.scheduleType,
        "drying_period_days": request.dryingPeriodDays,
        "wetting_period_days": request.wettingPeriodDays,
        "entries": schedule_entries,
        "created_at": datetime.utcnow().isoformat(),
        "status": "active"
    }
    
    return {
        "status": "success",
        "data": {
            "schedule_id": schedule_id,
            "section_id": request.sectionId,
            "schedule": schedule,
            "estimated_water_savings": {
                "per_cycle_m3": section['area_rai'] * 1.6 * 2,  # Approx 2mm saved
                "total_season_m3": section['area_rai'] * 1.6 * 2 * 4,  # 4 cycles
                "percentage": 25
            }
        }
    }


@router.get("/api/v1/awd/sensors/{section_id}")
async def get_awd_sensors(section_id: str):
    """Get AWD sensors for a section"""
    
    section = mock_data.sections.get(section_id)
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")
    
    # Generate mock sensors
    sensors = []
    sensor_count = random.randint(2, 4)
    
    for i in range(sensor_count):
        sensor_id = f"AWD-{section_id[-4:]}-{i+1}"
        sensors.append({
            "sensor_id": sensor_id,
            "type": "soil_moisture",
            "location": {
                "section_id": section_id,
                "position": f"Grid-{chr(65+i)}{i+1}",
                "depth_cm": 15,
                "coordinates": {
                    "latitude": 16.4419 + (section['zone'] * 0.01) + (i * 0.001),
                    "longitude": 102.8359 + (section['zone'] * 0.01) + (i * 0.001)
                }
            },
            "status": random.choice(["active", "active", "active", "maintenance"]),
            "battery_percent": random.randint(60, 100),
            "last_reading": {
                "moisture_percent": random.uniform(30, 70),
                "temperature_c": random.uniform(25, 35),
                "timestamp": (datetime.now() - timedelta(minutes=random.randint(5, 60))).isoformat()
            },
            "calibration": {
                "last_calibrated": (datetime.now() - timedelta(days=random.randint(30, 90))).date().isoformat(),
                "next_calibration": (datetime.now() + timedelta(days=random.randint(30, 90))).date().isoformat()
            }
        })
    
    return {
        "status": "success",
        "data": {
            "section_id": section_id,
            "sensor_count": len(sensors),
            "sensors": sensors,
            "coverage": {
                "area_per_sensor_rai": section['area_rai'] / len(sensors),
                "coverage_quality": "good" if len(sensors) >= 3 else "adequate"
            }
        }
    }


# Helper functions
def _get_growth_stage_for_awd(section_id: str) -> Dict:
    """Determine if current growth stage is suitable for AWD"""
    section = mock_data.sections.get(section_id, {})
    
    # Mock growth stage based on planting date
    if section.get('crop_type') != 'rice':
        return {"suitable_for_awd": False, "reason": "Not a rice field"}
    
    # Random stage for demonstration
    stages = [
        {"stage": "vegetative", "suitable": True, "reason": "Ideal stage for AWD"},
        {"stage": "reproductive", "suitable": False, "reason": "Critical water need period"},
        {"stage": "ripening", "suitable": True, "reason": "Can apply mild AWD"},
        {"stage": "harvest", "suitable": False, "reason": "No irrigation needed"}
    ]
    
    return random.choice(stages)


def _calculate_water_savings(awd_status: Dict) -> Dict:
    """Calculate estimated water savings from AWD"""
    if not awd_status.get('awd_enabled'):
        return {
            "current_saving_percent": 0,
            "projected_seasonal_percent": 0,
            "water_saved_m3": 0
        }
    
    # Mock calculations
    days_active = random.randint(10, 30)
    
    return {
        "current_saving_percent": random.uniform(15, 25),
        "projected_seasonal_percent": random.uniform(20, 30),
        "water_saved_m3": days_active * random.uniform(50, 150),
        "co2_reduced_kg": days_active * random.uniform(10, 30)
    }