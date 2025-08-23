import { GeoPackageAPI, GeoPackage as GP } from '@ngageoint/geopackage';
import * as turf from '@turf/turf';
import proj4 from 'proj4';
import { logger } from '../utils/logger';
import { Parcel } from '../models/parcel.entity';
import { Zone } from '../models/zone.entity';
import { AppDataSource } from '../config/database';
import { v4 as uuidv4 } from 'uuid';

interface ProcessingResult {
  parcels: Partial<Parcel>[];
  zones: Partial<Zone>[];
  metadata: {
    totalFeatures: number;
    processedFeatures: number;
    failedFeatures: number;
    sourceSRS?: string;
    tableName: string;
  };
}

export class GeoPackageProcessor {
  private parcelRepository = AppDataSource.getRepository(Parcel);
  private zoneRepository = AppDataSource.getRepository(Zone);

  async processGeoPackageFile(filePath: string, uploadId: string): Promise<ProcessingResult[]> {
    const results: ProcessingResult[] = [];
    let geoPackage: GP | null = null;

    try {
      // Open GeoPackage file
      logger.info('Opening GeoPackage file', { filePath });
      geoPackage = await GeoPackageAPI.open(filePath);
      
      // Get all feature tables
      const featureTables = geoPackage.getFeatureTables();
      logger.info('Found feature tables', { tables: featureTables });

      for (const tableName of featureTables) {
        const result = await this.processFeatureTable(geoPackage, tableName, uploadId);
        results.push(result);
      }

      return results;
    } catch (error) {
      logger.error('Error processing GeoPackage', { error, filePath });
      throw error;
    } finally {
      if (geoPackage) {
        geoPackage.close();
      }
    }
  }

  private async processFeatureTable(
    geoPackage: any, 
    tableName: string, 
    uploadId: string
  ): Promise<ProcessingResult> {
    const result: ProcessingResult = {
      parcels: [],
      zones: [],
      metadata: {
        totalFeatures: 0,
        processedFeatures: 0,
        failedFeatures: 0,
        tableName
      }
    };

    try {
      const featureDao = geoPackage.getFeatureDao(tableName);
      const srs = featureDao.getSrs();
      result.metadata.sourceSRS = srs?.organization + ':' + srs?.organization_coordsys_id;
      
      logger.info('Processing feature table', { 
        tableName, 
        srs: result.metadata.sourceSRS,
        columnNames: featureDao.columnNames 
      });

      // Get all features
      const features = featureDao.queryForAll();
      result.metadata.totalFeatures = features.length;

      // Define projection transformation
      const sourceProjection = this.getProjectionString(srs);
      const targetProjection = 'EPSG:4326'; // WGS84

      for (const row of features) {
        try {
          const feature = featureDao.getFeature(row);
          const processed = await this.processFeature(
            feature, 
            tableName, 
            uploadId, 
            sourceProjection, 
            targetProjection
          );

          if (processed) {
            // Determine if it's a parcel or zone based on attributes or table name
            if (this.isZoneFeature(tableName, feature)) {
              result.zones.push(processed as Partial<Zone>);
            } else {
              result.parcels.push(processed as Partial<Parcel>);
            }
            result.metadata.processedFeatures++;
          }
        } catch (featureError) {
          logger.error('Error processing feature', { featureError, tableName });
          result.metadata.failedFeatures++;
        }
      }

      logger.info('Completed processing table', { 
        tableName, 
        processed: result.metadata.processedFeatures,
        failed: result.metadata.failedFeatures 
      });

    } catch (error) {
      logger.error('Error processing feature table', { error, tableName });
      throw error;
    }

    return result;
  }

  private async processFeature(
    feature: any,
    tableName: string,
    uploadId: string,
    sourceProjection: string,
    targetProjection: string
  ): Promise<Partial<Parcel> | Partial<Zone> | null> {
    try {
      // Get geometry
      const geometry = feature.geometry;
      if (!geometry) {
        logger.warn('Feature has no geometry', { featureId: feature.id });
        return null;
      }

      // Transform coordinates to WGS84
      const transformedGeometry = this.transformGeometry(
        geometry, 
        sourceProjection, 
        targetProjection
      );

      // Extract properties
      const properties = feature.properties || {};
      
      // Common fields for RID data
      const commonFields = {
        boundary: transformedGeometry,
        properties: {
          uploadId,
          originalTableName: tableName,
          ridAttributes: {
            parcelAreaRai: properties.AREA_RAI || properties.area_rai || properties.AreaRai,
            dataDateProcess: properties.DATA_DATE || properties.date_process,
            startInt: properties.START_INT || properties.start_interval,
            wpet: properties.WPET || properties.water_pet,
            age: properties.AGE || properties.plant_age,
            wprod: properties.WPROD || properties.water_prod,
            plantId: properties.PLANT_ID || properties.plant_id,
            yieldAtMcKgpr: properties.YIELD || properties.yield_kg_rai,
            seasonIrrM3PerRai: properties.SEASON_IRR || properties.irrigation_m3,
            autoNote: properties.NOTE || properties.auto_note,
          },
          lastUpdated: new Date(),
          ...properties // Store all original properties
        }
      };

      // Check if this is a zone feature
      if (this.isZoneFeature(tableName, feature)) {
        return {
          id: uuidv4(),
          zoneCode: properties.ZONE_CODE || properties.zone_code || `Z-${feature.id}`,
          zoneName: properties.ZONE_NAME || properties.zone_name || tableName,
          zoneType: 'irrigation',
          areaHectares: this.calculateAreaHectares(transformedGeometry),
          ...commonFields
        } as Partial<Zone>;
      } else {
        // Process as parcel
        const areaHectares = this.calculateAreaHectares(transformedGeometry);
        const areaRai = this.calculateAreaRai(areaHectares);
        
        // Log area calculation for verification
        logger.debug('Calculated area for parcel', {
          plotCode: properties.PARCEL_ID || properties.parcel_id || `P-${tableName}-${feature.id}`,
          areaHectares,
          areaRai
        });
        
        return {
          id: uuidv4(),
          plotCode: properties.PARCEL_ID || properties.parcel_id || 
                   properties.PLOT_CODE || properties.plot_code || 
                   `P-${tableName}-${feature.id}`,
          farmerId: properties.FARMER_ID || properties.farmer_id || 
                   properties.OWNER_ID || properties.owner_id || 'unknown',
          areaHectares,
          currentCropType: properties.CROP_TYPE || properties.crop_type || 
                         properties.CROP || 'rice',
          soilType: properties.SOIL_TYPE || properties.soil_type,
          ...commonFields
        } as Partial<Parcel>;
      }
    } catch (error) {
      logger.error('Error processing feature', { error });
      return null;
    }
  }

  private transformGeometry(geometry: any, sourceProj: string, targetProj: string): any {
    try {
      // Handle GeoJSON geometry
      if (geometry.type && geometry.coordinates) {
        // Define the transformation
        const transform = proj4(sourceProj, targetProj);
        
        // Transform coordinates recursively
        const transformCoords = (coords: any): any => {
          if (typeof coords[0] === 'number') {
            // This is a coordinate pair
            return transform.forward(coords);
          } else {
            // This is an array of coordinates
            return coords.map((c: any) => transformCoords(c));
          }
        };

        return {
          type: geometry.type,
          coordinates: transformCoords(geometry.coordinates)
        };
      }
      
      return geometry;
    } catch (error) {
      logger.error('Error transforming geometry', { error, sourceProj, targetProj });
      // Return original geometry if transformation fails
      return geometry;
    }
  }

  private getProjectionString(srs: any): string {
    if (!srs) return 'EPSG:4326'; // Default to WGS84

    // Check common Thailand projections
    if (srs.organization_coordsys_id === 32647) {
      return 'EPSG:32647'; // WGS 84 / UTM zone 47N
    } else if (srs.organization_coordsys_id === 32648) {
      return 'EPSG:32648'; // WGS 84 / UTM zone 48N
    } else if (srs.organization === 'EPSG' && srs.organization_coordsys_id) {
      return `EPSG:${srs.organization_coordsys_id}`;
    }

    // Try to parse from WKT if available
    if (srs.definition) {
      return srs.definition;
    }

    return 'EPSG:4326'; // Default fallback
  }

  private calculateAreaHectares(geometry: any): number {
    try {
      // Calculate area in square meters and convert to hectares
      const area = turf.area(geometry);
      return area / 10000; // Convert m² to hectares
    } catch (error) {
      logger.error('Error calculating area', { error });
      return 0;
    }
  }

  private calculateAreaRai(areaHectares: number): number {
    // Convert hectares to rai (1 hectare = 6.25 rai)
    return areaHectares * 6.25;
  }

  private isZoneFeature(tableName: string, feature: any): boolean {
    // Check table name
    if (tableName.toLowerCase().includes('zone') || 
        tableName.toLowerCase().includes('district') ||
        tableName.toLowerCase().includes('boundary')) {
      return true;
    }

    // Check properties
    const props = feature.properties || {};
    if (props.ZONE_CODE || props.zone_code || 
        props.DISTRICT || props.district) {
      return true;
    }

    return false;
  }

  async saveProcessingResults(results: ProcessingResult[]): Promise<{
    totalParcels: number;
    totalZones: number;
    errors: string[];
  }> {
    let totalParcels = 0;
    let totalZones = 0;
    const errors: string[] = [];

    for (const result of results) {
      try {
        // Save parcels
        if (result.parcels.length > 0) {
          const savedParcels = await this.parcelRepository.save(result.parcels);
          totalParcels += savedParcels.length;
          logger.info('Saved parcels', { 
            tableName: result.metadata.tableName, 
            count: savedParcels.length 
          });
        }

        // Save zones
        if (result.zones.length > 0) {
          const savedZones = await this.zoneRepository.save(result.zones);
          totalZones += savedZones.length;
          logger.info('Saved zones', { 
            tableName: result.metadata.tableName, 
            count: savedZones.length 
          });
        }
      } catch (error: any) {
        const errorMsg = `Error saving results from ${result.metadata.tableName}: ${error.message}`;
        logger.error(errorMsg, { error });
        errors.push(errorMsg);
      }
    }

    return { totalParcels, totalZones, errors };
  }
}