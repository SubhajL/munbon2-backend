const { GeoPackageAPI } = require('@ngageoint/geopackage');
const { logger } = require('../utils/logger');
const fs = require('fs');
const path = require('path');

/**
 * Test extractor to understand GeoPackage API structure
 */
class GeoPackageTestExtractor {
    /**
     * Opens a GeoPackage file and logs all available methods and structures
     * @param {string} filePath - Path to the GeoPackage file
     * @returns {Promise<Object>} Analysis results
     */
    async testExtractGeoPackage(filePath) {
        let geoPackage = null;
        const results = {
            filePath,
            tables: [],
            apiMethods: {},
            errors: []
        };

        try {
            logger.info('Opening test GeoPackage', { filePath });
            
            if (!fs.existsSync(filePath)) {
                throw new Error(`File not found: ${filePath}`);
            }

            geoPackage = await GeoPackageAPI.open(filePath);
            
            // Log GeoPackage methods
            results.apiMethods.geoPackage = Object.getOwnPropertyNames(Object.getPrototypeOf(geoPackage))
                .filter(method => typeof geoPackage[method] === 'function')
                .sort();
            
            logger.info('GeoPackage API methods', { 
                methods: results.apiMethods.geoPackage.slice(0, 20) 
            });

            // Get feature tables
            const featureTables = geoPackage.getFeatureTables();
            logger.info('Found feature tables', { tables: featureTables });
            
            // Analyze each table
            for (const tableName of featureTables) {
                const tableInfo = await this.dumpTableStructure(geoPackage, tableName);
                results.tables.push(tableInfo);
            }
            
            return results;
            
        } catch (error) {
            logger.error('Error in test extraction', { error: error.message });
            results.errors.push(error.message);
            return results;
        } finally {
            if (geoPackage) {
                try {
                    geoPackage.close();
                } catch (e) {
                    // Ignore close errors
                }
            }
        }
    }

    /**
     * Logs column names, types, spatial reference system, and row count
     * @param {Object} geoPackage - Open GeoPackage instance
     * @param {string} tableName - Table name to analyze
     * @returns {Promise<Object>} Table structure information
     */
    async dumpTableStructure(geoPackage, tableName) {
        const tableInfo = {
            tableName,
            columns: [],
            rowCount: 0,
            srs: null,
            sampleRows: [],
            daoMethods: []
        };

        try {
            const featureDao = geoPackage.getFeatureDao(tableName);
            
            // Log DAO methods
            tableInfo.daoMethods = Object.getOwnPropertyNames(Object.getPrototypeOf(featureDao))
                .filter(method => typeof featureDao[method] === 'function')
                .sort();
            
            logger.info('FeatureDao methods', { 
                tableName,
                methods: tableInfo.daoMethods.slice(0, 20)
            });

            // Get table info - check different properties
            if (featureDao.table && featureDao.table.table_name) {
                tableInfo.tableName = featureDao.table.table_name;
            } else if (featureDao.table_name) {
                tableInfo.tableName = featureDao.table_name;
            } else if (featureDao.tableName) {
                tableInfo.tableName = featureDao.tableName;
            }
            
            // Debug table structure
            logger.info('Table object structure', {
                hasTable: !!featureDao.table,
                hasTableName: !!featureDao.table_name,
                tableKeys: featureDao.table ? Object.keys(featureDao.table) : [],
                featureDaoKeys: Object.keys(featureDao).slice(0, 20)
            });

            // Get columns - check various ways
            if (featureDao.columns) {
                // Check if columns is an array or object
                if (Array.isArray(featureDao.columns)) {
                    tableInfo.columns = featureDao.columns.map((col, idx) => ({
                        name: col.name || col.column_name || `col_${idx}`,
                        type: col.dataType || col.data_type || col.type || 'unknown',
                        isPrimary: col.primaryKey || col.pk || false,
                        notNull: col.notNull || col.nn || false
                    }));
                } else if (typeof featureDao.columns === 'object') {
                    tableInfo.columns = Object.keys(featureDao.columns).map(colName => {
                        const col = featureDao.columns[colName];
                        return {
                            name: colName,
                            type: col.dataType || col.data_type || col.type || 'unknown',
                            isPrimary: col.primaryKey || col.pk || false,
                            notNull: col.notNull || col.nn || false
                        };
                    });
                }
            } else if (featureDao.columnNames) {
                // Just column names available
                tableInfo.columns = featureDao.columnNames.map(name => ({
                    name: name,
                    type: 'unknown',
                    isPrimary: false,
                    notNull: false
                }));
            } else if (featureDao.getColumns && typeof featureDao.getColumns === 'function') {
                const cols = featureDao.getColumns();
                tableInfo.columns = cols.map(col => ({
                    name: col.name || col.column_name,
                    type: col.dataType || col.data_type || col.type || 'unknown',
                    isPrimary: col.primaryKey || col.pk || false,
                    notNull: col.notNull || col.nn || false
                }));
            }

            // Get SRS
            if (typeof featureDao.getSrs === 'function') {
                const srs = featureDao.getSrs();
                tableInfo.srs = {
                    srsId: srs?.srs_id,
                    organization: srs?.organization,
                    organizationCoordsysId: srs?.organization_coordsys_id
                };
            } else if (featureDao.srs) {
                tableInfo.srs = {
                    srsId: featureDao.srs?.srs_id,
                    organization: featureDao.srs?.organization,
                    organizationCoordsysId: featureDao.srs?.organization_coordsys_id
                };
            }

            // Get row count and samples
            const sampleData = await this.extractSampleRows(featureDao, 5);
            tableInfo.rowCount = sampleData.totalCount;
            tableInfo.sampleRows = sampleData.rows;
            
            logger.info('Table structure', { 
                tableName,
                columnCount: tableInfo.columns.length,
                rowCount: tableInfo.rowCount,
                srs: tableInfo.srs
            });

            return tableInfo;
            
        } catch (error) {
            logger.error('Error analyzing table', { tableName, error: error.message });
            tableInfo.error = error.message;
            return tableInfo;
        }
    }

    /**
     * Extracts and logs first few rows with all properties
     * @param {Object} featureDao - Feature DAO instance
     * @param {number} limit - Number of rows to extract
     * @returns {Promise<Object>} Sample rows and total count
     */
    async extractSampleRows(featureDao, limit = 5) {
        const result = {
            rows: [],
            totalCount: 0,
            iteratorType: null,
            geometryColumn: null
        };

        try {
            // Get geometry column name
            if (featureDao.geometryColumn) {
                result.geometryColumn = featureDao.geometryColumn;
            } else if (featureDao.getGeometryColumnName && typeof featureDao.getGeometryColumnName === 'function') {
                result.geometryColumn = featureDao.getGeometryColumnName();
            }
            
            logger.info('Geometry column info', {
                geometryColumn: result.geometryColumn,
                hasGetGeometry: typeof featureDao.getGeometry === 'function'
            });
            
            // Try different methods to get rows
            let rows = null;
            
            // Method 1: queryForAll
            if (typeof featureDao.queryForAll === 'function') {
                rows = featureDao.queryForAll();
                result.iteratorType = 'queryForAll';
                // Count rows if array
                if (Array.isArray(rows)) {
                    result.totalCount = rows.length;
                }
            }
            // Method 2: queryForEach (returns iterator)
            else if (typeof featureDao.queryForEach === 'function') {
                const iterator = featureDao.queryForEach();
                rows = [];
                for (const row of iterator) {
                    rows.push(row);
                    result.totalCount++;
                }
                result.iteratorType = 'queryForEach';
            }
            // Method 3: Direct query
            else if (typeof featureDao.query === 'function') {
                rows = featureDao.query();
                result.iteratorType = 'query';
            }

            if (!rows) {
                logger.warn('No query method found', { 
                    availableMethods: featureDao.daoMethods || Object.getOwnPropertyNames(Object.getPrototypeOf(featureDao))
                        .filter(method => method.includes('query'))
                });
                return result;
            }

            // Extract sample rows
            const rowsToProcess = Array.isArray(rows) ? rows.slice(0, limit) : rows;
            let count = 0;
            
            // If not array but iterable, count total while processing
            if (!Array.isArray(rows) && rows[Symbol.iterator]) {
                for (const row of rows) {
                    if (count < limit) {
                        const rowData = await this.processRow(row, featureDao, count);
                        result.rows.push(rowData);
                    }
                    count++;
                    result.totalCount++;
                }
            } else {
                // Process array or slice
                for (const row of rowsToProcess) {
                    if (count >= limit) break;
                    const rowData = await this.processRow(row, featureDao, count);
                    result.rows.push(rowData);
                    count++;
                }
                // If we haven't counted yet
                if (result.totalCount === 0 && Array.isArray(rows)) {
                    result.totalCount = rows.length;
                }
            }

            return result;
            
        } catch (error) {
            logger.error('Error extracting sample rows', { error: error.message });
            return result;
        }
    }
    
    /**
     * Process a single row
     * @param {Object} row - Row data
     * @param {Object} featureDao - Feature DAO instance
     * @param {number} index - Row index
     * @returns {Promise<Object>} Processed row data
     */
    async processRow(row, featureDao, index) {
        const rowData = {
            index: index,
            properties: {},
            geometry: null,
            rowType: typeof row,
            hasGetValue: typeof row.getValue === 'function',
            hasGetValueWithColumn: typeof row.getValueWithColumn === 'function',
            hasGetRow: typeof row.getRow === 'function',
            hasToGeoJSON: typeof row.toGeoJSON === 'function'
        };

        try {
            // Extract properties based on row type
            if (typeof row.getRow === 'function') {
                // GeoPackageRow object
                const values = row.getRow();
                rowData.properties = values;
            } else if (typeof row.toJSON === 'function') {
                // Has toJSON method
                rowData.properties = row.toJSON();
            } else if (typeof row.toGeoJSON === 'function') {
                // Has toGeoJSON method
                const geoJSON = row.toGeoJSON();
                rowData.properties = geoJSON.properties || {};
                rowData.geometry = geoJSON.geometry;
            } else {
                // Plain object - directly use properties
                rowData.properties = { ...row };
            }
            
            // Try to extract geometry if not already set
            if (!rowData.geometry && featureDao.getGeometry && typeof featureDao.getGeometry === 'function') {
                try {
                    rowData.geometry = featureDao.getGeometry(row);
                } catch (geomError) {
                    logger.debug('Could not extract geometry', { error: geomError.message });
                }
            }

            // Log first row in detail
            if (index === 0) {
                logger.info('First row details', {
                    rowType: rowData.rowType,
                    hasGetValue: rowData.hasGetValue,
                    hasGetRow: rowData.hasGetRow,
                    hasToGeoJSON: rowData.hasToGeoJSON,
                    properties: Object.keys(rowData.properties),
                    sampleValues: Object.entries(rowData.properties)
                        .slice(0, 5)
                        .reduce((acc, [k, v]) => ({ ...acc, [k]: typeof v === 'object' ? `[${typeof v}]` : v }), {})
                });
            }
            
        } catch (error) {
            logger.error('Error processing row', { index, error: error.message });
        }
        
        return rowData;
    }
}

module.exports = { GeoPackageTestExtractor };