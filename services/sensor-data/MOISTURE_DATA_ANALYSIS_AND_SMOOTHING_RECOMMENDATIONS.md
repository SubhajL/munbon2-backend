# Moisture Sensor Data Quality Analysis & Smoothing Recommendations

**Date**: November 5, 2025  
**Scope**: 12 sensors (0001-0001 through 0001-0012)  
**Time Window**: Past 14 days (October 22 - November 5, 2025)  
**Total Records Analyzed**: 11,412 readings

---

## 1. Executive Summary

### Data Quality Issues Identified

The moisture sensor data from Gateway 0001 exhibits **severe data quality problems** across all 12 sensors, characterized by:

1. **Extreme Value Spikes**: Frequent jumps to 0% and 100% that are physically implausible
2. **Rapid Oscillations**: Consecutive readings differing by >30% moisture
3. **Sensor Reliability Variance**: Some sensors nearly non-functional (mostly 0%), others highly erratic
4. **Bimodal Distributions**: Many sensors stuck at extremes rather than showing realistic gradients

### Recommended Solution

**Approach A: Hampel Filter + Rolling Median + EMA** (detailed in Section 3)
- Retrospectively smooth all 14 days of data into new `smoothed_moisture_readings` table
- Deploy prospective real-time smoothing at ingestion or via database trigger
- Preserves raw data for audit while providing clean data for operational use

---

## 2. Detailed Data Quality Analysis

### 2.1 Overall Statistics (14 Days)

| Metric | Value |
|--------|-------|
| Total Records | 11,412 |
| Unique Sensors | 12 (0001-0001 to 0001-0012) |
| Days with Data | 12 days |
| Earliest Reading | Oct 22, 2025 19:00:40 UTC |
| Latest Reading | Nov 5, 2025 13:06:25 UTC |

### 2.2 Per-Sensor Analysis

#### **CRITICAL SEVERITY** (Nearly Non-functional)

##### Sensor 0001-0008
- **Records**: 1,419 readings
- **Surface**: AVG 0.26% (Min 0%, Max 100%, StdDev 4.91%)
- **Deep**: AVG 0.37% (Min 0%, Max 100%, StdDev 5.71%)
- **Issues**:
  - **99.7% of surface readings ≤5%** (1,415 of 1,419)
  - **99.1% of deep readings ≤5%** (1,405 of 1,419)
  - Only 3 spikes to 100% each for surface and deep
- **Assessment**: Sensor appears **completely dry/disconnected** or has sensor failure

##### Sensor 0001-0007
- **Records**: 1,389 readings
- **Surface**: AVG 12.33% (Min 0%, Max 100%, StdDev 18.33%)
- **Deep**: AVG 6.63% (Min 0%, Max 100%, StdDev 14.73%)
- **Issues**:
  - **64.6% of surface readings ≤5%** (897 of 1,389)
  - **76.1% of deep readings ≤5%** (1,057 of 1,389)
  - Median surface = 0%, median deep = 0%
- **Assessment**: Predominantly offline/non-functional

##### Sensor 0001-0002 (Deep Probe)
- **Records**: 1,392 readings
- **Surface**: AVG 38.42% (acceptable range)
- **Deep**: AVG 0.38% (Min 0%, Max 100%, StdDev 5.55%)
- **Issues**:
  - Surface shows normal distribution
  - **98.9% of deep readings ≤5%** (1,377 of 1,392)
  - Deep probe completely failed or disconnected
- **Assessment**: Surface functional, deep probe **failed**

#### **SEVERE ISSUES** (High Spike Rate)

##### Sensor 0001-0001
- **Records**: 1,377 readings
- **Surface**: AVG 84.90% (Min 0%, Max 100%, StdDev 17.02%, Median 90%)
- **Deep**: AVG 80.03% (Min 0%, Max 100%, StdDev 11.69%, Median 78%)
- **Rapid Changes**:
  - **5.62% of readings have surface jumps >30%** (77 spikes)
  - **1.61% of readings have deep jumps >30%** (22 spikes)
  - Max surface change: 85%, max deep change: 86%
- **Extreme Values**:
  - 424 surface readings = 100% (30.8%)
  - 147 deep readings = 100% (10.7%)
- **Assessment**: Highly erratic with frequent implausible spikes

##### Sensor 0001-0010
- **Records**: 1,371 readings
- **Surface**: AVG 15.75% (Min 0%, Max 100%, StdDev 17.24%, Median 12%)
- **Deep**: AVG 76.06% (Min 0%, Max 100%, StdDev 16.38%, Median 75%)
- **Rapid Changes**:
  - **7.74% of readings have surface jumps >30%** (106 spikes) - **HIGHEST**
  - **5.33% of readings have deep jumps >30%** (73 spikes)
  - Max surface change: 88%, max deep change: 97%
  - Avg change: 6.98% surface, 5.34% deep
- **Assessment**: Most volatile sensor; requires aggressive smoothing

##### Sensor 0001-0012
- **Records**: 328 readings (recently activated Oct 31)
- **Surface**: AVG 87.27% (Min 0%, Max 100%, StdDev 30.95%, Median 100%)
- **Deep**: AVG 87.30% (Min 0%, Max 100%, StdDev 33.10%, Median 100%)
- **Rapid Changes**:
  - **12.01% of readings have surface jumps >30%** (37 spikes) - **EXTREME**
  - **2.60% of readings have deep jumps >30%** (8 spikes)
- **Extreme Values**:
  - 259 surface readings = 100% (79.0%)
  - 238 deep readings = 100% (72.6%)
- **Assessment**: Stuck at 100% most of the time with occasional drops; likely saturated or malfunctioning

##### Sensor 0001-0011
- **Records**: 322 readings (recently activated Oct 31)
- **Surface**: AVG 17.84% (Min 0%, Max 100%, StdDev 29.94%, Median 1%)
- **Deep**: AVG 86.34% (Min 0%, Max 100%, StdDev 31.17%, Median 99%)
- **Rapid Changes**:
  - **7.50% of readings have surface jumps >30%** (24 spikes)
  - **5.31% of readings have deep jumps >30%** (17 spikes)
- **Extreme Values**:
  - 231 surface readings ≤5% (71.7%)
  - 241 deep readings ≥95% (74.8%)
- **Assessment**: Bimodal extremes; surface mostly 0%, deep mostly 100%

#### **MODERATE ISSUES** (Workable but Noisy)

##### Sensor 0001-0006
- **Records**: 1,330 readings
- **Surface**: AVG 55.39% (Min 0%, Max 100%, StdDev 26.88%, Median 43.5%)
- **Deep**: AVG 33.17% (Min 0%, Max 100%, StdDev 8.04%, Median 31%)
- **Rapid Changes**:
  - **4.14% of readings have surface jumps >30%** (55 spikes)
  - **2.03% of readings have deep jumps >30%** (27 spikes)
  - Avg change: 5.53% surface, 3.81% deep
- **Extreme Values**:
  - 110 surface readings = 100% (8.3%)
  - Deep relatively stable
- **Assessment**: Surface has periodic spikes; deep probe more reliable

##### Sensor 0001-0004
- **Records**: 1,300 readings
- **Surface**: AVG 37.95% (Min 0%, Max 100%, StdDev 18.46%, Median 29%)
- **Deep**: AVG 85.78% (Min 0%, Max 100%, StdDev 8.45%, Median 86%)
- **Rapid Changes**:
  - **3.46% of readings have surface jumps >30%** (45 spikes)
  - **2.00% of readings have deep jumps >30%** (26 spikes)
- **Assessment**: Moderate noise; reasonable baseline values

##### Sensor 0001-0002 (Surface)
- See "Critical Severity" section for deep probe issues
- **Surface**: Generally functional with 5.75% spike rate (80 spikes)
- **Assessment**: Surface usable after smoothing; deep probe failed

#### **RECENTLY ACTIVATED** (Limited Data)

##### Sensor 0001-0003
- **Records**: 445 readings (activated Oct 30)
- **Surface**: AVG 60.76% (Min 0%, Max 100%, StdDev 48.81%, Median 100%)
- **Deep**: AVG 60.74% (Min 0%, Max 100%, StdDev 48.88%, Median 100%)
- **Extreme Values**:
  - 242 surface readings = 100% (54.4%)
  - 243 deep readings = 100% (54.6%)
  - 156 surface readings ≤5% (35.1%)
  - 157 deep readings ≤5% (35.3%)
- **Assessment**: Bimodal distribution; needs stabilization period

##### Sensor 0001-0009
- **Records**: 403 readings (activated Oct 30)
- **Surface**: AVG 61.76% (Min 0%, Max 100%, StdDev 45.19%, Median 91%)
- **Deep**: AVG 62.75% (Min 0%, Max 100%, StdDev 48.29%, Median 100%)
- **Extreme Values**:
  - 154 surface readings = 100% (38.2%)
  - 222 deep readings = 100% (55.1%)
- **Assessment**: High saturation rate; needs monitoring

##### Sensor 0001-0005
- **Records**: 336 readings (activated Oct 31)
- **Surface**: AVG 86.96% (Min 0%, Max 100%, StdDev 33.40%, Median 100%)
- **Deep**: AVG 82.51% (Min 0%, Max 100%, StdDev 36.85%, Median 100%)
- **Extreme Values**:
  - 244 surface readings = 100% (72.6%)
  - 230 deep readings = 100% (68.5%)
- **Assessment**: Mostly saturated; verify sensor placement

### 2.3 Summary Table: Sensor Reliability Classification

| Sensor | Surface Status | Deep Status | Classification | Priority for Smoothing |
|--------|----------------|-------------|----------------|------------------------|
| 0001-0008 | **FAILED** (99.7% zero) | **FAILED** (99.1% zero) | Non-functional | Low (smoothing won't help) |
| 0001-0007 | **POOR** (64.6% zero) | **FAILED** (76.1% zero) | Nearly offline | Low |
| 0001-0002 | Functional | **FAILED** (98.9% zero) | Surface only | Medium (surface) |
| 0001-0001 | **HIGH SPIKES** (30.8% at 100%) | Moderate spikes (10.7%) | Erratic | **HIGH** |
| 0001-0010 | **VERY VOLATILE** (7.74% jump rate) | **VOLATILE** (5.33% jump rate) | Unstable | **CRITICAL** |
| 0001-0012 | **SATURATED** (79% at 100%) | **SATURATED** (72.6% at 100%) | Oversaturated | **HIGH** |
| 0001-0011 | Mostly zero (71.7% ≤5%) | **SATURATED** (74.8% ≥95%) | Bimodal extremes | **HIGH** |
| 0001-0006 | Moderate spikes (8.3% at 100%) | Stable | Workable | Medium |
| 0001-0004 | Moderate noise | Stable | Good baseline | Medium |
| 0001-0003 | Bimodal (54% at 100%, 35% at 0%) | Bimodal | New sensor | Medium |
| 0001-0009 | High saturation (38.2% at 100%) | Very high saturation (55.1%) | New sensor | Medium |
| 0001-0005 | Very high saturation (72.6%) | High saturation (68.5%) | New sensor | Medium |

---

## 3. Three Recommended Smoothing Approaches

### Approach A: Hampel Filter + Rolling Median + EMA ✅ **RECOMMENDED**

#### Description
A robust, three-stage outlier detection and smoothing pipeline:

1. **Hampel Filter**: Detects outliers using rolling median and MAD (Median Absolute Deviation)
2. **Outlier Replacement**: Replaces detected outliers with local rolling median
3. **EMA Smoothing**: Applies Exponential Moving Average for final de-noising

#### Algorithm Details

**Stage 1: Hampel Outlier Detection**
```
For each reading x_t at time t:
  window = [x_{t-3}, x_{t-2}, x_{t-1}, x_t, x_{t+1}, x_{t+2}, x_{t+3}]  # 7-sample window
  
  m_t = median(window)  # Rolling median
  MAD_t = 1.4826 × median(|window - m_t|)  # Median Absolute Deviation
  
  threshold = 3.0 × MAD_t
  
  Flag as outlier IF:
    - |x_t - m_t| > threshold, OR
    - x_t ∈ {0, 100} unless part of ≥3-point plateau, OR
    - |x_t - x_{t-1}| > 30% unless median shift > 15%
```

**Stage 2: Replacement**
```
IF outlier:
  x'_t = m_t  # Replace with rolling median
ELSE:
  x'_t = x_t  # Keep original
```

**Stage 3: EMA Smoothing**
```
s_0 = first non-outlier value or median of first window
s_t = α × x'_t + (1 - α) × s_{t-1}
      where α = 0.25 (or 0.35 for recently activated sensors)
```

#### Parameters

| Parameter | Default Value | Adjustable By Sensor |
|-----------|---------------|----------------------|
| Window Size | 7 samples | 3-5 for new sensors (≤6 days data) |
| Hampel Threshold | 3.0 MAD | Fixed |
| Plateau Rule | ≥3 consecutive equal values | Fixed |
| Big Jump Threshold | >30% change | Fixed |
| EMA Alpha (α) | 0.25 | 0.35 for new sensors |

#### Pros
- ✅ **Extremely robust** to extreme outliers (0%, 100%) and spikes
- ✅ **Preserves legitimate trends** (slow changes, plateaus)
- ✅ **Statistically principled** (MAD is robust to outliers)
- ✅ **Implementable purely in SQL** with window functions and recursive CTEs
- ✅ **No training required**; works immediately on historical data
- ✅ **Adaptable per sensor** via parameter tuning
- ✅ **Real-time capable** with rolling window buffer

#### Cons
- ⚠️ Window operations add computational overhead (manageable for 11K rows)
- ⚠️ Edge effects at series start/end (mitigated by using global median)
- ⚠️ Requires careful handling of NULL values and offline sensors

#### Complexity
- **Time**: O(n) per sensor with window operations
- **Space**: O(window_size) = O(1) for fixed window
- **Implementation**: ~200 lines of SQL with CTEs
- **Runtime Estimate**: <60 seconds for 11,412 rows on PostgreSQL

#### Real-Time Suitability
- ✅ **Excellent**: Can maintain rolling 7-sample buffer per sensor
- ✅ Can be implemented as database trigger or application-layer filter
- ✅ Latency: <5ms per reading

---

### Approach B: EWMA with Gated Slope Limiter

#### Description
A simpler sequential filter that rejects implausible measurements based on exponentially-weighted moving average and slope constraints.

#### Algorithm

```
Initialize: s_0 = x_0 (first reading)

For each new reading x_t:
  predicted_range = [s_{t-1} - 30, s_{t-1} + 30]
  
  IF x_t ∈ {0, 100} AND not part of ≥3-point plateau:
    x'_t = s_{t-1}  # Reject extreme, use previous smoothed value
  ELSE IF |x_t - s_{t-1}| > 30:
    x'_t = CLAMP(x_t, s_{t-1} - 30, s_{t-1} + 30)  # Limit rate of change
  ELSE:
    x'_t = x_t  # Accept
  
  # Update smoothed value
  s_t = α × x'_t + (1 - α) × s_{t-1}
  
  where α adapts to time gap:
    α = 0.2 if Δt ≤ 5 min
    α = 0.4 if Δt > 1 hour
```

#### Pros
- ✅ **Very simple** to implement and understand
- ✅ **Low computational cost**: single pass, O(n)
- ✅ **Natural for real-time**: inherently sequential
- ✅ **No window lookback** required

#### Cons
- ⚠️ **Less robust** than Hampel; relies on previous smoothed value (error accumulation risk)
- ⚠️ **No context from future readings** (non-causal)
- ⚠️ **Struggles with bursts** of consecutive outliers
- ⚠️ **Initialization sensitive**: bad first reading pollutes early estimates

#### Complexity
- **Time**: O(n) per sensor
- **Space**: O(1) — only stores previous smoothed value
- **Implementation**: ~50 lines of SQL (recursive CTE) or PL/pgSQL function

#### Real-Time Suitability
- ✅ **Excellent**: inherently designed for streaming data
- ⚠️ May lag behind true signal after burst of outliers

---

### Approach C: Kalman Filter with Change-Point Detection

#### Description
A state-space model that estimates the true moisture level while accounting for measurement noise and allowing for legitimate step changes.

#### Algorithm

**State Model**:
```
State: x_t (true moisture level)
State transition: x_t = x_{t-1} + w_t   where w_t ~ N(0, q)  (process noise)
Measurement: z_t = x_t + v_t            where v_t ~ N(0, r)  (measurement noise)
```

**Kalman Update**:
```
Prediction:
  x̂_t|t-1 = x̂_{t-1|t-1}           # State prediction
  P_t|t-1 = P_{t-1|t-1} + q        # Covariance prediction

Measurement gating:
  innovation = z_t - x̂_t|t-1
  IF |innovation| > 3σ OR z_t ∈ {0, 100}:
    Reject measurement (use prediction only)
  ELSE:
    Update:
      K_t = P_t|t-1 / (P_t|t-1 + r)     # Kalman gain
      x̂_t|t = x̂_t|t-1 + K_t × innovation
      P_t|t = (1 - K_t) × P_t|t-1
```

**Change-Point Detection** (CUSUM):
```
Monitor cumulative innovation to detect true step changes:
  S_t = max(0, S_{t-1} + innovation - drift)
  IF S_t > threshold:
    Reset Kalman state to allow adaptation
```

#### Parameters

| Parameter | Estimation Method |
|-----------|-------------------|
| Process noise q | Learn from robust std dev of first-order differences |
| Measurement noise r | Learn from MAD of residuals on stable segments |
| Gating threshold | 3σ (3 standard deviations) |
| CUSUM drift | 0.5 × typical innovation |
| CUSUM threshold | 5 × typical innovation |

#### Pros
- ✅ **Highest fidelity**: optimal for Gaussian noise (MMSE estimator)
- ✅ **Principled framework**: well-established theory
- ✅ **Handles gradual trends** naturally
- ✅ **Change-point detection** allows step changes without lag
- ✅ **Real-time native**: designed for online filtering

#### Cons
- ⚠️ **Complex to implement and tune**: requires careful parameter learning per sensor
- ⚠️ **Assumes near-Gaussian noise** (violated by extreme spikes in this dataset)
- ⚠️ **Requires PL/pgSQL or application layer**: not easily expressed in pure SQL
- ⚠️ **Initialization and state management** more involved
- ⚠️ **Tuning complexity**: 5+ parameters per sensor

#### Complexity
- **Time**: O(n) per sensor
- **Space**: O(1) state per sensor
- **Implementation**: ~300-400 lines (PL/pgSQL or Python/Node.js)
- **Tuning effort**: High (parameter learning per sensor required)

#### Real-Time Suitability
- ✅ **Excellent**: designed for online filtering
- ⚠️ Requires persistent state storage (last Kalman estimate per sensor)

---

## 4. Final Recommendation: Approach A (Hampel + Median + EMA)

### Rationale

Given the **extreme nature of data quality issues** in this dataset:

1. **Robustness is paramount**: Hampel filter is explicitly designed for outlier-contaminated data
2. **SQL implementability**: Pure SQL solution avoids deployment complexity
3. **Interpretability**: Easy to explain and audit (vs. black-box Kalman)
4. **No training required**: Works immediately on historical data
5. **Proven track record**: Hampel filter widely used in sensor data cleaning

### Approach A Handles All Observed Issues

| Issue Type | How Approach A Addresses It |
|------------|----------------------------|
| **Extreme spikes (0%, 100%)** | Hampel detects via MAD; replaced with local median |
| **Rapid oscillations (>30% jumps)** | Explicit big-jump rule flags and replaces |
| **Bimodal distributions** | Rolling median finds central tendency; EMA stabilizes |
| **Saturated sensors (stuck at 100%)** | Plateau rule preserves legitimate saturation; isolated excursions removed |
| **Failed sensors (mostly 0%)** | Leaves as NULL after filtering (no fabrication) |
| **New sensors (limited data)** | Smaller window (3-5) and higher α (0.35) parameters |

### Expected Improvements

Based on analysis:

| Metric | Before Smoothing | After Smoothing (Target) |
|--------|------------------|--------------------------|
| **Surface spikes ≥95%** | 1,515 readings (14.0%) | <200 readings (<2%) |
| **Surface zeros ≤5%** | 3,883 readings (35.8%) | <500 readings (<5%) |
| **Deep spikes ≥95%** | 1,530 readings (14.1%) | <200 readings (<2%) |
| **Deep zeros ≤5%** | 4,310 readings (39.8%) | <500 readings (<5%) |
| **Large jumps >30%** | 500 total | <100 total (80% reduction) |
| **Standard deviation (avg)** | 26.1% | <12% (50% reduction) |

### Implementation Strategy

1. **Retrospective Backfill** (one-time):
   - Run SQL script to populate `smoothed_moisture_readings` for past 14 days
   - Validate quality improvements with comparison queries
   - Expected runtime: <60 seconds

2. **Prospective Smoothing** (ongoing):
   - **Option 1** (Recommended): Database trigger on `moisture_readings` INSERT
   - **Option 2**: Application-layer filter in Node.js ingestion service
   - Both use identical algorithm and parameters

3. **Monitoring**:
   - Daily KPI report: spike rates, stddev, NULL counts per sensor
   - Alert if any sensor shows >20% spikes post-smoothing (indicates sensor failure)

4. **Per-Sensor Calibration**:
   - Sensors 0001-0008, 0001-0007, 0001-0002 (deep): Leave as NULL due to failure
   - Sensors 0001-0003, 0001-0005, 0001-0009, 0001-0011, 0001-0012: Use smaller window (5) and higher α (0.35)
   - All others: Standard parameters (window=7, α=0.25)

---

## 5. Next Steps

### Immediate Actions (This Week)

1. ✅ **Analysis Complete**: This document
2. ⬜ **Introspect Schema**: Capture `moisture_readings` structure and indexes
3. ⬜ **Create Target Table**: `public.smoothed_moisture_readings`
4. ⬜ **Implement SQL Scripts**:
   - `01_create_smoothed_table.sql`
   - `02_profile_quality_raw.sql`
   - `04_backfill_smoothing_14d.sql` (Approach A implementation)
5. ⬜ **Run Backfill**: Populate smoothed table for past 14 days
6. ⬜ **Validate Quality**: Run `03_profile_quality_smoothed.sql` and compare metrics

### Short-Term (Next 2 Weeks)

7. ⬜ **Deploy Real-Time Smoothing**:
   - Choose trigger vs. app-layer implementation
   - Test with live data stream
   - Monitor latency and accuracy
8. ⬜ **Visualization**: Generate before/after overlay plots for all 12 sensors
9. ⬜ **Documentation**: Create runbook for operations team

### Long-Term (This Month)

10. ⬜ **Hardware Investigation**:
    - Sensors 0001-0008, 0001-0007: Physical inspection or replacement
    - Sensor 0001-0002: Check deep probe connection
    - Sensors with high saturation: Verify installation depth and soil conditions
11. ⬜ **Alerting**: Automated notifications for sensor failures or post-smoothing anomalies
12. ⬜ **Historical Backfill** (optional): Extend smoothing to full historical dataset if needed

---

## 6. Appendix: Sensor-Specific Recommendations

### Sensors Requiring Hardware Attention

| Sensor | Issue | Recommended Action |
|--------|-------|-------------------|
| **0001-0008** | 99.7% zeros (both probes) | **Replace entire sensor unit** |
| **0001-0007** | 64-76% zeros (both probes) | **Inspect connections; likely replacement** |
| **0001-0002** | Deep probe 98.9% zeros | **Check deep probe connection/replacement** |

### Sensors Requiring Monitoring

| Sensor | Issue | Recommended Action |
|--------|-------|-------------------|
| **0001-0012** | 79% saturation (new sensor) | Monitor for 1 week; verify not submerged |
| **0001-0005** | 72% saturation (new sensor) | Monitor for 1 week; verify installation depth |
| **0001-0011** | Surface 71% zeros, deep 74% saturated | Monitor; possible depth/connection issue |
| **0001-0009** | 55% deep saturation (new sensor) | Monitor for 1 week |

### Sensors with Acceptable Quality (Post-Smoothing)

| Sensor | Status |
|--------|--------|
| **0001-0001** | Erratic but smoothing will recover usable trends |
| **0001-0004** | Moderate noise; good candidate for smoothing |
| **0001-0006** | Surface noisy but deep stable; smoothing effective |
| **0001-0010** | High volatility but retains signal; smoothing critical |

---

## 7. References

### Statistical Methods

- **Hampel Filter**: Pearson, Ronald K. (2002). "Outliers in process modeling and identification". IEEE Transactions on Control Systems Technology.
- **MAD (Median Absolute Deviation)**: Rousseeuw & Croux (1993). "Alternatives to the Median Absolute Deviation". Journal of the American Statistical Association.
- **EMA**: Brown, Robert G. (1962). "Smoothing, Forecasting and Prediction of Discrete Time Series". Prentice-Hall.

### Implementation Resources

- PostgreSQL Window Functions: https://www.postgresql.org/docs/current/tutorial-window.html
- TimescaleDB Time-Series Best Practices: https://docs.timescale.com/timescaledb/latest/how-to-guides/

---

**Document Version**: 1.0  
**Author**: Data Analysis Team  
**Next Review**: After implementation and 7-day monitoring period
