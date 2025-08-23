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
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.GeoPackageProcessor = void 0;
const geopackage_1 = require("@ngageoint/geopackage");
const turf = __importStar(require("@turf/turf"));
const proj4_1 = __importDefault(require("proj4"));
const logger_1 = require("../utils/logger");
const parcel_entity_1 = require("../models/parcel.entity");
const zone_entity_1 = require("../models/zone.entity");
const database_1 = require("../config/database");
const uuid_1 = require("uuid");
class GeoPackageProcessor {
    parcelRepository = database_1.AppDataSource.getRepository(parcel_entity_1.Parcel);
    zoneRepository = database_1.AppDataSource.getRepository(zone_entity_1.Zone);
    async processGeoPackageFile(filePath, uploadId) {
        const results = [];
        let geoPackage = null;
        try {
            logger_1.logger.info('Opening GeoPackage file', { filePath });
            geoPackage = await geopackage_1.GeoPackageAPI.open(filePath);
            const featureTables = geoPackage.getFeatureTables();
            logger_1.logger.info('Found feature tables', { tables: featureTables });
            for (const tableName of featureTables) {
                const result = await this.processFeatureTable(geoPackage, tableName, uploadId);
                results.push(result);
            }
            return results;
        }
        catch (error) {
            logger_1.logger.error('Error processing GeoPackage', { error, filePath });
            throw error;
        }
        finally {
            if (geoPackage) {
                geoPackage.close();
            }
        }
    }
    async processFeatureTable(geoPackage, tableName, uploadId) {
        const result = {
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
            logger_1.logger.info('Processing feature table', {
                tableName,
                srs: result.metadata.sourceSRS,
                columnNames: featureDao.columnNames
            });
            const features = featureDao.queryForAll();
            result.metadata.totalFeatures = features.length;
            const sourceProjection = this.getProjectionString(srs);
            const targetProjection = 'EPSG:4326';
            for (const row of features) {
                try {
                    const feature = featureDao.getFeature(row);
                    const processed = await this.processFeature(feature, tableName, uploadId, sourceProjection, targetProjection);
                    if (processed) {
                        if (this.isZoneFeature(tableName, feature)) {
                            result.zones.push(processed);
                        }
                        else {
                            result.parcels.push(processed);
                        }
                        result.metadata.processedFeatures++;
                    }
                }
                catch (featureError) {
                    logger_1.logger.error('Error processing feature', { featureError, tableName });
                    result.metadata.failedFeatures++;
                }
            }
            logger_1.logger.info('Completed processing table', {
                tableName,
                processed: result.metadata.processedFeatures,
                failed: result.metadata.failedFeatures
            });
        }
        catch (error) {
            logger_1.logger.error('Error processing feature table', { error, tableName });
            throw error;
        }
        return result;
    }
    async processFeature(feature, tableName, uploadId, sourceProjection, targetProjection) {
        try {
            const geometry = feature.geometry;
            if (!geometry) {
                logger_1.logger.warn('Feature has no geometry', { featureId: feature.id });
                return null;
            }
            const transformedGeometry = this.transformGeometry(geometry, sourceProjection, targetProjection);
            const properties = feature.properties || {};
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
                    ...properties
                }
            };
            if (this.isZoneFeature(tableName, feature)) {
                return {
                    id: (0, uuid_1.v4)(),
                    zoneCode: properties.ZONE_CODE || properties.zone_code || `Z-${feature.id}`,
                    zoneName: properties.ZONE_NAME || properties.zone_name || tableName,
                    zoneType: 'irrigation',
                    areaHectares: this.calculateAreaHectares(transformedGeometry),
                    ...commonFields
                };
            }
            else {
                const areaHectares = this.calculateAreaHectares(transformedGeometry);
                const areaRai = this.calculateAreaRai(areaHectares);
                logger_1.logger.debug('Calculated area for parcel', {
                    plotCode: properties.PARCEL_ID || properties.parcel_id || `P-${tableName}-${feature.id}`,
                    areaHectares,
                    areaRai
                });
                return {
                    id: (0, uuid_1.v4)(),
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
                };
            }
        }
        catch (error) {
            logger_1.logger.error('Error processing feature', { error });
            return null;
        }
    }
    transformGeometry(geometry, sourceProj, targetProj) {
        try {
            if (geometry.type && geometry.coordinates) {
                const transform = (0, proj4_1.default)(sourceProj, targetProj);
                const transformCoords = (coords) => {
                    if (typeof coords[0] === 'number') {
                        return transform.forward(coords);
                    }
                    else {
                        return coords.map((c) => transformCoords(c));
                    }
                };
                return {
                    type: geometry.type,
                    coordinates: transformCoords(geometry.coordinates)
                };
            }
            return geometry;
        }
        catch (error) {
            logger_1.logger.error('Error transforming geometry', { error, sourceProj, targetProj });
            return geometry;
        }
    }
    getProjectionString(srs) {
        if (!srs)
            return 'EPSG:4326';
        if (srs.organization_coordsys_id === 32647) {
            return 'EPSG:32647';
        }
        else if (srs.organization_coordsys_id === 32648) {
            return 'EPSG:32648';
        }
        else if (srs.organization === 'EPSG' && srs.organization_coordsys_id) {
            return `EPSG:${srs.organization_coordsys_id}`;
        }
        if (srs.definition) {
            return srs.definition;
        }
        return 'EPSG:4326';
    }
    calculateAreaHectares(geometry) {
        try {
            const area = turf.area(geometry);
            return area / 10000;
        }
        catch (error) {
            logger_1.logger.error('Error calculating area', { error });
            return 0;
        }
    }
    calculateAreaRai(areaHectares) {
        return areaHectares * 6.25;
    }
    isZoneFeature(tableName, feature) {
        if (tableName.toLowerCase().includes('zone') ||
            tableName.toLowerCase().includes('district') ||
            tableName.toLowerCase().includes('boundary')) {
            return true;
        }
        const props = feature.properties || {};
        if (props.ZONE_CODE || props.zone_code ||
            props.DISTRICT || props.district) {
            return true;
        }
        return false;
    }
    async saveProcessingResults(results) {
        let totalParcels = 0;
        let totalZones = 0;
        const errors = [];
        for (const result of results) {
            try {
                if (result.parcels.length > 0) {
                    const savedParcels = await this.parcelRepository.save(result.parcels);
                    totalParcels += savedParcels.length;
                    logger_1.logger.info('Saved parcels', {
                        tableName: result.metadata.tableName,
                        count: savedParcels.length
                    });
                }
                if (result.zones.length > 0) {
                    const savedZones = await this.zoneRepository.save(result.zones);
                    totalZones += savedZones.length;
                    logger_1.logger.info('Saved zones', {
                        tableName: result.metadata.tableName,
                        count: savedZones.length
                    });
                }
            }
            catch (error) {
                const errorMsg = `Error saving results from ${result.metadata.tableName}: ${error.message}`;
                logger_1.logger.error(errorMsg, { error });
                errors.push(errorMsg);
            }
        }
        return { totalParcels, totalZones, errors };
    }
}
exports.GeoPackageProcessor = GeoPackageProcessor;
//# sourceMappingURL=geopackage-processor.js.map