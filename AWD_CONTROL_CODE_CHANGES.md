# AWD Control Service Code Changes for Database Consolidation

## Overview
The AWD Control service needs updates to support schema-based database connections when consolidating to EC2 PostgreSQL.

## Required Changes

### 1. **Database Configuration** (`src/config/database.ts`)
- Update to use `munbon_dev` database with `awd` schema for PostgreSQL
- Update to use `sensor_data` database for TimescaleDB
- Add schema configuration support
- Set search paths for connections

**Key changes:**
```typescript
// Old
database: process.env.POSTGRES_DB || 'munbon_awd',

// New
database: process.env.POSTGRES_DB || 'munbon_dev',
// Plus: SET search_path TO awd, public
```

### 2. **Schema Helper Utility** (`src/utils/schema-helper.ts`)
- New utility class to manage schema prefixes
- Handles table name mapping
- Converts queries to use proper schema prefixes

### 3. **Repository Updates**
All repository files need to update their queries:

#### **sensor.repository.ts**
- Replace `FROM awd_sensors` with `FROM awd.awd_sensors`
- Replace `FROM awd_configurations` with `FROM awd.awd_configurations`
- Replace `FROM awd_field_cycles` with `FROM awd.awd_field_cycles`
- Keep `FROM gis.water_level_measurements` as is (already prefixed)

#### **field.repository.ts** (if exists)
- Update all table references to include schema prefix

#### **irrigation.repository.ts** (if exists)
- Update all table references to include schema prefix

### 4. **Service Updates**
Update service files that directly query the database:

#### **awd-control.service.ts**
- Line 60: Update INSERT query for awd_field_cycles
- Line 361: Update SELECT query from awd_configurations
- Line 431: Update UPDATE query for awd_field_cycles
- Line 549: Update SELECT query from gis.field_attributes

### 5. **Environment Variables**
Update .env file:
```env
# Old
POSTGRES_DB=munbon_awd
TIMESCALE_DB=munbon_timeseries

# New
POSTGRES_DB=munbon_dev
POSTGRES_SCHEMA=awd
TIMESCALE_DB=sensor_data
TIMESCALE_SCHEMA=public
```

## Implementation Steps

1. **Replace database.ts**:
   ```bash
   mv src/config/database.ts src/config/database.old.ts
   mv src/config/database-updated.ts src/config/database.ts
   ```

2. **Add schema helper**:
   - The schema helper is already created at `src/utils/schema-helper.ts`

3. **Update imports in repositories**:
   ```typescript
   import { schemaHelper } from '../utils/schema-helper';
   ```

4. **Update queries**:
   - Use `schemaHelper.getTableName('table_name')` for dynamic schema prefixing
   - Or manually prefix with schema: `awd.table_name`

5. **Test the changes**:
   - Ensure all queries work with the new schema structure
   - Verify TimescaleDB hypertables are created in sensor_data

## Alternative Approach: Using Search Path

Instead of prefixing all queries, you can set the search path on the connection:

```typescript
// In database.ts, after creating the pool
await postgresPool.query('SET search_path TO awd, gis, public');
await timescalePool.query('SET search_path TO public');
```

This approach requires fewer code changes but needs careful management of the search path.

## Benefits
1. Consolidates databases from 3 instances to 1
2. Maintains data isolation through schemas
3. Simplifies deployment and maintenance
4. Reduces infrastructure costs

## Testing
After making these changes:
1. Test database connections
2. Verify all CRUD operations work
3. Check that TimescaleDB hypertables are accessible
4. Ensure GIS queries still work (cross-schema queries)