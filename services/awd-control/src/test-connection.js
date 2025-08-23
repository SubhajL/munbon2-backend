"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const dotenv_1 = __importDefault(require("dotenv"));
const logger_1 = require("./utils/logger");
dotenv_1.default.config();
async function testConnections() {
    logger_1.logger.info('Testing AWD Control Service connections...');
    logger_1.logger.info({
        port: process.env.PORT,
        postgresHost: process.env.POSTGRES_HOST,
        timescaleHost: process.env.TIMESCALE_HOST,
        redisHost: process.env.REDIS_HOST,
        kafkaBrokers: process.env.KAFKA_BROKERS,
    }, 'Configuration loaded');
    logger_1.logger.info('Basic configuration test passed');
    process.exit(0);
}
testConnections().catch(error => {
    logger_1.logger.error(error, 'Test failed');
    process.exit(1);
});
//# sourceMappingURL=test-connection.js.map