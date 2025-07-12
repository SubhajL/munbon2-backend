import AdmZip from 'adm-zip';
import { open as openShapefile } from 'shapefile';
import proj4 from 'proj4';
import * as turf from '@turf/turf';
import { Feature, Polygon, MultiPolygon } from 'geojson';
import * as fs from 'fs';
import * as path from 'path';
import { v4 as uuidv4 } from 'uuid';
import { logger } from '../utils/logger';

interface ProcessOptions {
  buffer: Buffer;
  fileName: string;
  uploadId: string;
}

interface ParsedParcel {
  parcelId: string;
  geometry: any;
  area: number;
  zoneId: string;
  subZone?: string;
  ownerName?: string;
  ownerId?: string;
  cropType?: string;
  landUseType?: string;
  attributes: any;
  ridAttributes?: {
    parcelAreaRai?: number;
    dataDateProcess?: string;
    startInt?: string;
    wpet?: number;
    age?: number;
    wprod?: number;
    plantId?: string;
    yieldAtMcKgpr?: number;
    seasonIrrM3PerRai?: number;
    autoNote?: string;
    stageAge?: number;
    lat?: number;
    lon?: number;
    subMember?: number;
  };
}

export class ShapeFileProcessor {
  private readonly tempDir = '/tmp/gis-shape-files';

  constructor() {
    // Ensure temp directory exists
    if (!fs.existsSync(this.tempDir)) {
      fs.mkdirSync(this.tempDir, { recursive: true });
    }
  }

  async processShapeFile(options: ProcessOptions): Promise<ParsedParcel[]> {
    const uploadDir = path.join(this.tempDir, options.uploadId);
    
    try {
      // Create temp directory for this upload
      fs.mkdirSync(uploadDir, { recursive: true });

      // Save and extract zip file
      const zipPath = path.join(uploadDir, options.fileName);
      fs.writeFileSync(zipPath, options.buffer);

      const zip = new AdmZip(zipPath);
      zip.extractAllTo(uploadDir, true);
      
      logger.info('Extracted shape file archive', { uploadDir });

      // Parse shape files
      const parcels = await this.parseShapeFiles(uploadDir);
      
      return parcels;
    } finally {
      // Clean up temp files
      this.cleanupDirectory(uploadDir);
    }
  }

  private async parseShapeFiles(directory: string): Promise<ParsedParcel[]> {
    const files = fs.readdirSync(directory);
    const shpFile = files.find(f => f.toLowerCase().endsWith('.shp'));
    const dbfFile = files.find(f => f.toLowerCase().endsWith('.dbf'));

    if (!shpFile) {
      throw new Error('No .shp file found in archive');
    }

    const shpPath = path.join(directory, shpFile);
    const dbfPath = dbfFile ? path.join(directory, dbfFile) : undefined;

    // Configure coordinate transformation (UTM Zone 48N to WGS84)
    const utm48n = '+proj=utm +zone=48 +datum=WGS84 +units=m +no_defs';
    const wgs84 = '+proj=longlat +datum=WGS84 +no_defs';
    const transform = proj4(utm48n, wgs84);

    const parcels: ParsedParcel[] = [];
    
    // Open shape file
    const source = await openShapefile(shpPath, dbfPath);
    let result = await source.read();
    let index = 0;

    while (!result.done && result.value) {
      const feature = result.value as Feature;
      
      if (feature.geometry.type !== 'Polygon' && feature.geometry.type !== 'MultiPolygon') {
        result = await source.read();
        continue;
      }

      // Transform coordinates from UTM to WGS84
      const transformedGeometry = this.transformCoordinates(feature.geometry, transform);
      
      // Calculate area in square meters
      const area = turf.area(transformedGeometry);
      
      // Extract properties (handle both English and Thai field names)
      const props = feature.properties || {};
      const parcel = this.extractParcelProperties(props, index);
      
      parcels.push({
        parcelId: parcel.parcelId || `P${Date.now()}-${index}`,
        zoneId: parcel.zoneId || '1',
        geometry: transformedGeometry,
        area,
        attributes: props,
        subZone: parcel.subZone,
        ownerName: parcel.ownerName,
        ownerId: parcel.ownerId,
        cropType: parcel.cropType,
        landUseType: parcel.landUseType,
        ridAttributes: parcel.ridAttributes,
      } as ParsedParcel);

      index++;
      result = await source.read();
    }

    logger.info('Parsed parcels from shape file', { count: parcels.length });
    return parcels;
  }

  private transformCoordinates(geometry: any, transform: any): any {
    if (geometry.type === 'Polygon') {
      return {
        type: 'Polygon',
        coordinates: geometry.coordinates.map((ring: number[][]) =>
          ring.map((coord: number[]) => transform.forward(coord))
        ),
      };
    } else if (geometry.type === 'MultiPolygon') {
      return {
        type: 'MultiPolygon',
        coordinates: geometry.coordinates.map((polygon: number[][][]) =>
          polygon.map((ring: number[][]) =>
            ring.map((coord: number[]) => transform.forward(coord))
          )
        ),
      };
    }
    return geometry;
  }

  private extractParcelProperties(props: any, index: number): Partial<ParsedParcel> {
    // Handle RID shapefile fields based on actual field names
    const fieldMappings = {
      parcelId: ['PARCEL_SEQ', 'PARCEL_ID', 'parcel_id', 'ID', 'id', 'แปลง', 'รหัสแปลง'],
      zone: ['sub_member', 'ZONE', 'zone', 'Zone_ID', 'zone_id', 'โซน'],
      subZone: ['SUBZONE', 'subzone', 'Sub_Zone', 'sub_zone', 'โซนย่อย'],
      ownerName: ['OWNER', 'owner', 'Owner_Name', 'owner_name', 'ชื่อเจ้าของ', 'ชื่อ'],
      ownerId: ['OWNER_ID', 'owner_id', 'Owner_ID', 'รหัสเจ้าของ'],
      cropType: ['plant_id', 'CROP', 'crop', 'Crop_Type', 'crop_type', 'พืช', 'ชนิดพืช'],
      landUseType: ['LANDUSE', 'landuse', 'Land_Use', 'land_use', 'การใช้ที่ดิน'],
    };

    const extracted: any = {
      parcelId: `P${Date.now()}-${index}`, // Default if not found
    };

    // Extract values based on field mappings
    for (const [key, possibleNames] of Object.entries(fieldMappings)) {
      for (const fieldName of possibleNames) {
        if (props[fieldName] !== undefined && props[fieldName] !== null) {
          extracted[key] = props[fieldName];
          break;
        }
      }
    }

    // Handle RID-specific fields
    if (props.PARCEL_SEQ) {
      extracted.parcelId = props.PARCEL_SEQ;
    }
    
    if (props.sub_member) {
      extracted.zone = `Zone${props.sub_member}`;
      extracted.zoneId = String(props.sub_member);
    } else if (!extracted.zone) {
      extracted.zone = 'Zone1'; // Default zone
      extracted.zoneId = '1';
    } else {
      // Extract zone ID from zone string (e.g., "Zone1" -> "1")
      const zoneMatch = String(extracted.zone).match(/\d+/);
      extracted.zoneId = zoneMatch ? zoneMatch[0] : '1';
    }

    // Add RID-specific attributes that should be stored
    // Field names match exactly what's in the RID shapefile
    extracted.ridAttributes = {
      parcelAreaRai: props.parcel_are,  // Actual field is 'parcel_are' not 'parcel_area_rai'
      dataDateProcess: props.data_date_, // Actual field is 'data_date_' not 'data_date_process'
      startInt: props.start_int,
      wpet: props.wpet,
      age: props.age,
      wprod: props.wprod,
      plantId: props.plant_id,
      yieldAtMcKgpr: props.yield_at_m,  // Actual field is 'yield_at_m' not 'yield_at_mc_kgpr'
      seasonIrrM3PerRai: props.season_irr, // Actual field is 'season_irr' not 'season_irr_m3_per_rai'
      autoNote: props.auto_note,
      // Additional fields from shapefile
      stageAge: props.stage_age,
      lat: props.lat,
      lon: props.lon,
      // Store the sub_member as it represents the zone
      subMember: props.sub_member,
    };

    return extracted;
  }

  private cleanupDirectory(directory: string) {
    try {
      if (fs.existsSync(directory)) {
        fs.rmSync(directory, { recursive: true, force: true });
      }
    } catch (error) {
      logger.warn('Failed to cleanup temporary directory', { error, directory });
    }
  }
}