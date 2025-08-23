"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.scadaApiService = exports.ScadaApiService = void 0;
const logger_1 = require("../utils/logger");
class ScadaApiService {
    baseUrl;
    authToken;
    constructor() {
        this.baseUrl = process.env.SCADA_SERVICE_URL || 'http://scada-integration:3015';
        this.authToken = process.env.SERVICE_AUTH_TOKEN;
    }
    async getHealthStatus() {
        try {
            const response = await fetch(`${this.baseUrl}/api/v1/scada/health`, {
                headers: this.getHeaders()
            });
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            return await response.json();
        }
        catch (error) {
            logger_1.logger.error({ error }, 'Failed to get SCADA health status');
            throw error;
        }
    }
    async getDetailedHealthStatus() {
        try {
            const response = await fetch(`${this.baseUrl}/api/v1/scada/health/detailed`, {
                headers: this.getHeaders()
            });
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            return await response.json();
        }
        catch (error) {
            logger_1.logger.error({ error }, 'Failed to get detailed SCADA health status');
            throw error;
        }
    }
    async sendGateCommand(command) {
        try {
            const response = await fetch(`${this.baseUrl}/api/v1/scada/command/send`, {
                method: 'POST',
                headers: {
                    ...this.getHeaders(),
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(command)
            });
            const result = await response.json();
            if (!response.ok) {
                logger_1.logger.error({ status: response.status, result }, 'Gate command failed');
                return {
                    success: false,
                    message: result.message || 'Failed to send gate command',
                    error: result.error
                };
            }
            return result;
        }
        catch (error) {
            logger_1.logger.error({ error, command }, 'Failed to send gate command');
            return {
                success: false,
                message: 'Failed to connect to SCADA service',
                error: error
            };
        }
    }
    async getCommandStatus(commandId) {
        try {
            const response = await fetch(`${this.baseUrl}/api/v1/scada/command/${commandId}/status`, {
                headers: this.getHeaders()
            });
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            return await response.json();
        }
        catch (error) {
            logger_1.logger.error({ error, commandId }, 'Failed to get command status');
            throw error;
        }
    }
    async closeGate(gateName, fieldId) {
        try {
            const response = await fetch(`${this.baseUrl}/api/v1/scada/gates/${gateName}/close`, {
                method: 'POST',
                headers: {
                    ...this.getHeaders(),
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ fieldId })
            });
            const result = await response.json();
            if (!response.ok) {
                return {
                    success: false,
                    message: result.message || 'Failed to close gate',
                    error: result.error
                };
            }
            return result;
        }
        catch (error) {
            logger_1.logger.error({ error, gateName }, 'Failed to close gate');
            return {
                success: false,
                message: 'Failed to connect to SCADA service',
                error: error
            };
        }
    }
    async openGate(gateName, level, fieldId, targetFlowRate) {
        try {
            const response = await fetch(`${this.baseUrl}/api/v1/scada/gates/${gateName}/open`, {
                method: 'POST',
                headers: {
                    ...this.getHeaders(),
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ level, fieldId, targetFlowRate })
            });
            const result = await response.json();
            if (!response.ok) {
                return {
                    success: false,
                    message: result.message || 'Failed to open gate',
                    error: result.error
                };
            }
            return result;
        }
        catch (error) {
            logger_1.logger.error({ error, gateName, level }, 'Failed to open gate');
            return {
                success: false,
                message: 'Failed to connect to SCADA service',
                error: error
            };
        }
    }
    async getControlSites() {
        try {
            const response = await fetch(`${this.baseUrl}/api/v1/scada/sites`, {
                headers: this.getHeaders()
            });
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            const data = await response.json();
            return data.sites || [];
        }
        catch (error) {
            logger_1.logger.error({ error }, 'Failed to get control sites');
            throw error;
        }
    }
    async isScadaAvailable() {
        try {
            const health = await this.getHealthStatus();
            return health.status === 'healthy' || health.status === 'degraded';
        }
        catch (error) {
            logger_1.logger.error({ error }, 'Failed to check SCADA availability');
            return false;
        }
    }
    getHeaders() {
        const headers = {};
        if (this.authToken) {
            headers['Authorization'] = `Bearer ${this.authToken}`;
        }
        return headers;
    }
}
exports.ScadaApiService = ScadaApiService;
exports.scadaApiService = new ScadaApiService();
//# sourceMappingURL=scada-api.service.js.map