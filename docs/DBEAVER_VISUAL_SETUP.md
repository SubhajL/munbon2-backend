# DBeaver Visual Setup Guide

## Step-by-Step Connection Setup

### For PostgreSQL (Port 5432)

1. **Open DBeaver** → Click the plug icon 🔌 (New Database Connection)

2. **Select Database Type**
   ```
   Choose: PostgreSQL
   Click: Next >
   ```

3. **Main Tab - Connection Settings**
   ```
   Server Host: localhost
   Port: 5432
   Database: munbon_dev
   Username: postgres
   Password: postgres
   
   ☑️ Save password
   ```

4. **Click "Test Connection..."**
   - If prompted to download driver → Click "Download"
   - Should see: "Connected (XXms)"

5. **General Tab (Optional)**
   ```
   Connection name: Munbon PostgreSQL (PostGIS)
   ```

6. **Click "Finish"**

### For TimescaleDB (Port 5433)

1. **New Connection** → Select "PostgreSQL" again

2. **Main Tab - Connection Settings**
   ```
   Server Host: localhost
   Port: 5433  ⚠️ DIFFERENT PORT!
   Database: munbon_timescale
   Username: postgres
   Password: postgres
   
   ☑️ Save password
   ```

3. **General Tab**
   ```
   Connection name: Munbon TimescaleDB
   ```

4. **Test & Finish**

## What You Should See

### After Connecting to PostgreSQL (5432):
```
📁 Munbon PostgreSQL (PostGIS)
  📁 munbon_dev
    📁 Schemas
      📁 public
        📁 Tables
        📁 Views
        📁 Functions
          📄 PostGIS functions (ST_*)
```

### After Connecting to TimescaleDB (5433):
```
📁 Munbon TimescaleDB
  📁 munbon_timescale
    📁 Schemas
      📁 public
        📁 Tables
          📄 (hypertables will appear here)
      📁 _timescaledb_internal
        📄 (chunks and internal tables)
```

## Quick SQL Tests

### Test PostgreSQL/PostGIS:
```sql
-- Check PostGIS
SELECT postgis_version();

-- Check connection
SELECT current_database(), current_user, version();
```

### Test TimescaleDB:
```sql
-- Check TimescaleDB
SELECT extversion FROM pg_extension WHERE extname = 'timescaledb';

-- List hypertables
SELECT * FROM timescaledb_information.hypertables;
```

## Common Issues

### ❌ "Connection refused"
- Run: `docker compose ps`
- If not running: `docker compose up -d postgres timescaledb`

### ❌ "FATAL: password authentication failed"
- Double-check password is `postgres`
- Verify correct port (5432 vs 5433)

### ❌ "FATAL: database 'xxx' does not exist"
- For PostgreSQL: Use `munbon_dev`
- For TimescaleDB: Use `munbon_timescale` or `sensor_data`

## Pro Tips

1. **Color Code Connections**
   - Right-click connection → Edit → General tab
   - Set different colors for dev/staging/prod

2. **SQL Templates**
   - Window → Preferences → SQL Editor → Templates
   - Create snippets for common queries

3. **Export Results**
   - Right-click query results → Export
   - Choose CSV, JSON, SQL INSERT, etc.

4. **Database Navigator Filter**
   - Right-click in navigator → Configure
   - Hide system schemas/tables for cleaner view