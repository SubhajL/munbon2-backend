# RID-MS Implementation Status

## Current Status: 40% Complete

### ✅ Phase 1: Ingestion (100% Complete)
- [x] API endpoint for file upload
- [x] S3 storage for ZIP files  
- [x] SQS message queuing
- [x] Authentication with token
- [x] Integration with sensor-data service
- [x] Documentation

### ⏳ Phase 2: Processing (0% Complete)
- [ ] SQS consumer service
- [ ] ZIP file extraction
- [ ] Shape file parser (.shp, .dbf, .shx)
- [ ] Coordinate transformation (UTM → WGS84)
- [ ] Database schema (PostgreSQL/PostGIS)
- [ ] Parcel data storage

### ⏳ Phase 3: Data Access (0% Complete)
- [ ] REST API for parcel queries
- [ ] Zone-based filtering
- [ ] GeoJSON export for visualization
- [ ] Water demand calculations
- [ ] Integration with GIS service

### ⏳ Phase 4: Water Demand (0% Complete)
- [ ] Crop coefficient tables
- [ ] Calculation methods (RID-MS, ROS, AWD)
- [ ] Scheduling based on interval
- [ ] Result storage and history

## What Still Needs to Be Done:

### 1. Create Processing Service (Priority: HIGH)
```typescript
// services/rid-ms/src/processors/shape-file-processor.ts
export class ShapeFileProcessor {
  constructor(
    private sqs: AWS.SQS,
    private s3: AWS.S3,
    private db: PostgreSQL
  ) {}

  async start() {
    // Poll SQS for new files
    // Download from S3
    // Extract and process
    // Store in database
  }
}
```

### 2. Database Schema (Priority: HIGH)
```sql
-- PostgreSQL with PostGIS extension
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE shape_file_uploads (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  upload_date TIMESTAMP NOT NULL,
  file_name VARCHAR(255) NOT NULL,
  s3_key VARCHAR(500) NOT NULL,
  status VARCHAR(50) DEFAULT 'uploaded',
  parcel_count INTEGER,
  processing_time_ms INTEGER,
  error_message TEXT,
  metadata JSONB
);

CREATE TABLE parcels (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  parcel_id VARCHAR(100) NOT NULL,
  shape_file_id UUID REFERENCES shape_file_uploads(id),
  valid_from TIMESTAMP NOT NULL DEFAULT NOW(),
  valid_to TIMESTAMP,
  zone VARCHAR(50) NOT NULL,
  sub_zone VARCHAR(50),
  geometry GEOMETRY(Polygon, 4326) NOT NULL,
  area_sqm NUMERIC(10,2),
  owner_name VARCHAR(255),
  owner_id VARCHAR(100),
  crop_type VARCHAR(100),
  water_demand_method VARCHAR(20) DEFAULT 'RID-MS',
  attributes JSONB,
  CONSTRAINT unique_current_parcel UNIQUE (parcel_id, valid_to)
);

-- Spatial and temporal indexes
CREATE INDEX idx_parcels_geometry ON parcels USING GIST (geometry);
CREATE INDEX idx_parcels_zone ON parcels (zone);
CREATE INDEX idx_parcels_valid ON parcels (valid_from, valid_to);
CREATE INDEX idx_parcels_current ON parcels (parcel_id) WHERE valid_to IS NULL;

CREATE TABLE water_demand_calculations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  parcel_id UUID REFERENCES parcels(id),
  calculated_at TIMESTAMP NOT NULL DEFAULT NOW(),
  method VARCHAR(20) NOT NULL, -- RID-MS, ROS, AWD
  crop_coefficient NUMERIC(4,2),
  reference_et NUMERIC(6,2), -- mm/day
  irrigation_efficiency NUMERIC(3,2),
  daily_demand_mm NUMERIC(8,2),
  daily_demand_liters NUMERIC(12,2),
  metadata JSONB
);
```

### 3. Shape File Parser (Priority: HIGH)
```typescript
// Install required packages
// npm install shapefile proj4 @turf/turf

import { open as openShapefile } from 'shapefile';
import proj4 from 'proj4';
import * as turf from '@turf/turf';

export class ShapeFileParser {
  async parseShapeFile(zipPath: string): Promise<Parcel[]> {
    // Extract ZIP
    const files = await this.extractZip(zipPath);
    
    // Parse .shp and .dbf together
    const source = await openShapefile(
      files['.shp'],
      files['.dbf']
    );
    
    const parcels: Parcel[] = [];
    let result = await source.read();
    
    while (!result.done) {
      const feature = result.value;
      
      // Transform coordinates
      const geometry = this.transformToWGS84(feature.geometry);
      
      // Extract attributes
      const parcel: Parcel = {
        parcelId: feature.properties.PARCEL_ID,
        zone: feature.properties.ZONE,
        geometry,
        area: turf.area(geometry),
        owner: feature.properties.OWNER,
        cropType: feature.properties.CROP_TYPE,
        attributes: feature.properties
      };
      
      parcels.push(parcel);
      result = await source.read();
    }
    
    return parcels;
  }
  
  private transformToWGS84(geometry: any): any {
    const utm48n = '+proj=utm +zone=48 +datum=WGS84 +units=m +no_defs';
    const wgs84 = '+proj=longlat +datum=WGS84 +no_defs';
    const transform = proj4(utm48n, wgs84);
    
    // Transform coordinates recursively
    return turf.transformRotate(geometry, 0, {
      mutate: true,
      pivot: 'centroid'
    });
  }
}
```

### 4. Data Access API (Priority: MEDIUM)
```typescript
// services/rid-ms/src/routes/parcel.routes.ts
router.get('/parcels/zones/:zone', async (req, res) => {
  const { zone } = req.params;
  const parcels = await db.query(`
    SELECT 
      parcel_id,
      ST_AsGeoJSON(geometry) as geometry,
      area_sqm,
      owner_name,
      crop_type,
      water_demand_method
    FROM parcels
    WHERE zone = $1 AND valid_to IS NULL
  `, [zone]);
  
  res.json({
    type: 'FeatureCollection',
    features: parcels.map(p => ({
      type: 'Feature',
      properties: p,
      geometry: JSON.parse(p.geometry)
    }))
  });
});
```

### 5. Water Demand Calculator (Priority: MEDIUM)
```typescript
export class WaterDemandCalculator {
  private cropCoefficients = {
    'Rice': { initial: 1.05, mid: 1.20, late: 0.90 },
    'Corn': { initial: 0.30, mid: 1.20, late: 0.60 },
    'Sugarcane': { initial: 0.40, mid: 1.25, late: 0.75 }
  };
  
  private efficiencies = {
    'RID-MS': 0.65,
    'ROS': 0.75,
    'AWD': 0.85
  };
  
  calculate(parcel: Parcel, et0: number): WaterDemand {
    const kc = this.getCropCoefficient(parcel.cropType, parcel.growthStage);
    const efficiency = this.efficiencies[parcel.waterDemandMethod];
    
    const etCrop = et0 * kc; // mm/day
    const grossDemand = etCrop / efficiency; // mm/day
    const volumetricDemand = grossDemand * parcel.area / 1000; // m³/day
    
    return {
      dailyDemandMm: grossDemand,
      dailyDemandCubicMeters: volumetricDemand,
      method: parcel.waterDemandMethod,
      efficiency,
      cropCoefficient: kc
    };
  }
}
```

## Next Steps (Priority Order):

1. **Deploy current Lambda** (file upload)
2. **Set up PostgreSQL/PostGIS** database
3. **Create processing service** (SQS consumer)
4. **Implement shape file parser**
5. **Build data access APIs**
6. **Add water demand calculations**
7. **Create monitoring dashboard**

## Estimated Time to Complete:
- Processing Service: 2-3 days
- Database & Parser: 2-3 days  
- APIs & Calculations: 2-3 days
- Testing & Integration: 2 days

**Total: ~10 days of development**