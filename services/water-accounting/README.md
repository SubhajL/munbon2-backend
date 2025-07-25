# Water Accounting Service

Section-level water delivery tracking and efficiency monitoring for the Munbon Irrigation System.

## Overview

The Water Accounting Service (Task 63) provides comprehensive tracking of water delivery, losses, and efficiency at the section level (50-200 hectares). It accounts for gravity-fed distribution constraints and helps build trust with farmers through accurate accounting.

## Key Features

### 1. Volume Integration
- Integrates flow rate measurements over time to calculate delivered volumes
- Supports multiple integration methods (trapezoidal, Simpson's, rectangular)
- Validates data quality and identifies gaps or outliers
- Provides cumulative volume tracking at configurable intervals

### 2. Loss Calculation
- **Seepage losses**: Based on canal type and characteristics
- **Evaporation losses**: Using simplified Penman equation with environmental factors
- **Operational losses**: Spills, gate leakage, and overflow
- Uncertainty estimation with confidence intervals
- Model calibration based on measured data

### 3. Efficiency Metrics
- **Delivery efficiency**: Water reaching section / Water released at gate
- **Application efficiency**: Water consumed by crop / Water applied to field
- **Overall efficiency**: Combined system performance
- Performance classification and benchmarking
- Trend analysis and improvement recommendations

### 4. Deficit Tracking
- Tracks water deficits by section and week
- Stress level assessment (none, mild, moderate, severe)
- Yield impact estimation based on deficit timing
- Carry-forward management (up to 4 weeks)
- Recovery plan generation for deficit compensation

## API Endpoints

### Accounting
- `GET /api/v1/accounting/section/{section_id}` - Get section accounting status
- `GET /api/v1/accounting/sections` - List all sections with filters
- `GET /api/v1/accounting/balance/{section_id}` - Water balance over time period

### Delivery
- `POST /api/v1/delivery/complete` - Process completed delivery
- `GET /api/v1/delivery/status/{delivery_id}` - Get delivery status
- `POST /api/v1/delivery/validate-flow-data` - Validate flow readings

### Efficiency
- `GET /api/v1/efficiency/report` - Generate efficiency report
- `GET /api/v1/efficiency/trends/{section_id}` - Efficiency trends
- `GET /api/v1/efficiency/benchmarks` - System benchmarks
- `POST /api/v1/efficiency/calculate-losses` - Calculate transit losses

### Deficits
- `GET /api/v1/deficits/week/{week}/{year}` - Weekly deficit summary
- `POST /api/v1/deficits/update` - Update deficit tracking
- `GET /api/v1/deficits/carry-forward/{section_id}` - Carry-forward status
- `POST /api/v1/deficits/recovery-plan` - Generate recovery plan
- `GET /api/v1/deficits/stress-assessment` - System-wide stress assessment

## Running the Service

### Local Development

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

3. Run the service:
```bash
python -m uvicorn src.main:app --reload --port 3024
```

### Docker

```bash
docker-compose up -d
```

### Testing

Run the integration test:
```bash
python test_integration.py
```

## Database Schema

### PostgreSQL (Metadata)
- **sections**: Irrigation section information
- **section_metrics**: Current performance metrics
- **water_deliveries**: Delivery records
- **efficiency_records**: Efficiency calculations
- **deficit_records**: Weekly deficit tracking
- **deficit_carryforward**: Active deficit management
- **transit_losses**: Detailed loss breakdowns

### TimescaleDB (Time-series)
- **flow_measurements**: High-frequency flow rate data
- **hourly_flow_stats**: Continuous aggregate for performance

## Integration Points

- **Flow Monitoring (Port 3016)**: Receives flow rate data
- **Scheduler (Port 3017)**: Gets delivery schedules
- **GIS Service (Port 3018)**: Reports deficits for next cycle planning

## Key Calculations

### Volume Integration
```
Volume = ∫(Flow Rate × dt)
```

### Transit Loss
```
Total Loss = Seepage + Evaporation + Operational
Seepage = Volume × Seepage_Rate × Canal_Length × Time_Factor
```

### Efficiency
```
Delivery Efficiency = Section Inflow / Gate Outflow
Application Efficiency = Water Consumed / Water Applied
Overall Efficiency = Delivery × Application
```

### Deficit
```
Deficit = Water Demand - Water Delivered
Stress Level = f(Deficit Percentage)
Priority Score = f(Deficit Amount, Age, Stress Level)
```

## Configuration

Key settings in `.env`:
- `DEFAULT_SEEPAGE_RATE`: Base seepage rate (default: 2% per km)
- `DEFAULT_EVAPORATION_RATE`: Base evaporation rate (default: 0.5% per hour)
- `MINIMUM_EFFICIENCY_THRESHOLD`: Target efficiency (default: 70%)
- `DEFICIT_CARRY_FORWARD_WEEKS`: Deficit memory (default: 4 weeks)

## Monitoring

Prometheus metrics available at `/metrics`:
- Request counts and durations
- Delivery completions processed
- Efficiency reports generated
- Custom business metrics

## Future Enhancements

1. Machine learning for loss prediction
2. Real-time efficiency alerts
3. Mobile app integration for farmers
4. Satellite imagery for validation
5. Advanced deficit forecasting