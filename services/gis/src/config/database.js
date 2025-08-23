"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.AppDataSource = void 0;
exports.connectDatabase = connectDatabase;
const typeorm_1 = require("typeorm");
const index_1 = require("./index");
const zone_entity_1 = require("../models/zone.entity");
const parcel_entity_1 = require("../models/parcel.entity");
const canal_entity_1 = require("../models/canal.entity");
const gate_entity_1 = require("../models/gate.entity");
const pump_entity_1 = require("../models/pump.entity");
const water_source_entity_1 = require("../models/water-source.entity");
const irrigation_block_entity_1 = require("../models/irrigation-block.entity");
const spatial_index_entity_1 = require("../models/spatial-index.entity");
const shape_file_upload_entity_1 = require("../models/shape-file-upload.entity");
const parcel_simple_entity_1 = require("../models/parcel-simple.entity");
exports.AppDataSource = new typeorm_1.DataSource({
    type: 'postgres',
    url: index_1.config.database.url,
    ssl: index_1.config.database.ssl ? { rejectUnauthorized: false } : false,
    synchronize: false,
    logging: index_1.config.database.enableQueryLogging,
    entities: [
        zone_entity_1.Zone,
        parcel_entity_1.Parcel,
        canal_entity_1.Canal,
        gate_entity_1.Gate,
        pump_entity_1.Pump,
        water_source_entity_1.WaterSource,
        irrigation_block_entity_1.IrrigationBlock,
        spatial_index_entity_1.SpatialIndex,
        shape_file_upload_entity_1.ShapeFileUpload,
        parcel_simple_entity_1.ParcelSimple,
    ],
    migrations: ['src/migrations/*.ts'],
    subscribers: ['src/subscribers/*.ts'],
    schema: index_1.config.database.gisSchema,
    poolSize: index_1.config.database.poolSize,
    extra: {
        max: index_1.config.database.poolSize,
        idleTimeoutMillis: index_1.config.database.poolIdleTimeout,
        connectionTimeoutMillis: 2000,
    },
});
async function connectDatabase() {
    try {
        console.log('Connecting to database with URL:', index_1.config.database.url?.replace(/:[^:]*@/, ':****@'));
        console.log('Database config:', {
            ssl: index_1.config.database.ssl,
            schema: index_1.config.database.gisSchema,
            poolSize: index_1.config.database.poolSize
        });
        await exports.AppDataSource.initialize();
        console.log('Database connection initialized');
        await exports.AppDataSource.query(`CREATE SCHEMA IF NOT EXISTS ${index_1.config.database.gisSchema}`);
        console.log('Schema created/verified');
        try {
            await exports.AppDataSource.query('CREATE EXTENSION IF NOT EXISTS postgis');
            await exports.AppDataSource.query('CREATE EXTENSION IF NOT EXISTS postgis_topology');
            console.log('PostGIS extensions enabled');
        }
        catch (error) {
            console.warn('PostGIS not available, continuing without spatial support');
        }
        await exports.AppDataSource.query(`SET search_path TO ${index_1.config.database.gisSchema}, public`);
        if (index_1.config.env === 'development') {
            console.log('Synchronizing database schema...');
            console.log('Database schema synchronization skipped');
        }
        if (index_1.config.env === 'production') {
            await exports.AppDataSource.runMigrations();
        }
        try {
            await createSpatialIndexes();
        }
        catch (error) {
            console.warn('Could not create spatial indexes:', error);
        }
    }
    catch (error) {
        console.error('Database connection error:', error);
        throw new Error(`Database connection failed: ${error}`);
    }
}
async function createSpatialIndexes() {
    const queries = [
        `CREATE INDEX IF NOT EXISTS idx_zones_boundary ON ${index_1.config.database.gisSchema}.irrigation_zones USING GIST (boundary)`,
        `CREATE INDEX IF NOT EXISTS idx_plots_boundary ON ${index_1.config.database.gisSchema}.agricultural_plots USING GIST (boundary)`,
        `CREATE INDEX IF NOT EXISTS idx_canals_geometry ON ${index_1.config.database.gisSchema}.canal_network USING GIST (geometry)`,
        `CREATE INDEX IF NOT EXISTS idx_control_structures_location ON ${index_1.config.database.gisSchema}.control_structures USING GIST (location)`,
    ];
    for (const query of queries) {
        try {
            await exports.AppDataSource.query(query);
        }
        catch (error) {
            console.error(`Failed to create spatial index: ${error}`);
        }
    }
}
//# sourceMappingURL=database.js.map