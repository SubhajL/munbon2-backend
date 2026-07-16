# Water Control BFF Service

Backend-for-Frontend service for real-time water control operations, gate management, and integration with SCADA systems.

## Overview

The Water Control BFF Service acts as the central orchestrator for water control operations in the Munbon irrigation system. It:

1. **Integrates with Core Services** - Fetches water demand calculations from Flow Monitoring, Gravity Optimizer, and Scheduled Field Operations
2. **Controls Automatic Gates** - Sends gate level commands to SCADA system via MS SQL database
3. **Manages Manual Gates** - Generates job orders for field teams with specific instructions
4. **Provides Real-time Updates** - WebSocket subscriptions for gate status and command updates

## Key Features

### 1. Automatic Gate Control

- Supports 18 automatic gates with predefined L1-L4 levels
- Cumulative level calculation (e.g., Level 3 = L1 + L2 + L3)
- Direct SCADA integration via `tb_gatelevel_command` table
- Command status tracking with 1-minute check intervals

### 2. Manual Gate Management

- Job order generation with gate location and zone information
- Opening/closing time specifications
- Step-by-step instructions for field operators
- Safety checks and precautions

### 3. Integration with Core Services

- Flow Monitoring Service (port 3044)
- Gravity Optimizer Service (port 3015)
- Scheduled Field Operations (port 3017)
- Water Level Service (port 3008)
- Alert Management Service (port 3032)

## Environment

`water-control-data.service.js` reads its PostgreSQL connection from `PG_*` env vars.
**`PG_PASSWORD` has no default** (SEC remediation: the previous hardcoded credential
leaked and was removed) — the service fails closed at construction without it.

```bash
PG_HOST=localhost        # default: 43.208.201.191
PG_PORT=5432             # default: 5432
PG_DATABASE=munbon_dev   # default: munbon_dev
PG_USER=postgres         # default: postgres
PG_PASSWORD=<required — no default>
```

## Gate Configuration

Automatic gates are configured in `/src/config/gate-levels.json`:

```json
{
  "RMC1": {
    "station_code": "M(0,0; 2,0)",
    "alias": "RMC1",
    "levels": {
      "l1": 0.0,
      "l2": 15.0,
      "l3": 14.0,
      "l4": 9.0
    },
    "cumulative_levels": {
      "level_1": 0.0,
      "level_2": 15.0,
      "level_3": 29.0,
      "level_4": 38.0
    }
  }
}
```

## API Endpoints

### GraphQL Endpoint

- URL: `http://localhost:4003/graphql`
- WebSocket: `ws://localhost:4103/graphql/ws`

### Key Operations

#### 1. Control Automatic Gate

```graphql
mutation {
  controlAutomaticGate(
    input: {
      gateName: "RMC1"
      targetLevel: 2
      reason: "Water demand adjustment"
    }
  ) {
    commandId
    scadaCommandId
    gateLevel
    status
  }
}
```

#### 2. Create Manual Gate Job Order

```graphql
mutation {
  createManualGateJobOrder(
    input: {
      operatorName: "Field Team Zone 1"
      gates: [
        {
          gateName: "Manual-Gate-01"
          location: "LMC Canal km 5+200"
          zone: 1
          targetHeight: 50
          openTime: "08:00"
          closeTime: "16:00"
        }
      ]
    }
  ) {
    id
    gates {
      instructions
    }
  }
}
```

## SCADA Integration

The service writes gate commands to MS SQL Server database:

- **Server**: moonup.hopto.org:1433
- **Database**: db_scada
- **Table**: tb_gatelevel_command

Command structure:

```sql
INSERT INTO tb_gatelevel_command (
  gate_name,      -- Gate alias (e.g., "RMC1")
  gate_level,     -- Cumulative height in cm
  startdatetime,  -- When to execute
  completestatus  -- 0=pending, 1=completed
)
```

## Installation & Setup

1. Install dependencies:

```bash
npm install
```

2. Configure environment:

```bash
cp .env.example .env
# Edit .env with your database credentials
```

3. Start the service:

```bash
npm start
# or for development
npm run dev
```

## Testing

Run the test suite:

```bash
node test/test-wc-bff.js
```

## Environment Variables

Key configuration in `.env`:

```bash
# SCADA Database
SCADA_DB_HOST=moonup.hopto.org
SCADA_DB_PORT=1433
SCADA_DB_NAME=db_scada
SCADA_DB_USER=sa
SCADA_DB_PASSWORD=your_password

# Internal Services
FLOW_MONITORING_URL=http://localhost:3044
GRAVITY_OPTIMIZER_URL=http://localhost:3015
```

## Architecture

```
┌─────────────────┐     ┌──────────────────┐
│   Frontend      │────▶│  WC BFF Service  │
└─────────────────┘     └────────┬─────────┘
                                 │
                    ┌────────────┴────────────┐
                    │                         │
              ┌─────▼─────┐            ┌─────▼─────┐
              │   SCADA   │            │   Core    │
              │ Database  │            │ Services  │
              └───────────┘            └───────────┘
```

## Safety Features

- Gate opening rate limits (max 10% per minute)
- Water level safety thresholds
- Emergency stop functionality
- Command timeout monitoring
- Operator authentication support

## Troubleshooting

1. **SCADA Connection Issues**
   - Check MS SQL connection settings
   - Verify network connectivity to moonup.hopto.org
   - Ensure database credentials are correct

2. **Service Integration Failures**
   - Check if core services are running
   - Verify service URLs in .env
   - Check network connectivity

3. **Gate Level Calculations**
   - Verify gate configuration in gate-levels.json
   - Check cumulative level calculations
   - Ensure gate alias matches SCADA expectations
