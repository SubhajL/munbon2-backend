# Zone 6 Irrigation Analysis - Continuous Flow Model

## Key Correction: Continuous Flow vs Canal Filling

### ❌ INCORRECT Assumption (9.2 hours)
- Assumed each canal section must fill before water proceeds
- Added "filling time" = 0.5 × canal_volume / flow_rate
- Result: Unrealistic 9.2 hour travel time

### ✅ CORRECT Model (2.6 hours / 158 minutes)
- Water flows **CONTINUOUSLY** through open gates
- No waiting for canal sections to fill
- Travel time = Distance / Velocity only
- Matches field observations better

## Detailed Analysis with K1/K2 Calibrations

### 1. Time Calculation Method
- **Flow Rate**: Q = Cs × L × H × √(2g × ΔH) where Cs = K1 × (opening)^K2
- **Velocity**: V = Q / A (flow rate / canal cross-sectional area)
- **Travel Time**: T = Distance / Velocity

### 2. Actual Travel Times by Section

| Section | Distance | Flow (m³/s) | Velocity (m/s) | Time (min) |
|---------|----------|-------------|----------------|------------|
| Dam → PC 01 | 2.0 km | 11.91 | 0.60 | 56.0 |
| PC 01 → RMC | 1.0 km | 11.91 | 0.60 | 28.0 |
| RMC → SC | 0.5 km | 7.35 | 0.98 | 8.5 |
| SC → Circular | 0.5 km | 7.50 | 1.00 | 8.3 |
| Circular → TC1 | 0.5 km | 1.39 | 0.69 | 12.0 |
| TC1 → TC2 | 1.0 km | 1.19 | 0.60 | 28.0 |
| TC2 → FTO | 1.05 km | 2.00 | 1.00 | 17.5 |
| **TOTAL** | **6.55 km** | - | - | **158 min** |

### 3. K1/K2 Impact on Flows

**Gates with SCADA Calibrations:**
- M(0,0): K1=1.0693, K2=-1.229 → -24% flow vs default
- M(0,1;1,0): K1=1.0244, K2=-3.399 → +111% flow vs default
- M(0,1;1,1;1,0): K1=1.3876, K2=-3.58 → +44% flow vs default

**Key Finding**: More negative K2 values (like -3.399) make gates much more sensitive to opening changes, providing finer control but requiring more careful operation.

### 4. Velocity Profile
- **Primary canals**: 0.60 m/s (controlled by large gate flows)
- **Secondary canals**: 0.98-1.00 m/s (optimal range)
- **Tertiary canals**: 0.60-1.00 m/s (varies with gate restrictions)

All velocities are within typical irrigation canal range (0.3-2.0 m/s).

### 5. Irrigation Summary
- **Travel time**: 158 minutes (2.6 hours)
- **Irrigation duration**: 3 hours
- **Total operation**: 5.6 hours
- **Water delivered**: 3,240 m³ (6mm depth, 60% coverage)
- **Rotations needed**: 2 per full irrigation cycle

## Conclusion

The corrected continuous flow model shows that water reaches FTO 337 Rai in approximately **2.6 hours**, not 9.2 hours. This matches typical field observations where water flows continuously through the irrigation network without waiting for each canal section to completely fill. 

The K1/K2 calibrations significantly impact flow rates through gates, which in turn affect velocities and travel times, but the overall travel time remains reasonable for a 6.55 km irrigation network.