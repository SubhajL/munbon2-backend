/**
 * RID Shapefile Data Dictionary Types
 * Based on DataDictionary_ridplan_result.docx
 */

export interface RIDShapefileProperties {
  /**
   * รหัสอ้างอิงรูปแปลง - Parcel reference ID
   */
  PARCEL_SEQ: string;

  /**
   * เลขที่โซน - Zone number (1-6)
   */
  sub_member: number;

  /**
   * พื้นที่รูปแปลง (ไร่) - Parcel area in rai
   */
  parcel_area_rai: number;

  /**
   * วันที่ของข้อมูล - Data processing date
   */
  data_date_process: string;

  /**
   * วันเริ่มปลูก - Planting start date
   */
  start_int: string;

  /**
   * ประสิทธิภาพการใช้น้ำด้านการเกษตร (ทั้งรอบการเพาะปลูก)
   * Water use efficiency for agriculture (entire planting cycle)
   */
  wpet: number;

  /**
   * อายุพืช - Plant age
   */
  age: number;

  /**
   * ผลิตภาพการใช้น้ำด้านการเกษตร (ทั้งรอบการเพาะปลูก)
   * Water productivity for agriculture (entire planting cycle)
   */
  wprod: number;

  /**
   * ชนิดพืช - Plant/crop type ID
   */
  plant_id: string;

  /**
   * ผลผลิต kg/rai - Yield in kg per rai
   */
  yield_at_mc_kgpr: number;

  /**
   * ความต้องการใช้น้ำด้านการเกษตร (ทั้งรอบการเพาะปลูก) หน่วย m3 ต่อไร่
   * Agricultural water demand (entire planting cycle) in m3 per rai
   */
  season_irr_m3_per_rai: number;

  /**
   * วันที่มีการให้น้ำในแปลงนั้นๆ ในรูปแบบ json
   * Irrigation dates for the parcel in JSON format
   */
  auto_note: string;
}

/**
 * Zone planting start dates as of 2025
 */
export const ZONE_PLANTING_DATES = {
  1: '2025-07-15', // Zone 1: 15 กค 68
  2: '2025-07-20', // Zone 2: 20 กค 68
  3: '2025-07-25', // Zone 3: 25 กค 68
  4: '2025-07-27', // Zone 4: 27 กค 68
  5: '2025-07-29', // Zone 5: 29 กค 68
  6: '2025-07-31', // Zone 6: 31 กค 68
};

/**
 * Shapefile feature structure
 * Geometry is in EPSG:32648 (UTM Zone 48N)
 */
export interface RIDShapefileFeature {
  type: 'Feature';
  geometry: {
    type: 'Polygon' | 'MultiPolygon';
    coordinates: number[][][] | number[][][][];
  };
  properties: RIDShapefileProperties;
}

export interface RIDShapefileCollection {
  type: 'FeatureCollection';
  features: RIDShapefileFeature[];
  crs?: {
    type: 'name';
    properties: {
      name: 'EPSG:32648';
    };
  };
}