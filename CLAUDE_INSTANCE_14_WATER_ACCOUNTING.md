# Claude Instance 14: Section-Level Water Accounting System

## Context
You are implementing Task 63 for the Munbon Irrigation Backend project. The system must track water deliveries at the section level (50-200 hectares) through both automated gates (20 with continuous measurement) and manual gates (estimated flows).

## Your Task
Implement the Section-Level Water Accounting system that provides comprehensive water tracking with mixed data sources.

## Key Requirements

### Accounting Scope
- Section level (not plot level)
- Mix of real-time (automated) and estimated (manual) data
- Weekly reconciliation cycles
- Support regulatory compliance reporting

### Core Features to Implement

1. **Volume Calculator**
   - Integrate continuous flow data (automated gates)
   - Calculate volumes from gate settings + hydraulic models (manual gates)
   - Handle mixed confidence levels

2. **Delivery Tracker**
   - Compare planned vs actual deliveries
   - Track delivery windows and durations
   - Account for travel time and losses

3. **Loss Detection**
   - Identify discrepancies between upstream/downstream
   - Distinguish between seepage, evaporation, and measurement error
   - Generate investigation alerts

4. **Weekly Reconciliation**
   - Combine all data sources
   - Apply field team corrections
   - Generate weekly balance reports

5. **Efficiency Metrics**
   - Calculate delivery efficiency by section
   - Consider soil type and crop requirements
   - Track improvement over time

### Technical Specifications
- Python/FastAPI service
- Port: 3019
- PostgreSQL for transactional data
- TimescaleDB for time-series volumes
- Integration with calibrated gate flow equations

### Deliverables
1. Water accounting APIs
2. Volume calculation engine
3. Loss detection algorithms
4. Reconciliation workflows
5. Regulatory report generators
6. Efficiency dashboards

### Data Sources
- Automated gate flows (real-time)
- Manual gate settings (field reports)
- Hydraulic model estimates
- Field team observations
- Weather data (for evaporation)

## Implementation Notes
- Handle partial data gracefully
- Maintain audit trails for all calculations
- Support backdated corrections
- Calculate confidence intervals for all estimates
- Design for 5-year data retention

Start by defining the data models and calculation engine.