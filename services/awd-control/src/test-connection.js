"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const dotenv_1 = __importDefault(require("dotenv"));
const logger_1 = require("./utils/logger");
const database_1 = require("./config/database");
const pg_1 = require("pg");
dotenv_1.default.config();
const withPool = async (config, fn) => {
    const pool = new pg_1.Pool(config);
    try {
        return await fn(pool);
    }
    finally {
        await pool.end();
    }
};
const verifyDatabaseConnections = async () => {
    logger_1.logger.info('Verifying database connectivity for AWD Control Service...');
    const postgresConfig = (0, database_1.buildPostgresConfig)();
    const timescaleConfig = (0, database_1.buildTimescaleConfig)();
    await withPool(postgresConfig, async pool => {
        await pool.query('SELECT 1');
        logger_1.logger.info('PostgreSQL connectivity check passed');
    });
    await withPool(timescaleConfig, async pool => {
        await pool.query('SELECT 1');
        logger_1.logger.info('TimescaleDB connectivity check passed');
    });
    logger_1.logger.info('All database connectivity checks succeeded');
};
exports.verifyDatabaseConnections = verifyDatabaseConnections;
if (require.main === module) {
    verifyDatabaseConnections()
        .then(() => process.exit(0))
        .catch(error => {
        logger_1.logger.error(error, 'Database connection verification failed');
        process.exit(1);
    });
}
//# sourceMappingURL=test-connection.js.map
