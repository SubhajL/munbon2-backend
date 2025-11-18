# Moisture Data Smoothing Implementation Guide

## Overview

This directory contains SQL scripts to implement **Approach A: Hampel Filter + Rolling Median + EMA** for smoothing moisture sensor data.

**Purpose**: Remove data quality issues (spikes, extreme values, rapid oscillations) from 12 moisture sensors (0001-0001 through 0001-0012) while preserving legitimate trends.

**Expected Results**:
- 80% reduction in spikes (>30% jumps)
- 50% reduction in standard deviation
- <2% extreme values (0% or 100%) in smoothed data

---

## Files

| File | Purpose | Runtime |
|------|---------|---------|
| `01_create_smoothed_table.sql` | Create `smoothed_moisture_readings` table and indexes | <5 sec |
| `02_profile_quality_raw.sql` | Analyze raw data quality (baseline) | ~10 sec |
| `04_backfill_smoothing_14d.sql` | Apply smoothing to past 14 days | 30-60 sec |
| `03_profile_quality_smoothed.sql` | Analyze smoothed data quality (comparison) | ~10 sec |
| `05_realtime_fn_and_trigger.sql` | (Optional) Deploy real-time smoothing | TBD |

---

## Prerequisites

1. **PostgreSQL Connection**: Access to sensor_data database
2. **psql Client**: PostgreSQL command-line tool
3. **Permissions**: CREATE TABLE, INSERT, SELECT on `public` schema
4. **Data Availability**: At least some moisture_readings data for sensors 0001-0001 to 0001-0012

---

## Quick Start (5 Steps)

### Step 1: Create Smoothed Table

```bash
cd /Users/subhajlimanond/dev/munbon2-backend/services/sensor-data

psql -h 43.208.201.191 -U postgres -d sensor_data -f sql/01_create_smoothed_table.sql
```

**What it does**:
- Creates `smoothed_moisture_readings` table (identical structure to `moisture_readings`)
- Creates 3 indexes for optimal query performance
- Adds table comment documenting the algorithm

**Verification**:
```sql
\d smoothed_moisture_readings
-- Should show 13 columns, 3 indexes
```

---

### Step 2: Profile Raw Data Quality (Baseline)

```bash
psql -h 43.208.201.191 -U postgres -d sensor_data -f sql/02_profile_quality_raw.sql
```

**What it does**:
- Analyzes past 14 days of raw moisture data
- Reports per-sensor statistics (avg, stddev, min, max, median)
- Counts extreme values (0%, 100%)
- Detects rapid changes (>30% jumps)
- Classifies sensors by data quality

**Sample Output**:
```
=== RAW MOISTURE DATA QUALITY PROFILE ===

1. OVERALL STATISTICS (14 days)
 total_records | unique_sensors | earliest_reading | latest_reading | days_with_data 
---------------+----------------+------------------+----------------+----------------
         11412 |             12 | 2025-10-22 ...   | 2025-11-05 ... |             12

2. PER-SENSOR STATISTICS
 sensor_id | record_count | avg_surface | stddev_surface | ...
-----------+--------------+-------------+----------------+-----
 0001-0001 |         1377 |       84.90 |          17.02 | ...
 0001-0008 |         1419 |        0.26 |           4.91 | ... (FAILED)
 ...

5. DATA QUALITY SUMMARY
 sensor_id | pct_surface_zeros | pct_surface_hundreds | classification
-----------+-------------------+----------------------+-------------------------
 0001-0008 |              99.7 |                  0.2 | CRITICAL - Likely Failed
 0001-0010 |               3.3 |                  1.7 | MODERATE - High Spikes
 ...
```

**Save this output** for comparison after smoothing.

---

### Step 3: Apply Smoothing (Core Algorithm)

```bash
psql -h 43.208.201.191 -U postgres -d sensor_data -f sql/04_backfill_smoothing_14d.sql
```

**What it does**:
1. Truncates `smoothed_moisture_readings` (clears old data)
2. Applies Hampel filter to detect outliers:
   - Computes rolling median (7-sample window)
   - Calculates MAD (Median Absolute Deviation)
   - Flags outliers: |value - median| > 3×MAD OR value ∈ {0,100} OR jump >30%
   - Preserves plateaus (3+ consecutive equal values)
3. Replaces outliers with rolling median
4. Applies EMA smoothing:
   - α = 0.25 for standard sensors
   - α = 0.35 for new sensors (0001-0003, 0001-0005, 0001-0009, 0001-0011, 0001-0012)
5. Inserts ~11,000 smoothed rows

**Expected Runtime**: 30-60 seconds

**Sample Output**:
```
=== STARTING SMOOTHING BACKFILL ===
Approach A: Hampel Filter + Rolling Median + EMA

Step 1: Truncating smoothed_moisture_readings table...
TRUNCATE TABLE

Step 2: Applying Hampel filter and EMA smoothing...
This may take 30-60 seconds...

Step 3: Verifying insert...
 rows_inserted | sensors_processed | earliest | latest
---------------+-------------------+----------+--------
         11412 |                12 | ...      | ...

=== SMOOTHING BACKFILL COMPLETE ===
```

---

### Step 4: Profile Smoothed Data Quality (Verification)

```bash
psql -h 43.208.201.191 -U postgres -d sensor_data -f sql/03_profile_quality_smoothed.sql
```

*(Note: Create this file using the same structure as `02_profile_quality_raw.sql` but query `smoothed_moisture_readings` instead of `moisture_readings`)*

**What to check**:

| Metric | Raw (Before) | Target (After) | ✅ Success Criteria |
|--------|--------------|----------------|---------------------|
| Surface spikes ≥95% | ~1,515 (14%) | <200 (<2%) | ≥80% reduction |
| Surface zeros ≤5% | ~3,883 (36%) | <500 (<5%) | ≥80% reduction |
| Deep spikes ≥95% | ~1,530 (14%) | <200 (<2%) | ≥80% reduction |
| Deep zeros ≤5% | ~4,310 (40%) | <500 (<5%) | ≥80% reduction |
| Large jumps >30% | ~500 | <100 | ≥80% reduction |
| Avg stddev | ~26% | <13% | ≥50% reduction |

---

### Step 5: Compare Raw vs. Smoothed (Side-by-Side)

```sql
-- Quick comparison query
WITH raw AS (
    SELECT 
        'RAW' as source,
        COUNT(*) as records,
        COUNT(CASE WHEN moisture_surface_pct >= 95 THEN 1 END) as surface_high,
        COUNT(CASE WHEN moisture_surface_pct <= 5 THEN 1 END) as surface_low,
        ROUND(STDDEV(moisture_surface_pct)::numeric, 2) as stddev_surface
    FROM moisture_readings
    WHERE time >= NOW() - INTERVAL '14 days'
      AND sensor_id IN ('0001-0001','0001-0002','0001-0003','0001-0004','0001-0005',
                        '0001-0006','0001-0007','0001-0008','0001-0009','0001-0010',
                        '0001-0011','0001-0012')
),
smoothed AS (
    SELECT 
        'SMOOTHED' as source,
        COUNT(*) as records,
        COUNT(CASE WHEN moisture_surface_pct >= 95 THEN 1 END) as surface_high,
        COUNT(CASE WHEN moisture_surface_pct <= 5 THEN 1 END) as surface_low,
        ROUND(STDDEV(moisture_surface_pct)::numeric, 2) as stddev_surface
    FROM smoothed_moisture_readings
)
SELECT * FROM raw
UNION ALL
SELECT * FROM smoothed;
```

**Expected Output**:
```
  source   | records | surface_high | surface_low | stddev_surface
-----------+---------+--------------+-------------+----------------
 RAW       |   11412 |         1515 |        3883 |          26.14
 SMOOTHED  |   11412 |          150 |         400 |          12.80
```

✅ **Success**: 90% spike reduction, 51% stddev reduction!

---

## Rollback Plan

If you need to revert:

```sql
-- Option 1: Truncate smoothed table (keeps structure)
TRUNCATE TABLE public.smoothed_moisture_readings;

-- Option 2: Drop table completely
DROP TABLE IF EXISTS public.smoothed_moisture_readings CASCADE;
```

Raw data in `moisture_readings` is **never modified** — you can re-run the smoothing script anytime.

---

## Troubleshooting

### Issue 1: "ERROR: out of memory"
**Solution**: Increase work_mem (already set to 256MB in script). If still fails:
```sql
SET work_mem = '512MB';  -- At top of 04_backfill_smoothing_14d.sql
```

### Issue 2: "ERROR: relation moisture_readings does not exist"
**Solution**: Verify table name and schema:
```sql
\dt public.moisture_readings
```

### Issue 3: Query takes >5 minutes
**Solution**: Check indexes exist:
```sql
\di public.moisture_readings
-- Should show: idx_moisture_sensor_time, moisture_readings_time_idx, idx_moisture_sensor
```

### Issue 4: Smoothed data still has many spikes
**Solution**: Tune parameters (see Algorithm Tuning below)

---

## Algorithm Tuning

If results are not satisfactory, adjust parameters in `04_backfill_smoothing_14d.sql`:

### More Aggressive Smoothing
```sql
-- Line 133: Lower Hampel threshold (2.5 instead of 3.0)
WHEN ABS(moisture_surface_pct - rolling_median_surface) > (2.5 * GREATEST(mad_surface, 0.01))

-- Line 214/255: Lower EMA alpha (0.15 instead of 0.25)
ELSE 0.15  -- Stronger smoothing
```

### Less Aggressive Smoothing (Preserve More Variation)
```sql
-- Line 133: Raise Hampel threshold (4.0 instead of 3.0)
WHEN ABS(moisture_surface_pct - rolling_median_surface) > (4.0 * GREATEST(mad_surface, 0.01))

-- Line 214/255: Raise EMA alpha (0.35 instead of 0.25)
ELSE 0.35  -- Faster response to changes
```

### Per-Sensor Tuning
Add sensor-specific logic:
```sql
-- Example: Sensor 0001-0010 needs more aggressive filtering
CASE 
    WHEN r.sensor_id = '0001-0010' THEN 0.15  -- Strong smoothing
    WHEN r.sensor_id IN ('0001-0003','0001-0005','0001-0009','0001-0011','0001-0012') THEN 0.35
    ELSE 0.25
END as alpha
```

---

## Next Steps

### Optional: Deploy Real-Time Smoothing

After validating the batch backfill, you can deploy real-time smoothing:

**Option A**: Database Trigger (planned for `05_realtime_fn_and_trigger.sql`)
- Automatically smooths new rows as they're inserted into `moisture_readings`
- Maintains identical algorithm to backfill

**Option B**: Application-Layer Filter
- Implement smoothing logic in Node.js ingestion service
- Easier to unit-test and debug

### Monitoring & Maintenance

1. **Daily Quality Check**:
   ```sql
   -- Run daily to detect sensor failures
   SELECT sensor_id, 
          COUNT(CASE WHEN moisture_surface_pct >= 95 OR moisture_surface_pct <= 5 THEN 1 END) as spikes,
          ROUND(100.0 * COUNT(CASE WHEN moisture_surface_pct >= 95 OR moisture_surface_pct <= 5 THEN 1 END) / COUNT(*), 2) as spike_pct
   FROM smoothed_moisture_readings
   WHERE time >= NOW() - INTERVAL '24 hours'
   GROUP BY sensor_id
   HAVING COUNT(CASE WHEN moisture_surface_pct >= 95 OR moisture_surface_pct <= 5 THEN 1 END) > 0.20 * COUNT(*);
   ```

2. **Incremental Backfill** (for new data):
   ```bash
   # Modify sql/04_backfill_smoothing_14d.sql to smooth last 24 hours instead of 14 days
   # Change line 52: WHERE time >= NOW() - INTERVAL '24 hours'
   # Then run daily via cron
   ```

3. **Alert on Anomalies**:
   - If any sensor shows >20% spikes post-smoothing → Hardware failure likely

---

## Performance Metrics

| Operation | Rows | Expected Time | Actual Time (your results) |
|-----------|------|---------------|---------------------------|
| Create table | - | <5 sec | |
| Profile raw | 11,412 | ~10 sec | |
| Apply smoothing | 11,412 | 30-60 sec | |
| Profile smoothed | 11,412 | ~10 sec | |
| **Total** | | **~1-2 min** | |

---

## Support & Documentation

- **Full Analysis**: `../MOISTURE_DATA_ANALYSIS_AND_SMOOTHING_RECOMMENDATIONS.md`
- **Algorithm Details**: See "Approach A" section in analysis document
- **Parameter Reference**: Lines 133, 144, 156, 214, 255 in `04_backfill_smoothing_14d.sql`

---

## Success Checklist

- [  ] Step 1: Table created successfully
- [  ] Step 2: Raw data profiled (baseline saved)
- [  ] Step 3: Smoothing applied (11,412 rows inserted)
- [  ] Step 4: Smoothed data profiled (metrics improved)
- [  ] Step 5: Comparison shows ≥80% spike reduction
- [  ] ✅ **READY FOR PRODUCTION USE**

---

**Questions or Issues?**  
Refer to the full analysis document or re-run scripts with adjusted parameters.

**Last Updated**: 2025-11-05  
**Version**: 1.0
