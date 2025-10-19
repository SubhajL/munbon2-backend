# Threshold Recommendation Report

Generated: 2025-10-15T08:19:57.850Z

## Current Thresholds

| Plot ID | Moisture Lower | Moisture Upper | Water Level Lower | Water Level Upper |
|---------|----------------|----------------|-------------------|-------------------|
| 491f0baf-452... | 50.00% | 69.00% | -10.00 cm | 10.00 cm |
| 5177f028-020... | 50.00% | 69.00% | -10.00 cm | 10.00 cm |
| 535d0d0b-afd... | 80.60% | 87.00% | -10.00 cm | 10.00 cm |
| 5ea77d99-c3f... | 53.00% | 73.00% | -10.00 cm | 10.00 cm |
| 6ab85dc0-748... | 50.00% | 69.00% | -10.00 cm | 10.00 cm |
| 7012604e-07d... | 50.00% | 69.00% | -10.00 cm | 10.00 cm |
| 7072584e-e3c... | 15.00% | 29.60% | -10.00 cm | 10.00 cm |
| aabb24c1-b67... | 50.00% | 69.00% | -10.00 cm | 10.00 cm |
| c34e125d-805... | 50.00% | 69.00% | -10.00 cm | 10.00 cm |
| cc74748e-1c9... | 50.00% | 69.00% | -10.00 cm | 10.00 cm |
| f0b3c562-606... | 50.00% | 69.00% | -10.00 cm | 10.00 cm |
| fbd7920c-1a0... | 90.00% | 96.20% | -10.00 cm | 10.00 cm |
| TEST-PLOT-01 | 50.00% | 69.00% | -10.00 cm | 10.00 cm |
| TEST-PLOT-02 | 50.00% | 69.00% | -10.00 cm | 10.00 cm |
| TEST-PLOT-03 | 50.00% | 69.00% | -10.00 cm | 10.00 cm |

## Historical Data Summary

| Plot ID | Count | Min | Avg | Max | Median | P95 |
|---------|-------|-----|-----|-----|--------|-----|
| 491f0baf-452... | N/A | N/A | N/A | N/A | N/A | N/A |
| 5177f028-020... | N/A | N/A | N/A | N/A | N/A | N/A |
| 535d0d0b-afd... | 2088 | 0 | 29 | 100 | 17 | 95 |
| 5ea77d99-c3f... | 1922 | 0 | 25 | 95 | 2 | 77 |
| 6ab85dc0-748... | N/A | N/A | N/A | N/A | N/A | N/A |
| 7012604e-07d... | N/A | N/A | N/A | N/A | N/A | N/A |
| 7072584e-e3c... | 1916 | 0 | 11 | 82 | 5 | 31 |
| aabb24c1-b67... | N/A | N/A | N/A | N/A | N/A | N/A |
| c34e125d-805... | N/A | N/A | N/A | N/A | N/A | N/A |
| cc74748e-1c9... | N/A | N/A | N/A | N/A | N/A | N/A |
| f0b3c562-606... | N/A | N/A | N/A | N/A | N/A | N/A |
| fbd7920c-1a0... | 2084 | 0 | 18 | 98 | 16 | 77 |
| TEST-PLOT-01 | N/A | N/A | N/A | N/A | N/A | N/A |
| TEST-PLOT-02 | N/A | N/A | N/A | N/A | N/A | N/A |
| TEST-PLOT-03 | N/A | N/A | N/A | N/A | N/A | N/A |

## Recommendations

⚠️  **15 plot(s) have significant out-of-range readings:**

### 491f0baf-452...

- **Issue:** No historical data available for this plot
- **Recommendation:** Ensure sensor is mapped and collecting data

### 5177f028-020...

- **Issue:** No historical data available for this plot
- **Recommendation:** Ensure sensor is mapped and collecting data

### 535d0d0b-afd...

- **Current Moisture Thresholds:** 80.60% - 87.00%
- **Historical Range:** 0% - 100%
- **Estimated Out-of-Range:** 94% of readings
  - Below Lower: ~81%
  - Above Upper: ~13%

- **Recommendation:** Consider lowering moisture_lower_threshold to 70.6% to reduce excessive valve cycling

### 5ea77d99-c3f...

- **Current Moisture Thresholds:** 53.00% - 73.00%
- **Historical Range:** 0% - 95%
- **Estimated Out-of-Range:** 79% of readings
  - Below Lower: ~56%
  - Above Upper: ~23%

- **Recommendation:** Consider lowering moisture_lower_threshold to 43% to reduce excessive valve cycling
- **Recommendation:** Consider raising moisture_upper_threshold to 73.001% to reduce excessive valve cycling

### 6ab85dc0-748...

- **Issue:** No historical data available for this plot
- **Recommendation:** Ensure sensor is mapped and collecting data

### 7012604e-07d...

- **Issue:** No historical data available for this plot
- **Recommendation:** Ensure sensor is mapped and collecting data

### 7072584e-e3c...

- **Current Moisture Thresholds:** 15.00% - 29.60%
- **Historical Range:** 0% - 82%
- **Estimated Out-of-Range:** 82% of readings
  - Below Lower: ~18%
  - Above Upper: ~64%

- **Recommendation:** Consider raising moisture_upper_threshold to 29.601% to reduce excessive valve cycling

### aabb24c1-b67...

- **Issue:** No historical data available for this plot
- **Recommendation:** Ensure sensor is mapped and collecting data

### c34e125d-805...

- **Issue:** No historical data available for this plot
- **Recommendation:** Ensure sensor is mapped and collecting data

### cc74748e-1c9...

- **Issue:** No historical data available for this plot
- **Recommendation:** Ensure sensor is mapped and collecting data

### f0b3c562-606...

- **Issue:** No historical data available for this plot
- **Recommendation:** Ensure sensor is mapped and collecting data

### fbd7920c-1a0...

- **Current Moisture Thresholds:** 90.00% - 96.20%
- **Historical Range:** 0% - 98%
- **Estimated Out-of-Range:** 94% of readings
  - Below Lower: ~92%
  - Above Upper: ~2%

- **Recommendation:** Consider lowering moisture_lower_threshold to 80% to reduce excessive valve cycling

### TEST-PLOT-01

- **Issue:** No historical data available for this plot
- **Recommendation:** Ensure sensor is mapped and collecting data

### TEST-PLOT-02

- **Issue:** No historical data available for this plot
- **Recommendation:** Ensure sensor is mapped and collecting data

### TEST-PLOT-03

- **Issue:** No historical data available for this plot
- **Recommendation:** Ensure sensor is mapped and collecting data
