"""
Scheduler Service with EC2 PostgreSQL Connection
Works without heavy optimization dependencies
"""

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import os
import json
import asyncpg
import redis.asyncio as aioredis
from contextlib import asynccontextmanager
import urllib.parse

# Configuration
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "43.209.22.250")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "P@ssw0rd123!")
POSTGRES_DB = os.getenv("POSTGRES_DB", "munbon_dev")

# Redis configuration
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

# URL encode the password to handle special characters
encoded_password = urllib.parse.quote_plus(POSTGRES_PASSWORD)
DATABASE_URL = f"postgresql://{POSTGRES_USER}:{encoded_password}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"

# Global connections
db_pool = None
redis_client = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global db_pool, redis_client
    
    print(f"Connecting to PostgreSQL at {POSTGRES_HOST}:{POSTGRES_PORT}")
    try:
        # Create database connection pool
        db_pool = await asyncpg.create_pool(
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            database=POSTGRES_DB,
            min_size=5,
            max_size=20,
            command_timeout=60
        )
        print("✅ PostgreSQL connected successfully")
        
        # Test connection and create schema if needed
        async with db_pool.acquire() as conn:
            # Check if scheduler schema exists
            schema_exists = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM information_schema.schemata WHERE schema_name = 'scheduler')"
            )
            if not schema_exists:
                print("Creating scheduler schema...")
                await conn.execute("CREATE SCHEMA IF NOT EXISTS scheduler")
                print("✅ Schema created")
            
            # Check tables
            tables = await conn.fetch(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'scheduler'"
            )
            print(f"Found {len(tables)} tables in scheduler schema")
    
    except Exception as e:
        print(f"❌ PostgreSQL connection failed: {str(e)}")
        print(f"Connection details: {POSTGRES_USER}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}")
    
    # Connect to Redis
    try:
        redis_client = await aioredis.create_redis_pool(
            f"redis://{REDIS_HOST}:{REDIS_PORT}",
            encoding="utf-8"
        )
        print("✅ Redis connected successfully")
    except Exception as e:
        print(f"❌ Redis connection failed: {str(e)}")
        redis_client = None
    
    yield
    
    # Shutdown
    if db_pool:
        await db_pool.close()
    if redis_client:
        redis_client.close()
        await redis_client.wait_closed()

# Create FastAPI app
app = FastAPI(
    title="Munbon Scheduler Service",
    description="Weekly batch scheduler for irrigation operations - EC2 Connected",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

# Database dependency
async def get_db():
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database connection not available")
    async with db_pool.acquire() as conn:
        yield conn

# Root endpoints
@app.get("/")
async def root():
    return {
        "service": "Munbon Scheduler Service",
        "version": "1.0.0",
        "status": "operational",
        "database": "EC2 PostgreSQL",
        "docs": "/docs"
    }

@app.get("/health")
async def health_check():
    health_status = {
        "status": "healthy",
        "service": "scheduler",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "dependencies": {}
    }
    
    # Check PostgreSQL
    try:
        if db_pool:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
                health_status["dependencies"]["postgresql"] = {
                    "status": "connected",
                    "host": POSTGRES_HOST,
                    "port": POSTGRES_PORT
                }
        else:
            health_status["dependencies"]["postgresql"] = {"status": "disconnected"}
            health_status["status"] = "degraded"
    except Exception as e:
        health_status["dependencies"]["postgresql"] = {
            "status": "error",
            "error": str(e)
        }
        health_status["status"] = "unhealthy"
    
    # Check Redis
    try:
        if redis_client:
            await redis_client.ping()
            health_status["dependencies"]["redis"] = {
                "status": "connected",
                "host": REDIS_HOST,
                "port": REDIS_PORT
            }
        else:
            health_status["dependencies"]["redis"] = {"status": "disconnected"}
    except Exception as e:
        health_status["dependencies"]["redis"] = {
            "status": "error",
            "error": str(e)
        }
    
    return health_status

@app.get("/ready")
async def readiness_check():
    if not db_pool:
        raise HTTPException(status_code=503, detail="Service not ready")
    return {
        "status": "ready",
        "database": "connected",
        "redis": "connected" if redis_client else "disconnected"
    }

# Schedule Management Endpoints
@app.get("/api/v1/schedule/week/{week}")
async def get_weekly_schedule(week: str, conn: asyncpg.Connection = Depends(get_db)):
    # Try to get from database first
    schedule = await conn.fetchrow(
        """
        SELECT * FROM scheduler.weekly_schedules 
        WHERE week = $1
        """,
        week
    )
    
    if schedule:
        # Get operations for this schedule
        operations = await conn.fetch(
            """
            SELECT * FROM scheduler.schedule_operations
            WHERE schedule_id = $1
            ORDER BY scheduled_time
            """,
            schedule['id']
        )
        
        return {
            "id": schedule['id'],
            "week": schedule['week'],
            "status": schedule['status'],
            "operations": [dict(op) for op in operations],
            "total_volume_m3": float(schedule['total_volume_m3']) if schedule['total_volume_m3'] else 0,
            "optimization_score": float(schedule['optimization_score']) if schedule['optimization_score'] else 0,
            "created_at": schedule['created_at'].isoformat() if schedule['created_at'] else None
        }
    
    # Return mock data if not found
    return {
        "week": week,
        "status": "draft",
        "operations": [],
        "total_volume_m3": 0,
        "optimization_score": 0
    }

@app.post("/api/v1/schedule/week/{week}/generate")
async def generate_weekly_schedule(week: str, conn: asyncpg.Connection = Depends(get_db)):
    try:
        # Create new schedule
        schedule_id = await conn.fetchval(
            """
            INSERT INTO scheduler.weekly_schedules (week, status, total_volume_m3, optimization_score)
            VALUES ($1, $2, $3, $4)
            RETURNING id
            """,
            week, "generated", 125000.0, 0.85
        )
        
        # Add some sample operations
        await conn.execute(
            """
            INSERT INTO scheduler.schedule_operations 
            (schedule_id, gate_id, action, target_opening_m, scheduled_time, team_assigned)
            VALUES 
            ($1, 'Source->M(0,0)', 'open', 2.0, $2, 'Team_A'),
            ($1, 'M(0,0)->M(0,2)', 'adjust', 1.5, $3, 'Team_A')
            """,
            schedule_id,
            datetime.utcnow() + timedelta(days=2),
            datetime.utcnow() + timedelta(days=4)
        )
        
        return {
            "schedule_id": schedule_id,
            "status": "generated",
            "message": "Schedule generated successfully"
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate schedule: {str(e)}")

@app.put("/api/v1/schedule/week/{week}/status")
async def update_schedule_status(week: str, status: str, conn: asyncpg.Connection = Depends(get_db)):
    try:
        result = await conn.execute(
            """
            UPDATE scheduler.weekly_schedules 
            SET status = $2, updated_at = NOW()
            WHERE week = $1
            """,
            week, status
        )
        
        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail="Schedule not found")
        
        return {"week": week, "status": status, "updated": True}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update status: {str(e)}")

# Field Operations Endpoints
@app.get("/api/v1/field-ops/teams/status")
async def get_teams_status(conn: asyncpg.Connection = Depends(get_db)):
    teams = await conn.fetch(
        """
        SELECT * FROM scheduler.field_teams
        WHERE is_active = true
        """
    )
    
    return {
        "teams": [dict(team) for team in teams],
        "active_teams": len(teams),
        "timestamp": datetime.utcnow().isoformat()
    }

@app.post("/api/v1/field-ops/teams/{team}/location")
async def update_team_location(team: str, location: TeamLocation, conn: asyncpg.Connection = Depends(get_db)):
    try:
        # Update team location
        result = await conn.execute(
            """
            UPDATE scheduler.field_teams
            SET current_lat = $2, current_lon = $3, last_update = NOW()
            WHERE team_code = $1
            """,
            team, location.lat, location.lon
        )
        
        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail="Team not found")
        
        # Also log in assignments table if team is on active assignment
        await conn.execute(
            """
            UPDATE scheduler.team_assignments
            SET actual_lat = $2, actual_lon = $3
            WHERE team_code = $1 AND status = 'in_progress'
            """,
            team, location.lat, location.lon
        )
        
        return {"team": team, "location_updated": True}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update location: {str(e)}")

# Demand Processing Endpoints
@app.post("/api/v1/scheduler/demands")
async def submit_demands(demands: DemandSubmission, conn: asyncpg.Connection = Depends(get_db)):
    try:
        # Store demands in database
        total_demand = sum(s.get("demand_m3", 0) for s in demands.sections)
        
        demand_id = await conn.fetchval(
            """
            INSERT INTO scheduler.weekly_demands 
            (week, section_demands, total_demand_m3, status)
            VALUES ($1, $2, $3, $4)
            RETURNING id
            """,
            demands.week,
            json.dumps(demands.sections),
            total_demand,
            "submitted"
        )
        
        return {
            "demand_id": demand_id,
            "status": "processing",
            "total_demand_m3": total_demand,
            "estimated_completion": (datetime.utcnow() + timedelta(minutes=5)).isoformat()
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to submit demands: {str(e)}")

# Database info endpoint
@app.get("/api/v1/database/info")
async def get_database_info(conn: asyncpg.Connection = Depends(get_db)):
    # Get PostgreSQL version
    version = await conn.fetchval("SELECT version()")
    
    # Get schema tables
    tables = await conn.fetch(
        """
        SELECT table_name, 
               (SELECT COUNT(*) FROM scheduler.weekly_schedules) as schedules_count,
               (SELECT COUNT(*) FROM scheduler.field_teams) as teams_count
        FROM information_schema.tables 
        WHERE table_schema = 'scheduler'
        """
    )
    
    return {
        "database": {
            "host": POSTGRES_HOST,
            "port": POSTGRES_PORT,
            "name": POSTGRES_DB,
            "version": version,
            "schema": "scheduler"
        },
        "tables": [t['table_name'] for t in tables],
        "counts": {
            "schedules": tables[0]['schedules_count'] if tables else 0,
            "teams": tables[0]['teams_count'] if tables else 0
        }
    }

# Run the application
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("SERVICE_PORT", "3021"))
    uvicorn.run(app, host="0.0.0.0", port=port)