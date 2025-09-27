const fs = require('fs');
const path = require('path');
const AdmZip = require('adm-zip');
const { GeoPackageAPI } = require('@ngageoint/geopackage');
const { logger } = require('../utils/logger');
const { AppDataSource } = require('../config/database');

class RidplanProcessor {
    constructor() {
        this.tempDir = '/tmp/gis-shape-files';
        if (!fs.existsSync(this.tempDir)) {
            fs.mkdirSync(this.tempDir, { recursive: true });
        }
    }

    async processRidplanData(options) {
        const uploadDir = path.join(this.tempDir, options.uploadId);
        try {
            fs.mkdirSync(uploadDir, { recursive: true });
            const zipPath = path.join(uploadDir, options.fileName);
            fs.writeFileSync(zipPath, options.buffer);
            
            const zip = new AdmZip(zipPath);
            zip.extractAllTo(uploadDir, true);
            logger.info('Extracted ridplan archive', { uploadDir });
            
            // Only process data_ridplan folder
            const sensorData = await this.parseRidplanGeoPackage(uploadDir);
            
            // Write to sensor_data table
            if (sensorData.length > 0) {
                await this.saveSensorData(sensorData);
                logger.info('Saved ridplan sensor data', { count: sensorData.length });
            }
            
            return { sensorDataCount: sensorData.length };
        } finally {
            this.cleanupDirectory(uploadDir);
        }
    }

    async parseRidplanGeoPackage(directory) {
        const sensorData = [];
        
        // Find GeoPackage files in data_ridplan directory only
        const ridplanDir = path.join(directory, 'data_ridplan');
        if (!fs.existsSync(ridplanDir)) {
            logger.warn('No data_ridplan directory found');
            return sensorData;
        }
        
        const gpkgFiles = this.findGeoPackageFiles(ridplanDir);
        logger.info('Found ridplan GeoPackage files', { 
            count: gpkgFiles.length,
            files: gpkgFiles.map(f => path.relative(directory, f))
        });
        
        for (const gpkgPath of gpkgFiles) {
            let geoPackage = null;
            try {
                logger.info('Opening ridplan GeoPackage', { file: path.basename(gpkgPath) });
                geoPackage = await GeoPackageAPI.open(gpkgPath);
                
                const tables = geoPackage.getFeatureTables();
                logger.info('Found tables in ridplan GeoPackage', { tables });
                
                for (const tableName of tables) {
                    const featureDao = geoPackage.getFeatureDao(tableName);
                    const features = featureDao.queryForAll();
                    
                    logger.info('Processing ridplan table', { 
                        tableName, 
                        featureCount: features.length,
                        columns: featureDao.columnNames
                    });
                    
                    for (const row of features) {
                        const feature = featureDao.getRow(row);
                        const props = feature.values || {};
                        
                        // Extract sensor data from properties
                        const data = this.extractSensorData(props, tableName);
                        if (data) {
                            sensorData.push(data);
                        }
                    }
                }
            } catch (error) {
                logger.error('Error processing ridplan GeoPackage', { 
                    error: error.message,
                    file: gpkgPath 
                });
            } finally {
                if (geoPackage) {
                    geoPackage.close();
                }
            }
        }
        
        return sensorData;
    }

    findGeoPackageFiles(dir) {
        const gpkgFiles = [];
        
        const searchDir = (currentDir) => {
            const items = fs.readdirSync(currentDir);
            for (const item of items) {
                const fullPath = path.join(currentDir, item);
                const stats = fs.statSync(fullPath);
                
                if (stats.isDirectory()) {
                    searchDir(fullPath);
                } else if (item.toLowerCase().endsWith('.gpkg')) {
                    gpkgFiles.push(fullPath);
                }
            }
        };
        
        searchDir(dir);
        return gpkgFiles;
    }

    extractSensorData(props, tableName) {
        // Log all properties to understand the structure
        logger.debug('Ridplan properties', { 
            tableName,
            sampleProps: Object.keys(props).slice(0, 20),
            allProps: props
        });
        
        // Try different field mappings based on what might be in the data
        const data = {
            data_datetime: this.parseDateTime(
                props.data_date_ || props.data_datetime || props.date_time || 
                props.DATA_DATE || props.timestamp || new Date()
            ),
            battery: this.parseFloat(props.battery || props.BATTERY || props.batt),
            windspeed: this.parseFloat(props.windspeed || props.WINDSPEED || props.wind_speed || props.wpet),
            windmax: this.parseFloat(props.windmax || props.WINDMAX || props.wind_max),
            raingauge: this.parseFloat(props.raingauge || props.RAINGAUGE || props.rain || props.precipitation),
            temp: this.parseFloat(props.temp || props.TEMP || props.temperature || props.air_temp),
            winddirect: this.parseFloat(props.winddirect || props.WINDDIRECT || props.wind_dir || props.wind_direction),
            solar: this.parseFloat(props.solar || props.SOLAR || props.solar_radiation || props.radiation),
            sensor_id: props.sensor_id || props.SENSOR_ID || props.station_id || tableName,
            plot_code: props.PARCEL_SEQ || props.parcel_seq || props.plot_code || props.PLOT_CODE
        };
        
        // Also store original properties as metadata
        data.metadata = {
            originalTable: tableName,
            parcelAreaRai: props.parcel_are,
            startInt: props.start_int,
            wpet: props.wpet,
            age: props.age,
            wprod: props.wprod,
            plantId: props.plant_id,
            yieldAtMcKgpr: props.yield_at_m,
            seasonIrrM3PerRai: props.season_irr,
            autoNote: props.auto_note,
            stageAge: props.stage_age,
            lat: props.lat,
            lon: props.lon,
            subMember: props.sub_member
        };
        
        return data;
    }

    parseDateTime(value) {
        if (!value) return new Date();
        if (value instanceof Date) return value;
        
        try {
            const date = new Date(value);
            return isNaN(date.getTime()) ? new Date() : date;
        } catch (e) {
            return new Date();
        }
    }

    parseFloat(value) {
        if (value === null || value === undefined) return null;
        const parsed = parseFloat(value);
        return isNaN(parsed) ? null : parsed;
    }

    async saveSensorData(sensorDataArray) {
        const queryRunner = AppDataSource.createQueryRunner();
        await queryRunner.connect();
        await queryRunner.startTransaction();

        try {
            for (const data of sensorDataArray) {
                // First save to sensor_data table
                await queryRunner.query(
                    `INSERT INTO gis.sensor_data 
                    (data_datetime, battery, windspeed, windmax, raingauge, temp, winddirect, solar, sensor_id, plot_code)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)`,
                    [
                        data.data_datetime,
                        data.battery,
                        data.windspeed,
                        data.windmax,
                        data.raingauge,
                        data.temp,
                        data.winddirect,
                        data.solar,
                        data.sensor_id,
                        data.plot_code
                    ]
                );

                // If we have plot data, also update agricultural_plots
                if (data.plot_code && data.metadata) {
                    await queryRunner.query(
                        `INSERT INTO gis.agricultural_plots 
                        (plot_code, area_hectares, properties, boundary)
                        VALUES ($1, $2, $3, ST_GeomFromText('POINT(0 0)', 4326))
                        ON CONFLICT (plot_code) 
                        DO UPDATE SET 
                            properties = COALESCE(agricultural_plots.properties, '{}'::jsonb) || $3,
                            updated_at = NOW()`,
                        [
                            data.plot_code,
                            data.metadata.parcelAreaRai ? data.metadata.parcelAreaRai / 6.25 : null,
                            JSON.stringify(data.metadata)
                        ]
                    );
                }
            }

            await queryRunner.commitTransaction();
            logger.info('Sensor data saved successfully', { count: sensorDataArray.length });
        } catch (error) {
            await queryRunner.rollbackTransaction();
            logger.error('Error saving sensor data', { error: error.message });
            throw error;
        } finally {
            await queryRunner.release();
        }
    }

    cleanupDirectory(directory) {
        try {
            if (fs.existsSync(directory)) {
                fs.rmSync(directory, { recursive: true, force: true });
            }
        } catch (error) {
            logger.warn('Failed to cleanup temporary directory', { error, directory });
        }
    }
}

module.exports = { RidplanProcessor };