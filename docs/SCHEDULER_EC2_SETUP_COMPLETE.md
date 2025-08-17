# Scheduler Service EC2 Setup Complete ✅

## Summary

I have successfully connected the scheduler service to the EC2 PostgreSQL database and set up all required schema components.

## EC2 Database Connection Details

- **Host**: 43.209.22.250
- **Port**: 5432
- **Database**: munbon_dev
- **User**: postgres
- **Password**: P@ssw0rd123!
- **Connection String**: `postgresql://postgres:P%40ssw0rd123%21@43.209.22.250:5432/munbon_dev`

### Important: Password Encoding
The password contains special characters that must be URL-encoded in connection strings:
- `@` → `%40`
- `!` → `%21`

## Schema Created on EC2

### Tables in `scheduler` schema:
1. **weekly_schedules** - Main schedule management
2. **schedule_operations** - Individual gate operations with day_of_week
3. **weekly_demands** - Water demand aggregation
4. **field_teams** - Team management (2 teams inserted)
5. **team_assignments** - Assignment history
6. **weather_adjustments** - Weather-based adjustments
7. **optimization_runs** - Optimization history

### Default Data:
- Team_A: Field Team Alpha (Leader: Somchai Jaidee)
- Team_B: Field Team Bravo (Leader: Prasert Suksri)

## Configuration Files Updated

### 1. `/services/scheduler/.env`
```env
POSTGRES_HOST=43.209.22.250
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=P@ssw0rd123!
POSTGRES_DB=munbon_dev
POSTGRES_URL=postgresql://postgres:P%40ssw0rd123%21@43.209.22.250:5432/munbon_dev
```

### 2. `/services/scheduler/src/main_ec2.py`
- Created EC2-compatible version with proper password encoding
- Uses asyncpg for async PostgreSQL connections
- Implements all core scheduler endpoints
- Includes health checks for PostgreSQL and Redis

## Test Results

### ✅ Database Connection Test
```bash
python3 test_ec2_connection.py
```
- Successfully connected to EC2 PostgreSQL
- Verified all 7 tables exist
- Confirmed 2 field teams loaded

### ✅ SQL Command Line Access
```bash
psql "postgresql://postgres:P%40ssw0rd123%21@43.209.22.250:5432/munbon_dev"
```

## Services Architecture

```
┌─────────────────────────┐
│   Scheduler Service     │
│     (Port 3021)         │
├─────────────────────────┤
│   - Weekly Planning     │
│   - Team Assignment     │
│   - Gate Operations     │
└──────────┬──────────────┘
           │
           ▼
┌─────────────────────────┐
│  EC2 PostgreSQL (5432)  │
│   43.209.22.250         │
├─────────────────────────┤
│ scheduler.* tables      │
│ - weekly_schedules      │
│ - schedule_operations   │
│ - field_teams           │
│ - team_assignments      │
└─────────────────────────┘
```

## Next Steps

### 1. **Deploy Scheduler to EC2**
```bash
# Build Docker image
docker build -t munbon-scheduler:latest .

# Deploy via docker-compose
docker-compose -f docker-compose.ec2.yml up -d scheduler
```

### 2. **Deploy Redis on EC2**
Currently Redis runs locally. For production:
- Add Redis service to EC2 docker-compose
- Update REDIS_HOST in .env to EC2 IP

### 3. **Complete Python Dependencies**
The full scheduler requires Python 3.11/3.12 for optimization libraries:
- ortools for optimization
- scipy for mathematical operations
- networkx for graph algorithms

### 4. **Integration Points**
- Flow Monitoring Service (port 3011)
- ROS/GIS Integration (port 3041)
- Mock Server (port 3099) for development

## Current Status

✅ **EC2 Database**: Connected and schema created
✅ **Connection Testing**: Verified with test scripts
✅ **Environment Config**: Updated for EC2
✅ **Default Data**: Teams loaded

⏳ **Pending**:
- Python dependencies (requires Python 3.11/3.12)
- Redis deployment on EC2
- Full scheduler deployment
- Mobile app implementation

The scheduler is now configured to use the EC2 PostgreSQL database. All schema and initial data have been successfully created on the EC2 instance.