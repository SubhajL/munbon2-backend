const { logger } = require('./logger');

/**
 * Helper utilities for working with GeoPackage API
 */
class GeoPackageHelper {
    /**
     * Extract all rows from a feature table
     * @param {Object} featureDao - Feature DAO from geoPackage.getFeatureDao(tableName)
     * @returns {Promise<Array>} Array of row objects with properties and geometry
     */
    static async extractAllRows(featureDao) {
        const results = [];
        
        try {
            // Get geometry column name
            const geometryColumn = featureDao.geometryColumn || 
                                   (featureDao.geometryColumns && featureDao.geometryColumns[0]) ||
                                   'geom';
            
            // Query for all rows
            let rows;
            if (typeof featureDao.queryForAll === 'function') {
                rows = featureDao.queryForAll();
            } else if (typeof featureDao.queryForEach === 'function') {
                rows = featureDao.queryForEach();
            } else {
                throw new Error('No query method available on featureDao');
            }
            
            // Process each row
            for (const row of rows) {
                const processedRow = this.extractRowData(row, geometryColumn);
                results.push(processedRow);
            }
            
            logger.debug('Extracted rows from feature table', { 
                tableName: featureDao.table_name,
                rowCount: results.length 
            });
            
            return results;
            
        } catch (error) {
            logger.error('Error extracting rows', { 
                error: error.message,
                tableName: featureDao.table_name 
            });
            return results;
        }
    }
    
    /**
     * Extract data from a single row
     * @param {Object} row - Row object from GeoPackage query
     * @param {string} geometryColumn - Name of geometry column
     * @returns {Object} Processed row with properties and geometry
     */
    static extractRowData(row, geometryColumn = 'geom') {
        const result = {
            properties: {},
            geometry: null
        };
        
        // Extract all properties
        for (const key in row) {
            if (key === geometryColumn) {
                // Handle geometry separately
                result.geometry = this.extractGeometry(row[key]);
            } else {
                result.properties[key] = row[key];
            }
        }
        
        return result;
    }
    
    /**
     * Extract geometry from various formats
     * @param {*} geomValue - Geometry value from row
     * @returns {Object|null} GeoJSON geometry object
     */
    static extractGeometry(geomValue) {
        if (!geomValue) return null;
        
        try {
            // If it's already a GeoJSON geometry
            if (geomValue.type && geomValue.coordinates) {
                return geomValue;
            }
            
            // If it's a Buffer (WKB format)
            if (Buffer.isBuffer(geomValue) || (geomValue.data && geomValue.type === 'Buffer')) {
                // For now, return placeholder - would need wkx or similar library for proper parsing
                return {
                    type: 'Point',
                    coordinates: [0, 0],
                    _raw: 'WKB Buffer - needs parsing'
                };
            }
            
            // If it's a string (possibly WKT)
            if (typeof geomValue === 'string') {
                return {
                    type: 'Point',
                    coordinates: [0, 0],
                    _raw: 'WKT String - needs parsing'
                };
            }
            
            // Unknown format
            logger.debug('Unknown geometry format', { 
                type: typeof geomValue,
                keys: Object.keys(geomValue || {})
            });
            
            return null;
            
        } catch (error) {
            logger.error('Error extracting geometry', { error: error.message });
            return null;
        }
    }
    
    /**
     * Get table metadata
     * @param {Object} featureDao - Feature DAO
     * @returns {Object} Table metadata including columns, SRS, etc.
     */
    static getTableMetadata(featureDao) {
        const metadata = {
            tableName: featureDao.table_name || 'unknown',
            columns: [],
            geometryColumn: null,
            srs: null
        };
        
        // Get geometry column
        metadata.geometryColumn = featureDao.geometryColumn || 
                                  (featureDao.geometryColumns && featureDao.geometryColumns[0]) ||
                                  null;
        
        // Get SRS info
        if (featureDao.srs) {
            metadata.srs = {
                srsId: featureDao.srs.srs_id || featureDao.srs.srsId,
                organization: featureDao.srs.organization,
                organizationCoordsysId: featureDao.srs.organization_coordsys_id || featureDao.srs.organizationCoordsysId
            };
        } else if (typeof featureDao.getSrs === 'function') {
            try {
                const srs = featureDao.getSrs();
                if (srs) {
                    metadata.srs = {
                        srsId: srs.srs_id || srs.srsId,
                        organization: srs.organization,
                        organizationCoordsysId: srs.organization_coordsys_id || srs.organizationCoordsysId
                    };
                }
            } catch (e) {
                logger.debug('Could not get SRS', { error: e.message });
            }
        }
        
        // Get column info
        if (featureDao.columns && typeof featureDao.columns === 'object') {
            // columns might be indexed by number or name
            for (const key in featureDao.columns) {
                const col = featureDao.columns[key];
                metadata.columns.push({
                    index: key,
                    name: col.name || col.column_name || key,
                    type: col.dataType || col.data_type || col.type || 'unknown',
                    isPrimary: col.primaryKey || col.pk || false,
                    notNull: col.notNull || col.nn || false
                });
            }
        }
        
        return metadata;
    }
    
    /**
     * Map row data to agricultural plot structure
     * @param {Object} rowData - Row data extracted from GeoPackage
     * @param {string} tableName - Table name for context
     * @returns {Object} Agricultural plot object
     */
    static mapToAgriculturalPlot(rowData, tableName) {
        const props = rowData.properties;
        
        const plot = {
            plot_code: props.PARCEL_SEQ || props.parcel_seq || 
                      props.PARCEL_ID || props.parcel_id || 
                      `RID-${tableName}-${Date.now()}`,
            farmer_id: props.FARMER_ID || props.farmer_id || 
                      props.OWNER_ID || props.owner_id || null,
            area_hectares: null,
            current_crop_type: this.mapCropType(props.plant_id || props.PLANT_ID),
            soil_type: props.SOIL_TYPE || props.soil_type || null,
            planting_date: this.parseDate(props.start_int || props.START_INT),
            properties: {
                ridAttributes: {
                    parcelAreaRai: props.area_rai || props.AREA_RAI || props.parcel_are || props.PARCEL_ARE,
                    dataDateProcess: props.data_date_ || props.DATA_DATE || props.batch_date_int,
                    startInt: props.start_int || props.START_INT,
                    wpet: props.wpet || props.WPET,
                    age: props.age || props.AGE,
                    wprod: props.wprod || props.WPROD,
                    plantId: props.plant_id || props.PLANT_ID,
                    yieldAtMcKgpr: props.yield_at_mc_kgpr || props.YIELD || props.yield_at_m,
                    seasonIrrM3PerRai: props.season_irri_m3_per_rai || props.season_irr || props.SEASON_IRR,
                    autoNote: props.auto_note || props.AUTO_NOTE,
                    stageAge: props.stage_age || props.STAGE_AGE,
                    lat: props.lat || props.LAT,
                    lon: props.lon || props.LON,
                    subMember: props.sub_member || props.SUB_MEMBER || props.zone_area
                },
                originalTable: tableName,
                allProperties: props
            },
            geometry: rowData.geometry
        };
        
        // Calculate area in hectares from rai
        const areaRai = plot.properties.ridAttributes.parcelAreaRai;
        if (areaRai) {
            plot.area_hectares = parseFloat(areaRai) / 6.25;
        }
        
        return plot;
    }
    
    /**
     * Map crop type codes to standard names
     * @param {string} plantId - Plant ID from data
     * @returns {string|null} Standardized crop type
     */
    static mapCropType(plantId) {
        if (!plantId) return null;
        
        const cropMap = {
            '1': 'rice',
            '2': 'maize',
            '3': 'sugarcane',
            '4': 'cassava',
            'rice': 'rice',
            'maize': 'maize',
            'corn': 'maize',
            'sugarcane': 'sugarcane',
            'cassava': 'cassava'
        };
        
        return cropMap[String(plantId).toLowerCase()] || plantId;
    }
    
    /**
     * Parse date from various formats
     * @param {*} dateStr - Date string or value
     * @returns {Date|null} Parsed date
     */
    static parseDate(dateStr) {
        if (!dateStr) return null;
        
        try {
            // Check if it's a YYYYMMDD number format
            if (typeof dateStr === 'number' || /^\d{8}$/.test(String(dateStr))) {
                const str = String(dateStr);
                const year = parseInt(str.substring(0, 4));
                const month = parseInt(str.substring(4, 6)) - 1; // JS months are 0-based
                const day = parseInt(str.substring(6, 8));
                const date = new Date(year, month, day);
                if (!isNaN(date.getTime())) {
                    return date;
                }
            }
            
            // Try standard date parsing
            const date = new Date(dateStr);
            if (!isNaN(date.getTime())) {
                return date;
            }
        } catch (e) {
            // Ignore parse errors
        }
        
        return null;
    }
}

module.exports = { GeoPackageHelper };