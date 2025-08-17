# RID Shapefile Integration

## Overview
The GIS service has been updated to handle RID (Royal Irrigation Department) shapefiles with specific field mappings based on the data dictionary provided in `DataDictionary_ridplan_result.docx`.

## RID Shapefile Fields

| Field Name | Description | Data Type |
|------------|-------------|-----------|
| PARCEL_SEQ | รหัสอ้างอิงรูปแปลง (Parcel reference ID) | String |
| sub_member | เลขที่โซน (Zone number 1-6) | Integer |
| parcel_area_rai | พื้นที่รูปแปลง (Parcel area in rai) | Float |
| data_date_process | วันที่ของข้อมูล (Data processing date) | Date |
| start_int | วันเริ่มปลูก (Planting start date) | Date |
| wpet | ประสิทธิภาพการใช้น้ำด้านการเกษตร | Float |
| age | อายุพืช (Plant age) | Integer |
| wprod | ผลิตภาพการใช้น้ำด้านการเกษตร | Float |
| plant_id | ชนิดพืช (Plant/crop type ID) | String |
| yield_at_mc_kgpr | ผลผลิต kg/rai | Float |
| season_irr_m3_per_rai | ความต้องการใช้น้ำ m³/ไร่ | Float |
| auto_note | วันที่มีการให้น้ำ (JSON format) | String |

## Zone Planting Dates (2025)
- Zone 1: July 15, 2025
- Zone 2: July 20, 2025
- Zone 3: July 25, 2025
- Zone 4: July 27, 2025
- Zone 5: July 29, 2025
- Zone 6: July 31, 2025

## Integration Details

### 1. Shapefile Processor Updates
The `ShapeFileProcessor` class has been updated to:
- Extract RID-specific fields from shapefiles
- Map `PARCEL_SEQ` to parcel ID
- Map `sub_member` to zone ID
- Store all RID attributes in a dedicated structure

### 2. Data Conversion
- **Area**: Converted from rai to square meters (1 rai = 1600 m²)
- **Water Allocation**: Converted from seasonal total (m³/rai) to daily allocation (m³/day)
- **Crop Rotation**: Generated from planting date and crop type
- **Coordinate System**: Geometry is in EPSG:32648 (UTM Zone 48N), converted to WGS84

### 3. Storage
RID attributes are stored in the Parcel entity's `properties` field as JSONB with the following structure:
```json
{
  "uploadId": "uuid",
  "ridAttributes": {
    "parcelAreaRai": 10.5,
    "dataDateProcess": "2025-01-15",
    "startInt": "2025-07-15",
    "wpet": 0.85,
    "age": 30,
    "wprod": 0.78,
    "plantId": "rice_rd43",
    "yieldAtMcKgpr": 450,
    "seasonIrrM3PerRai": 1200,
    "autoNote": "{...}"
  },
  "importedAt": "2025-01-15T10:30:00Z"
}
```

## Usage

### Upload RID Shapefile
```bash
# External API endpoint
curl -X POST https://6wls4auo90.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/gis/shapefile/upload \
  -H "Authorization: Bearer munbon-gis-shapefile" \
  -F "file=@rid_shapefile.zip" \
  -F "waterDemandMethod=RID-MS" \
  -F "zone=Zone1"
```

### Check Upload Status
```bash
node deployments/aws-lambda/check-upload-status.js
```

## Next Steps
1. Start the GIS service to process uploaded shapefiles
2. Implement water demand calculations based on RID data
3. Create reports showing water allocation by zone
4. Integrate with irrigation scheduling system