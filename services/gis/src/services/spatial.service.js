"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.spatialService = void 0;
const turf = __importStar(require("@turf/turf"));
const database_1 = require("../config/database");
const config_1 = require("../config");
const logger_1 = require("../utils/logger");
class SpatialService {
    async findWithinBounds(tableName, bounds, options = {}) {
        const { properties = ['*'], limit = 1000, offset = 0 } = options;
        const query = `
      SELECT 
        ${properties.join(', ')},
        ST_AsGeoJSON(geometry) as geojson
      FROM ${config_1.config.database.gisSchema}.${tableName}
      WHERE ST_Intersects(
        geometry,
        ST_MakeEnvelope($1, $2, $3, $4, 4326)
      )
      LIMIT $5 OFFSET $6
    `;
        try {
            const results = await database_1.AppDataSource.query(query, [...bounds, limit, offset]);
            const features = results.map((row) => ({
                type: 'Feature',
                geometry: JSON.parse(row.geojson),
                properties: this.extractProperties(row, ['geojson']),
            }));
            return {
                type: 'FeatureCollection',
                features,
            };
        }
        catch (error) {
            logger_1.logger.error('Error in findWithinBounds:', error);
            throw error;
        }
    }
    async findWithinDistance(tableName, center, distance, unit = 'meters', options = {}) {
        const { properties = ['*'], limit = 1000, offset = 0 } = options;
        const distanceInMeters = turf.convertLength(distance, unit, 'meters');
        const query = `
      SELECT 
        ${properties.join(', ')},
        ST_AsGeoJSON(geometry) as geojson,
        ST_Distance(
          ST_Transform(geometry, ${config_1.config.spatial.thailandSRID}),
          ST_Transform(ST_SetSRID(ST_MakePoint($1, $2), 4326), ${config_1.config.spatial.thailandSRID})
        ) as distance
      FROM ${config_1.config.database.gisSchema}.${tableName}
      WHERE ST_DWithin(
        ST_Transform(geometry, ${config_1.config.spatial.thailandSRID}),
        ST_Transform(ST_SetSRID(ST_MakePoint($1, $2), 4326), ${config_1.config.spatial.thailandSRID}),
        $3
      )
      ORDER BY distance
      LIMIT $4 OFFSET $5
    `;
        try {
            const results = await database_1.AppDataSource.query(query, [
                center[0],
                center[1],
                distanceInMeters,
                limit,
                offset,
            ]);
            const features = results.map((row) => ({
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
        }
        catch (error) {
            logger_1.logger.error('Error in findWithinDistance:', error);
            throw error;
        }
    }
    async findIntersecting(tableName, geometry, options = {}) {
        const { properties = ['*'], limit = 1000, offset = 0 } = options;
        const query = `
      SELECT 
        ${properties.join(', ')},
        ST_AsGeoJSON(geometry) as geojson
      FROM ${config_1.config.database.gisSchema}.${tableName}
      WHERE ST_Intersects(
        geometry,
        ST_GeomFromGeoJSON($1)
      )
      LIMIT $2 OFFSET $3
    `;
        try {
            const results = await database_1.AppDataSource.query(query, [
                JSON.stringify(geometry),
                limit,
                offset,
            ]);
            const features = results.map((row) => ({
                type: 'Feature',
                geometry: JSON.parse(row.geojson),
                properties: this.extractProperties(row, ['geojson']),
            }));
            return {
                type: 'FeatureCollection',
                features,
            };
        }
        catch (error) {
            logger_1.logger.error('Error in findIntersecting:', error);
            throw error;
        }
    }
    async calculateArea(geometry, unit = 'hectares') {
        const query = `
      SELECT ST_Area(
        ST_Transform(
          ST_GeomFromGeoJSON($1),
          ${config_1.config.spatial.thailandSRID}
        )
      ) as area
    `;
        try {
            const result = await database_1.AppDataSource.query(query, [JSON.stringify(geometry)]);
            let area = result[0].area;
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
        }
        catch (error) {
            logger_1.logger.error('Error in calculateArea:', error);
            throw error;
        }
    }
    async calculateLength(geometry, unit = 'meters') {
        const query = `
      SELECT ST_Length(
        ST_Transform(
          ST_GeomFromGeoJSON($1),
          ${config_1.config.spatial.thailandSRID}
        )
      ) as length
    `;
        try {
            const result = await database_1.AppDataSource.query(query, [JSON.stringify(geometry)]);
            let length = result[0].length;
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
        }
        catch (error) {
            logger_1.logger.error('Error in calculateLength:', error);
            throw error;
        }
    }
    async buffer(geometry, options) {
        const { distance, unit = 'meters', steps = 64 } = options;
        const distanceInMeters = turf.convertLength(distance, unit, 'meters');
        const query = `
      SELECT ST_AsGeoJSON(
        ST_Transform(
          ST_Buffer(
            ST_Transform(
              ST_GeomFromGeoJSON($1),
              ${config_1.config.spatial.thailandSRID}
            ),
            $2,
            $3
          ),
          4326
        )
      ) as geojson
    `;
        try {
            const result = await database_1.AppDataSource.query(query, [
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
        }
        catch (error) {
            logger_1.logger.error('Error in buffer:', error);
            throw error;
        }
    }
    async union(geometries) {
        const query = `
      SELECT ST_AsGeoJSON(
        ST_Union(
          ARRAY[${geometries.map((_, i) => `ST_GeomFromGeoJSON($${i + 1})`).join(',')}]
        )
      ) as geojson
    `;
        try {
            const result = await database_1.AppDataSource.query(query, geometries.map(g => JSON.stringify(g)));
            return {
                type: 'Feature',
                geometry: JSON.parse(result[0].geojson),
                properties: {},
            };
        }
        catch (error) {
            logger_1.logger.error('Error in union:', error);
            throw error;
        }
    }
    async intersection(geometry1, geometry2) {
        const query = `
      SELECT ST_AsGeoJSON(
        ST_Intersection(
          ST_GeomFromGeoJSON($1),
          ST_GeomFromGeoJSON($2)
        )
      ) as geojson
    `;
        try {
            const result = await database_1.AppDataSource.query(query, [
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
        }
        catch (error) {
            logger_1.logger.error('Error in intersection:', error);
            throw error;
        }
    }
    async simplify(geometry, tolerance = 0.0001, highQuality = true) {
        const query = `
      SELECT ST_AsGeoJSON(
        ${highQuality ? 'ST_SimplifyPreserveTopology' : 'ST_Simplify'}(
          ST_GeomFromGeoJSON($1),
          $2
        )
      ) as geojson
    `;
        try {
            const result = await database_1.AppDataSource.query(query, [
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
        }
        catch (error) {
            logger_1.logger.error('Error in simplify:', error);
            throw error;
        }
    }
    async transform(geometry, fromSRID, toSRID) {
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
            const result = await database_1.AppDataSource.query(query, [
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
        }
        catch (error) {
            logger_1.logger.error('Error in transform:', error);
            throw error;
        }
    }
    async routeOptimization(start, end, waypoints) {
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
    async getElevation(lng, lat) {
        const query = `
      SELECT 
        -- Placeholder: In production, this would query actual elevation data
        -- ST_Value(rast, ST_SetSRID(ST_MakePoint($1, $2), 4326)) as elevation
        100 + (random() * 50) as elevation
      -- FROM gis.elevation_raster
      -- WHERE ST_Intersects(rast, ST_SetSRID(ST_MakePoint($1, $2), 4326))
    `;
        try {
            const result = await database_1.AppDataSource.query(query, [lng, lat]);
            return result[0]?.elevation || 0;
        }
        catch (error) {
            logger_1.logger.error('Error in getElevation:', error);
            throw error;
        }
    }
    extractProperties(row, excludeKeys = []) {
        const properties = {};
        Object.keys(row).forEach(key => {
            if (!excludeKeys.includes(key)) {
                properties[key] = row[key];
            }
        });
        return properties;
    }
}
exports.spatialService = new SpatialService();
//# sourceMappingURL=spatial.service.js.map