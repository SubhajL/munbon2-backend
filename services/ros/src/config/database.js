"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.pool = void 0;
exports.testConnection = testConnection;
exports.closeDatabase = closeDatabase;
const pg_1 = require("pg");
const index_1 = require("./index");
const logger_1 = require("@utils/logger");
const poolConfig = {
    host: index_1.config.database.host,
    port: index_1.config.database.port,
    database: index_1.config.database.name,
    user: index_1.config.database.user,
    password: index_1.config.database.password,
    max: 20,
    idleTimeoutMillis: 30000,
    connectionTimeoutMillis: 2000,
};
exports.pool = new pg_1.Pool(poolConfig);
exports.pool.on('error', (err) => {
    logger_1.logger.error('Unexpected error on idle database client', err);
});
async function testConnection() {
    try {
        const client = await exports.pool.connect();
        await client.query('SELECT 1');
        client.release();
        logger_1.logger.info('Database connection successful');
        return true;
    }
    catch (error) {
        logger_1.logger.error('Database connection failed:', error);
        return false;
    }
}
async function closeDatabase() {
    await exports.pool.end();
    logger_1.logger.info('Database pool closed');
}
//# sourceMappingURL=database.js.map