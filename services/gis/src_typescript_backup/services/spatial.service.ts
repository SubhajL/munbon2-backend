import { Repository } from 'typeorm';
import * as turf from '@turf/turf';
import { AppDataSource } from '../config/database';
import { config } from '../config';
import { logger } from '../utils/logger';
import { Feature, FeatureCollection, GeoJsonProperties, Geometry } from 'geojson';

interface SpatialQueryOptions {
  geometry?: Geometry;
  distance?: number;
  unit?: turf.Units;
  properties?: string[];
  limit?: number;
  offset?: number;
}

interface BufferOptions {
  distance: number;
  unit?: turf.Units;
  steps?: number;
}

class SpatialService {
  async findWithinBounds(
    tableName: string,
    bounds: [number, number, number, number], // [minX, minY, maxX, maxY]
    options: SpatialQueryOptions = {}
  ): Promise<FeatureCollection> {
    const { properties = ['*'], limit = 1000, offset = 0 } = options;
    
    const query = `
      SELECT 
        ${properties.join(', ')},
        ST_AsGeoJSON(geometry) as geojson
      FROM ${config.database.gisSchema}.${tableName}
      WHERE ST_Intersects(
        geometry,
        ST_MakeEnvelope($1, $2, $3, $4, 4326)
      )
      LIMIT $5 OFFSET $6
    `;
    
    try {
      const results = await AppDataSource.query(query, [...bounds, limit, offset]);
      
      const features = results.map((row: any) => ({
        type: 'Feature',
        geometry: JSON.parse(row.geojson),
        properties: this.extractProperties(row, ['geojson']),
      }));
      
      return {
        type: 'FeatureCollection',
        features,
      };
    } catch (error) {
      logger.error('Error in findWithinBounds:', error);
      throw error;
    }
  }

  async findWithinDistance(
    tableName: string,
    center: [number, number], // [lng, lat]
    distance: number,
    unit: turf.Units = 'meters',
    options: SpatialQueryOptions = {}
  ): Promise<FeatureCollection> {
    const { properties = ['*'], limit = 1000, offset = 0 } = options;
    
    // Convert distance to meters for PostGIS
    const distanceInMeters = turf.convertLength(distance, unit, 'meters');
    
    const query = `
      SELECT 
        ${properties.join(', ')},
        ST_AsGeoJSON(geometry) as geojson,
        ST_Distance(
          ST_Transform(geometry, ${config.spatial.thailandSRID}),
          ST_Transform(ST_SetSRID(ST_MakePoint($1, $2), 4326), ${config.spatial.thailandSRID})
        ) as distance
      FROM ${config.database.gisSchema}.${tableName}
      WHERE ST_DWithin(
        ST_Transform(geometry, ${config.spatial.thailandSRID}),
        ST_Transform(ST_SetSRID(ST_MakePoint($1, $2), 4326), ${config.spatial.thailandSRID}),
        $3
      )
      ORDER BY distance
      LIMIT $4 OFFSET $5
    `;
    
    try {
      const results = await AppDataSource.query(query, [
        center[0],
        center[1],
        distanceInMeters,
        limit,
        offset,
      ]);
      
      const features = results.map((row: any) => ({
        type: 'Feature',
        geometry: JSON.parse(row.geojson),
        properties: {
          ...this.extractProperties(row, ['geojson']),
          distance: row.distance,
        },
      }));
      
      return {
        type: 'FeatureCollection',
        features,
      };
    } catch (error) {
      logger.error('Error in findWithinDistance:', error);
      throw error;
    }
  }

  async findIntersecting(
    tableName: string,
    geometry: Geometry,
    options: SpatialQueryOptions = {}
  ): Promise<FeatureCollection> {
    const { properties = ['*'], limit = 1000, offset = 0 } = options;
    
    const query = `
      SELECT 
        ${properties.join(', ')},
        ST_AsGeoJSON(geometry) as geojson
      FROM ${config.database.gisSchema}.${tableName}
      WHERE ST_Intersects(
        geometry,
        ST_GeomFromGeoJSON($1)
      )
      LIMIT $2 OFFSET $3
    `;
    
    try {
      const results = await AppDataSource.query(query, [
        JSON.stringify(geometry),
        limit,
        offset,
      ]);
      
      const features = results.map((row: any) => ({
        type: 'Feature',
        geometry: JSON.parse(row.geojson),
        properties: this.extractProperties(row, ['geojson']),
      }));
      
      return {
        type: 'FeatureCollection',
        features,
      };
    } catch (error) {
      logger.error('Error in findIntersecting:', error);
      throw error;
    }
  }

  async calculateArea(geometry: Geometry, unit: string = 'hectares'): Promise<number> {
    const query = `
      SELECT ST_Area(
        ST_Transform(
          ST_GeomFromGeoJSON($1),
          ${config.spatial.thailandSRID}
        )
      ) as area
    `;
    
    try {
      const result = await AppDataSource.query(query, [JSON.stringify(geometry)]);
      let area = result[0].area; // square meters
      
      // Convert to requested unit
      switch (unit) {
        case 'hectares':
          return area / 10000;
        case 'acres':
          return area * 0.000247105;
        case 'sqkm':
          return area / 1000000;
        case 'sqm':
        default:
          return area;
      }
    } catch (error) {
      logger.error('Error in calculateArea:', error);
      throw error;
    }
  }

  async calculateLength(geometry: Geometry, unit: string = 'meters'): Promise<number> {
    const query = `
      SELECT ST_Length(
        ST_Transform(
          ST_GeomFromGeoJSON($1),
          ${config.spatial.thailandSRID}
        )
      ) as length
    `;
    
    try {
      const result = await AppDataSource.query(query, [JSON.stringify(geometry)]);
      let length = result[0].length; // meters
      
      // Convert to requested unit
      switch (unit) {
        case 'kilometers':
        case 'km':
          return length / 1000;
        case 'miles':
          return length * 0.000621371;
        case 'feet':
          return length * 3.28084;
        case 'meters':
        default:
          return length;
      }
    } catch (error) {
      logger.error('Error in calculateLength:', error);
      throw error;
    }
  }

  async buffer(geometry: Geometry, options: BufferOptions): Promise<Feature> {
    const { distance, unit = 'meters', steps = 64 } = options;
    
    // Convert distance to meters for PostGIS
    const distanceInMeters = turf.convertLength(distance, unit, 'meters');
    
    const query = `
      SELECT ST_AsGeoJSON(
        ST_Transform(
          ST_Buffer(
            ST_Transform(
              ST_GeomFromGeoJSON($1),
              ${config.spatial.thailandSRID}
            ),
            $2,
            $3
          ),
          4326
        )
      ) as geojson
    `;
    
    try {
      const result = await AppDataSource.query(query, [
        JSON.stringify(geometry),
        distanceInMeters,
        steps,
      ]);
      
      return {
        type: 'Feature',
        geometry: JSON.parse(result[0].geojson),
        properties: {
          bufferDistance: distance,
          bufferUnit: unit,
        },
      };
    } catch (error) {
      logger.error('Error in buffer:', error);
      throw error;
    }
  }

  async union(geometries: Geometry[]): Promise<Feature> {
    const query = `
      SELECT ST_AsGeoJSON(
        ST_Union(
          ARRAY[${geometries.map((_, i) => `ST_GeomFromGeoJSON($${i + 1})`).join(',')}]
        )
      ) as geojson
    `;
    
    try {
      const result = await AppDataSource.query(
        query,
        geometries.map(g => JSON.stringify(g))
      );
      
      return {
        type: 'Feature',
        geometry: JSON.parse(result[0].geojson),
        properties: {},
      };
    } catch (error) {
      logger.error('Error in union:', error);
      throw error;
    }
  }

  async intersection(geometry1: Geometry, geometry2: Geometry): Promise<Feature | null> {
    const query = `
      SELECT ST_AsGeoJSON(
        ST_Intersection(
          ST_GeomFromGeoJSON($1),
          ST_GeomFromGeoJSON($2)
        )
      ) as geojson
    `;
    
    try {
      const result = await AppDataSource.query(query, [
        JSON.stringify(geometry1),
        JSON.stringify(geometry2),
      ]);
      
      if (!result[0].geojson) {
        return null;
      }
      
      return {
        type: 'Feature',
        geometry: JSON.parse(result[0].geojson),
        properties: {},
      };
    } catch (error) {
      logger.error('Error in intersection:', error);
      throw error;
    }
  }

  async simplify(geometry: Geometry, tolerance: number = 0.0001, highQuality: boolean = true): Promise<Feature> {
    const query = `
      SELECT ST_AsGeoJSON(
        ${highQuality ? 'ST_SimplifyPreserveTopology' : 'ST_Simplify'}(
          ST_GeomFromGeoJSON($1),
          $2
        )
      ) as geojson
    `;
    
    try {
      const result = await AppDataSource.query(query, [
        JSON.stringify(geometry),
        tolerance,
      ]);
      
      return {
        type: 'Feature',
        geometry: JSON.parse(result[0].geojson),
        properties: {
          simplified: true,
          tolerance,
          highQuality,
        },
      };
    } catch (error) {
      logger.error('Error in simplify:', error);
      throw error;
    }
  }

  async transform(geometry: Geometry, fromSRID: number, toSRID: number): Promise<Feature> {
    const query = `
      SELECT ST_AsGeoJSON(
        ST_Transform(
          ST_SetSRID(
            ST_GeomFromGeoJSON($1),
            $2
          ),
          $3
        )
      ) as geojson
    `;
    
    try {
      const result = await AppDataSource.query(query, [
        JSON.stringify(geometry),
        fromSRID,
        toSRID,
      ]);
      
      return {
        type: 'Feature',
        geometry: JSON.parse(result[0].geojson),
        properties: {
          fromSRID,
          toSRID,
        },
      };
    } catch (error) {
      logger.error('Error in transform:', error);
      throw error;
    }
  }


  async routeOptimization(
    start: [number, number],
    end: [number, number],
    waypoints?: Array<[number, number]>
  ): Promise<Feature> {
    // This would integrate with routing service
    // For now, return a simple line
    const coordinates = [start, ...(waypoints || []), end];
    
    return {
      type: 'Feature',
      geometry: {
        type: 'LineString',
        coordinates,
      },
      properties: {
        distance: turf.length(turf.lineString(coordinates), { units: 'meters' }),
      },
    };
  }

  async getElevation(lng: number, lat: number): Promise<number> {
    // This would typically query a DEM (Digital Elevation Model) dataset
    // For now, returning a placeholder value
    // In production, this should integrate with elevation data services
    const query = `
      SELECT 
        -- Placeholder: In production, this would query actual elevation data
        -- ST_Value(rast, ST_SetSRID(ST_MakePoint($1, $2), 4326)) as elevation
        100 + (random() * 50) as elevation
      -- FROM gis.elevation_raster
      -- WHERE ST_Intersects(rast, ST_SetSRID(ST_MakePoint($1, $2), 4326))
    `;
    
    try {
      const result = await AppDataSource.query(query, [lng, lat]);
      return result[0]?.elevation || 0;
    } catch (error) {
      logger.error('Error in getElevation:', error);
      throw error;
    }
  }

  private extractProperties(row: any, excludeKeys: string[] = []): GeoJsonProperties {
    const properties: GeoJsonProperties = {};
    
    Object.keys(row).forEach(key => {
      if (!excludeKeys.includes(key)) {
        properties[key] = row[key];
      }
    });
    
    return properties;
  }
}

export const spatialService = new SpatialService();