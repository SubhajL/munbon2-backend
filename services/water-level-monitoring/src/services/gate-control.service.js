"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.GateControlService = void 0;
const axios_1 = __importDefault(require("axios"));
const config_1 = require("../config");
const logger_1 = require("../utils/logger");
class GateControlService {
    constructor(timescaleService) {
        this.timescaleService = timescaleService;
    }
    async generateRecommendation(gateId, sensorId, currentReading) {
        if (!config_1.config.gateControl.enabled) {
            return null;
        }
        const currentLevel = currentReading.levelCm;
        const targetLevel = (config_1.config.gateControl.minLevel + config_1.config.gateControl.maxLevel) / 2;
        // Get rate of change
        const rateOfChange = await this.timescaleService.getRateOfChange(sensorId, 30);
        // Determine action
        let action;
        let percentage;
        let reason;
        let confidence;
        if (currentLevel < config_1.config.gateControl.minLevel) {
            // Water too low - close gate to retain water
            action = 'close';
            const deficit = config_1.config.gateControl.minLevel - currentLevel;
            percentage = Math.min(100, (deficit / config_1.config.gateControl.minLevel) * 100);
            reason = `Water level ${currentLevel}cm is below minimum ${config_1.config.gateControl.minLevel}cm`;
            confidence = 0.9;
        }
        else if (currentLevel > config_1.config.gateControl.maxLevel) {
            // Water too high - open gate to release water
            action = 'open';
            const excess = currentLevel - config_1.config.gateControl.maxLevel;
            percentage = Math.min(100, (excess / config_1.config.gateControl.maxLevel) * 100);
            reason = `Water level ${currentLevel}cm exceeds maximum ${config_1.config.gateControl.maxLevel}cm`;
            confidence = 0.9;
        }
        else {
            // Water in acceptable range - check trend
            if (rateOfChange > 2) {
                // Rising rapidly
                action = 'open';
                percentage = Math.min(50, rateOfChange * 10);
                reason = `Water rising rapidly at ${rateOfChange.toFixed(2)}cm/hour`;
                confidence = 0.7;
            }
            else if (rateOfChange < -2) {
                // Falling rapidly
                action = 'close';
                percentage = Math.min(50, Math.abs(rateOfChange) * 10);
                reason = `Water falling rapidly at ${Math.abs(rateOfChange).toFixed(2)}cm/hour`;
                confidence = 0.7;
            }
            else {
                // Stable
                action = 'maintain';
                percentage = 0;
                reason = 'Water level stable within acceptable range';
                confidence = 0.95;
            }
        }
        // Estimate time to target
        let estimatedTimeToTarget;
        if (action !== 'maintain' && Math.abs(rateOfChange) > 0.1) {
            const levelDifference = Math.abs(targetLevel - currentLevel);
            estimatedTimeToTarget = (levelDifference / Math.abs(rateOfChange)) * 60; // minutes
        }
        const recommendation = {
            gateId,
            sensorId,
            currentLevel,
            targetLevel,
            recommendedAction: action,
            recommendedPercentage: Math.round(percentage),
            reason,
            confidence,
            estimatedTimeToTarget,
        };
        logger_1.logger.info({ recommendation }, 'Generated gate control recommendation');
        // Send to SCADA service if configured
        if (config_1.config.services.scadaUrl && action !== 'maintain') {
            this.sendToScada(recommendation).catch(err => {
                logger_1.logger.error({ err, recommendation }, 'Failed to send recommendation to SCADA');
            });
        }
        return recommendation;
    }
    async sendToScada(recommendation) {
        try {
            await axios_1.default.post(`${config_1.config.services.scadaUrl}/api/v1/gate-control/recommendations`, {
                source: 'water-level-monitoring',
                recommendation,
                timestamp: new Date(),
            });
        }
        catch (error) {
            throw new Error(`Failed to send to SCADA service: ${error}`);
        }
    }
    async getGateStatus(gateId) {
        if (!config_1.config.services.scadaUrl) {
            throw new Error('SCADA service URL not configured');
        }
        try {
            const response = await axios_1.default.get(`${config_1.config.services.scadaUrl}/api/v1/gates/${gateId}/status`);
            return response.data;
        }
        catch (error) {
            logger_1.logger.error({ error, gateId }, 'Failed to get gate status');
            throw error;
        }
    }
}
exports.GateControlService = GateControlService;
//# sourceMappingURL=gate-control.service.js.map