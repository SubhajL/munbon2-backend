# AWD Control Service - What It Does

## Executive Summary

The **AWD (Alternate Wetting and Drying) Control Service** is an intelligent irrigation management system that automatically controls water levels in rice fields to optimize water usage while maintaining crop yield. It reduces water consumption by 20-30% compared to traditional continuous flooding.

## Core Functionality

### 1. **Automated Water Level Management**
The service continuously monitors water levels in rice fields and automatically decides when to irrigate based on AWD principles:

- **Normal Operation**: Maintains 5-10 cm water depth during flooding
- **Drying Phase**: Allows water to drop to 15-20 cm below soil surface
- **Re-flooding**: Automatically triggers irrigation when threshold is reached
- **Smart Timing**: Adjusts based on crop growth stage and weather

### 2. **What Makes It "Alternate Wetting and Drying"**

```
Traditional Rice Farming:          AWD Method:
========================          ============
┌─────────────────────┐          ┌─────────────────────┐
│ CONTINUOUS FLOODING │          │   FLOODING (5-10cm) │ ← Wetting Phase
│    (Always wet)     │          └──────────┬──────────┘
│                     │                     ↓
│  Wastes 40% water   │          ┌─────────────────────┐
└─────────────────────┘          │  CONTROLLED DRYING  │ ← Drying Phase
                                 │  (-15 to -20cm)     │
                                 └──────────┬──────────┘
                                            ↓
                                 [Cycle Repeats]
```

### 3. **Growth Stage Intelligence**

The service adapts irrigation patterns based on rice growth stages:

| Growth Stage | Week | AWD Strategy | Water Level Target |
|-------------|------|--------------|-------------------|
| **Preparation** | 0 | Saturate field | 0-5 cm |
| **Vegetative** | 1-7 | Flexible AWD | -15 to -20 cm |
| **Reproductive** | 8-11 | Safe AWD | -10 cm (less stress) |
| **Maturation** | 12-16 | Terminal drying | Gradual dry-out |

### 4. **Real-World Actions**

**What happens in the field:**

1. **Sensors detect low water** → AWD-B7E6 sensor reads -18 cm
2. **Service evaluates** → Checks growth stage, weather, soil type
3. **Decision made** → "Irrigate Field F001 for 120 minutes"
4. **Command sent** → Kafka message to SCADA system
5. **Gates open** → Physical gates/pumps activate
6. **Water flows** → Field floods to 5-10 cm
7. **Gates close** → Target level reached
8. **Cycle logged** → Water usage recorded for analytics

### 5. **Smart Features**

#### **Weather Integration**
- Skip irrigation if rain is forecasted within 6 hours
- Adjust thresholds based on evapotranspiration rates
- Deeper drying during cooler periods

#### **Multi-Field Coordination**
- Manages irrigation queue when multiple fields need water
- Prioritizes based on:
  - Water stress level
  - Growth stage criticality
  - Field size
  - Available water supply

#### **Failure Handling**
- Automatic sensor failover to GIS data
- Manual override capabilities
- Emergency irrigation for critical stress

### 6. **Key Benefits**

| Benefit | Description | Measurement |
|---------|-------------|-------------|
| **Water Savings** | Reduces irrigation water use | 20-30% less water |
| **Cost Reduction** | Lower pumping costs | 25% energy savings |
| **Yield Maintenance** | No significant yield loss | 95-100% of traditional |
| **Methane Reduction** | Less anaerobic conditions | 30-40% less CH₄ |
| **Labor Efficiency** | Automated monitoring | 50% less field visits |

### 7. **Example Day in Operation**

```
06:00 - Morning sensor check
      - Field A: -8 cm (OK)
      - Field B: -17 cm (approaching threshold)
      - Field C: -19 cm (needs irrigation)

06:15 - Queue Field C for irrigation
      - Check weather: No rain expected
      - Calculate duration: 150 minutes needed

07:00 - Start irrigation Field C
      - Open gates G3, G4
      - Monitor flow rate

09:30 - Complete irrigation
      - Water level: +8 cm
      - Volume used: 4,500 liters
      - Close gates

10:00 - Analytics update
      - Water saved today: 1,200 liters
      - Season total saved: 45,000 liters
```

### 8. **System Intelligence Examples**

**Scenario 1: Rain Predicted**
```
Current: -16 cm
Threshold: -15 cm
Weather: 80% rain in 4 hours
Decision: SKIP irrigation, wait for rain
```

**Scenario 2: Critical Growth Stage**
```
Current: -12 cm
Stage: Flowering (critical)
Safe threshold: -10 cm
Decision: IRRIGATE immediately (safety priority)
```

**Scenario 3: Multiple Fields Need Water**
```
Field A: -18 cm, 2.5 hectares, vegetative
Field B: -14 cm, 1.8 hectares, flowering
Field C: -19 cm, 3.2 hectares, vegetative
Decision: Prioritize B (critical stage) → C (larger) → A
```

### 9. **What It Replaces**

**Traditional Method:**
- Farmer checks field daily
- Subjective water level assessment
- Manual gate operation
- Tendency to over-irrigate
- No systematic records

**With AWD Control Service:**
- Automated 24/7 monitoring
- Precise sensor measurements
- Algorithmic decisions
- Optimal water usage
- Complete audit trail

### 10. **In Simple Terms**

The AWD Control Service is like a **smart thermostat for rice fields**:
- Instead of keeping fields constantly flooded (like running AC all day)
- It cycles between wet and dry periods (like a programmable thermostat)
- Saves resources while maintaining comfort (yield)
- Learns and adapts to conditions
- Provides detailed usage reports

## Technical Implementation

- **Runs on**: Port 3013
- **Monitors**: 1000+ fields simultaneously
- **Processes**: 100,000+ sensor readings/day
- **Saves**: 20-30% irrigation water
- **Response time**: < 1 minute from detection to action
- **Reliability**: 99.9% uptime target