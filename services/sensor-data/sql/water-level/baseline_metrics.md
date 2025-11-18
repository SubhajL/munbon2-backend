# Water Level Raw Data Quality Baseline Metrics

## Date: 2025-11-17
## Period Analyzed: 14 days

## Key Findings

### Overall Summary
- **6 sensors analyzed**: AWD-6D47, AWD-9950, AWD-B89D, AWD-558F, AWD-4ED4, AWD-A4F8
- **1,992 total readings**
- **0.00% spike rate (>200cm)** - No extreme spikes detected
- **13.55cm overall average water level**

### Per-Sensor Metrics

| Sensor | Readings | Avg Level | Min | Max | Std Dev | Negative Values | Data Gaps |
|--------|----------|-----------|-----|-----|---------|-----------------|-----------|
| AWD-6D47 | 555 | 15.11cm | 9cm | 19cm | 3.83cm | 0 | 184 |
| AWD-9950 | 390 | 19.02cm | 13cm | 23cm | 2.08cm | 0 | 129 |
| AWD-B89D | 972 | 10.39cm | -2cm | 27cm | 7.19cm | 3 | 323 |
| AWD-558F | 57 | 13.79cm | 7cm | 20cm | 3.56cm | 0 | 16 |
| AWD-4ED4 | 15 | 19.80cm | 15cm | 27cm | 4.06cm | 0 | 4 |
| AWD-A4F8 | 3 | 4.00cm | 4cm | 4cm | 0.00cm | 0 | 0 |

### Data Quality Issues

1. **Negative Values**: Only AWD-B89D has 3 negative readings (-2cm)
2. **No Spikes**: No readings above 150cm or 200cm threshold
3. **No Large Jumps**: No jumps >30cm or >50cm between consecutive readings
4. **Data Gaps**: Significant gaps (>5min) ranging from 0 to 323 per sensor
5. **Low Data Volume**: AWD-A4F8 has only 3 readings, AWD-4ED4 has only 15

### Standard Deviation Analysis
- Lowest: AWD-A4F8 (0.00cm) - but only 3 readings
- Highest: AWD-B89D (7.19cm) - most variable sensor
- Average: ~3.6cm for most active sensors

### Smoothing Goals
Since there are no spikes to reduce, the smoothing algorithm will focus on:
1. **Noise reduction**: Reduce standard deviation by 30-50%
2. **Negative value correction**: Replace negative values with reasonable estimates
3. **Gap filling**: Interpolate reasonable values during data gaps
4. **General smoothing**: Apply EMA to create smoother trend lines