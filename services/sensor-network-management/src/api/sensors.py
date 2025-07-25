from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import List, Optional
from datetime import datetime

from db import get_db
from models.sensor import Sensor, SensorDB, SensorUpdate, SensorStatus, SensorType
from services.sensor_tracker import SensorTracker

router = APIRouter()

@router.get("/mobile/status", response_model=List[Sensor])
async def get_mobile_sensors_status(
    sensor_type: Optional[SensorType] = None,
    db: AsyncSession = Depends(get_db)
):
    """Get status of all mobile sensors"""
    query = select(SensorDB)
    if sensor_type:
        query = query.where(SensorDB.type == sensor_type)
    
    result = await db.execute(query)
    sensors = result.scalars().all()
    
    return [Sensor.model_validate(sensor) for sensor in sensors]

@router.get("/{sensor_id}", response_model=Sensor)
async def get_sensor_details(
    sensor_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get detailed information about a specific sensor"""
    result = await db.execute(
        select(SensorDB).where(SensorDB.id == sensor_id)
    )
    sensor = result.scalar_one_or_none()
    
    if not sensor:
        raise HTTPException(status_code=404, detail="Sensor not found")
    
    return Sensor.model_validate(sensor)

@router.put("/{sensor_id}", response_model=Sensor)
async def update_sensor(
    sensor_id: str,
    sensor_update: SensorUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update sensor information"""
    # Check if sensor exists
    result = await db.execute(
        select(SensorDB).where(SensorDB.id == sensor_id)
    )
    sensor = result.scalar_one_or_none()
    
    if not sensor:
        raise HTTPException(status_code=404, detail="Sensor not found")
    
    # Update fields
    update_data = sensor_update.model_dump(exclude_unset=True)
    update_data["updated_at"] = datetime.utcnow()
    
    await db.execute(
        update(SensorDB).where(SensorDB.id == sensor_id).values(**update_data)
    )
    await db.commit()
    
    # Get updated sensor
    result = await db.execute(
        select(SensorDB).where(SensorDB.id == sensor_id)
    )
    updated_sensor = result.scalar_one()
    
    return Sensor.model_validate(updated_sensor)

@router.get("/battery/low", response_model=List[Sensor])
async def get_low_battery_sensors(
    threshold: float = 20.0,
    db: AsyncSession = Depends(get_db)
):
    """Get sensors with low battery"""
    result = await db.execute(
        select(SensorDB).where(SensorDB.battery_level < threshold)
    )
    sensors = result.scalars().all()
    
    return [Sensor.model_validate(sensor) for sensor in sensors]

@router.get("/status/{status}", response_model=List[Sensor])
async def get_sensors_by_status(
    status: SensorStatus,
    db: AsyncSession = Depends(get_db)
):
    """Get sensors by status"""
    result = await db.execute(
        select(SensorDB).where(SensorDB.status == status)
    )
    sensors = result.scalars().all()
    
    return [Sensor.model_validate(sensor) for sensor in sensors]

@router.post("/register", response_model=Sensor)
async def register_sensor(
    sensor: Sensor,
    db: AsyncSession = Depends(get_db)
):
    """Register a new sensor"""
    # Check if sensor ID already exists
    result = await db.execute(
        select(SensorDB).where(SensorDB.id == sensor.id)
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        raise HTTPException(status_code=400, detail="Sensor ID already exists")
    
    # Create new sensor
    db_sensor = SensorDB(**sensor.model_dump())
    db.add(db_sensor)
    await db.commit()
    
    return Sensor.model_validate(db_sensor)

@router.get("/section/{section_id}", response_model=List[Sensor])
async def get_sensors_in_section(
    section_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get all sensors currently in a specific section"""
    result = await db.execute(
        select(SensorDB).where(SensorDB.current_section_id == section_id)
    )
    sensors = result.scalars().all()
    
    return [Sensor.model_validate(sensor) for sensor in sensors]