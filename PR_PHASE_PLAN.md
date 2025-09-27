# Pull Request Phase Plan

## Overview
Breaking down the feature/WD-BFF-and-ts-to-js branch into manageable pull requests.

## Phase 1: Auth Service TypeScript to JavaScript Conversion
**Priority: HIGH**
**Size: Large**

### Changes:
- Deleted all TypeScript files from auth service (`services/auth/src/*.ts`)
- Added JavaScript equivalents with `.js`, `.d.ts`, and `.map` files
- Updated `package.json` dependencies
- Created backup directories (`src_typescript_backup/`)
- Removed `tsconfig.json`

### Files affected:
- All files in `services/auth/src/`
- `services/auth/package.json`
- `services/auth/package-lock.json`

### PR Title: "Convert Auth Service from TypeScript to JavaScript"

### PR Description:
```
## Summary
Converted the Auth service from TypeScript to JavaScript to align with project standards and reduce build complexity.

## Changes
- Converted all TypeScript files to JavaScript
- Generated type definitions (.d.ts) for type safety
- Updated package dependencies
- Created backup of original TypeScript files

## Testing
- [ ] All auth endpoints tested
- [ ] Login/logout functionality verified
- [ ] JWT token generation working
- [ ] User management endpoints tested
```

---

## Phase 2: Remove ROS-GIS Integration Service
**Priority: MEDIUM**
**Size: Medium**

### Changes:
- Deleted entire `services/ros-gis-integration/` directory
- Removed migration scripts
- Removed deployment scripts

### Files affected:
- All files in `services/ros-gis-integration/`

### PR Title: "Remove deprecated ROS-GIS Integration service"

### PR Description:
```
## Summary
Removed the deprecated ROS-GIS Integration service as functionality has been moved to BFF services.

## Changes
- Removed entire ros-gis-integration service
- Cleaned up related deployment scripts
- Removed database migration files

## Impact
- No production impact - service was not in use
- Functionality replaced by BFF Water Planning service
```

---

## Phase 3: BFF Water Planning Service Enhancements
**Priority: HIGH**
**Size: Large**

### Changes:
- Added new routes for crop season demand
- Added water demand v2 endpoints
- New services for weekly calculations
- Added schedulers for daily and weekly operations
- Updated main.py
- Added new dependencies in requirements.txt

### Files affected:
- `services/bff-water-planning/src/api/routes/crop_season_demand.py`
- `services/bff-water-planning/src/api/routes/water_demand_v2.py`
- `services/bff-water-planning/src/db/weekly_demand_repository.py`
- `services/bff-water-planning/src/services/*.py` (multiple new services)
- `services/bff-water-planning/src/main.py`
- `services/bff-water-planning/requirements.txt`

### PR Title: "Add water demand calculation and scheduling to BFF Water Planning"

### PR Description:
```
## Summary
Enhanced BFF Water Planning service with comprehensive water demand calculations and scheduling capabilities.

## New Features
- Crop season demand calculations
- Weekly water demand accumulation
- Daily demand scheduling
- Water demand API v2 with improved performance

## Changes
- Added new API endpoints for water demand calculations
- Implemented schedulers for automated calculations
- Added repository layer for weekly demand data
- Enhanced calculation services with v2 algorithms

## Testing
- [ ] All new endpoints tested
- [ ] Scheduler functionality verified
- [ ] Calculation accuracy validated against Excel sheets
- [ ] Performance improvements measured
```

---

## Phase 4: ROS Service Updates
**Priority: MEDIUM**
**Size: Small**

### Changes:
- Added area ID validation middleware
- Added water level aggregation service
- Added weekly update scheduler
- Added area ID formatter utility
- Updated package.json and index.js

### Files affected:
- `services/ros/src/middleware/area-id-validator.js`
- `services/ros/src/services/area.service.updated.js`
- `services/ros/src/services/water-level-aggregation.service.js`
- `services/ros/src/services/weekly-update-scheduler.service.js`
- `services/ros/src/utils/area-id-formatter.js`
- `services/ros/package.json`
- `services/ros/src/index.js`

### PR Title: "Add area validation and water level aggregation to ROS service"

### PR Description:
```
## Summary
Enhanced ROS service with area ID validation, water level aggregation, and weekly scheduling.

## Changes
- Added middleware for area ID validation
- Implemented water level aggregation from multiple sensors
- Added weekly scheduler for automated updates
- Added utility for consistent area ID formatting

## Testing
- [ ] Area ID validation tested with various formats
- [ ] Water level aggregation accuracy verified
- [ ] Weekly scheduler timing tested
```

---

## Phase 5: Documentation Updates
**Priority: LOW**
**Size: Medium**

### Changes:
- Updated all Claude instance documentation files
- Updated .claude/settings.json
- Modified view-docs.sh script

### Files affected:
- All files in `docs/CLAUDE_INSTANCE_*.md`
- `docs/CLAUDE_INSTANCES_MASTER.md`
- `.claude/settings.json`
- `view-docs.sh`

### PR Title: "Update Claude instance documentation"

### PR Description:
```
## Summary
Updated documentation for all Claude instances to reflect current service architecture.

## Changes
- Updated instance documentation for all services
- Added new BFF service documentation
- Updated Claude settings
- Enhanced documentation viewer script
```

---

## Phase 6: Sensor Data and Monitoring Updates
**Priority: MEDIUM**
**Size: Medium**

### Changes:
- Added moisture sensor fixes and deployment scripts
- Added water level sensor test scripts
- Added EC2 deployment configurations
- Added sensor ID mapping utilities

### Files affected:
- All files in `services/sensor-data/` (new scripts)
- Water level test scripts in root directory
- Sensor ID mapping files

### PR Title: "Fix sensor data processing and add monitoring tools"

### PR Description:
```
## Summary
Fixed moisture sensor data processing issues and added comprehensive monitoring tools.

## Changes
- Fixed moisture sensor data processor
- Added deployment scripts for EC2
- Added water level sensor testing utilities
- Implemented sensor ID mapping for numeric conversions

## Bug Fixes
- Resolved MAC address conversion issues
- Fixed numeric sensor ID handling
```

---

## Recommended Order of PRs:

1. **Phase 1** - Auth Service Conversion (blocking other services)
2. **Phase 3** - BFF Water Planning (core functionality)
3. **Phase 4** - ROS Service Updates (depends on water planning)
4. **Phase 6** - Sensor Data Fixes (can be parallel)
5. **Phase 2** - Remove ROS-GIS Integration (cleanup)
6. **Phase 5** - Documentation (can be done last)

## Alternative: Single Large PR

If you prefer a single PR, use this structure:

### PR Title: "Convert Auth to JS and add BFF Water Planning service"

### PR Description:
```
## Summary
Major refactoring to convert Auth service from TypeScript to JavaScript and add comprehensive BFF Water Planning service with water demand calculations.

## Major Changes

### 1. Auth Service Conversion
- Converted from TypeScript to JavaScript
- Maintained type safety with .d.ts files

### 2. BFF Water Planning Service
- Added water demand calculation endpoints
- Implemented scheduling for automated calculations
- Added crop season demand features

### 3. ROS Service Enhancements
- Added area validation and water level aggregation

### 4. Cleanup
- Removed deprecated ros-gis-integration service
- Updated documentation

## Testing Checklist
- [ ] Auth service fully tested
- [ ] Water planning calculations verified
- [ ] Schedulers running correctly
- [ ] All endpoints documented
```