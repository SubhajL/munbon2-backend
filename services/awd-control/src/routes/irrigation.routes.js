"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.irrigationRouter = void 0;
const express_1 = require("express");
const scada_gate_control_service_1 = require("../services/scada-gate-control.service");
const logger_1 = require("../utils/logger");
const axios_1 = __importDefault(require("axios"));
const router = (0, express_1.Router)();
router.post('/execute-schedule', async (req, res) => {
    try {
        const { scheduleId, date, waterDemand, duration, sections, autoAdjust } = req.body;
        const executionId = `exec-${new Date().toISOString().split('T')[0]}-${Date.now().toString(36)}`;
        logger_1.logger.info(`Executing irrigation schedule ${scheduleId} for ${waterDemand}m³ over ${duration}s`);
        const flowRateNeeded = waterDemand / (duration / 3600);
        const gatesToOpen = await determineGatesForSections(sections);
        const waterLevels = await getCurrentWaterLevels();
        let adjustedGates = gatesToOpen;
        if (autoAdjust) {
            adjustedGates = await adjustGateOpenings(gatesToOpen, waterLevels, flowRateNeeded);
        }
        const gateResults = [];
        for (const gate of adjustedGates) {
            try {
                const result = await scada_gate_control_service_1.scadaGateControlService.controlGate(gate.gateId, {
                    targetOpening: gate.position,
                    mode: 'auto',
                    reason: `Schedule ${scheduleId}: ${waterDemand}m³ irrigation`,
                    duration
                });
                gateResults.push({
                    gateId: gate.gateId,
                    action: 'opened',
                    position: gate.position,
                    flow: gate.estimatedFlow || calculateFlowForGate(gate.position, waterLevels.upstream)
                });
            }
            catch (error) {
                logger_1.logger.error(`Failed to open gate ${gate.gateId}:`, error);
                gateResults.push({
                    gateId: gate.gateId,
                    action: 'failed',
                    error: error instanceof Error ? error.message : 'Unknown error'
                });
            }
        }
        const totalFlow = gateResults
            .filter(g => g.action === 'opened')
            .reduce((sum, g) => sum + (g.flow || 0), 0);
        startIrrigationMonitoring(executionId, waterDemand, duration);
        const response = {
            executionId,
            status: 'active',
            schedule: {
                start: new Date().toISOString(),
                end: new Date(Date.now() + duration * 1000).toISOString(),
                waterTarget: waterDemand,
                waterDelivered: 0,
                progress: 0
            },
            gates: gateResults,
            monitoring: {
                upstream_level: waterLevels.upstream,
                downstream_level: waterLevels.downstream,
                total_flow: totalFlow,
                efficiency: calculateEfficiency(totalFlow, flowRateNeeded)
            }
        };
        res.json(response);
    }
    catch (error) {
        logger_1.logger.error('Failed to execute irrigation schedule:', error);
        res.status(500).json({
            success: false,
            error: error.message
        });
    }
});
router.get('/status/:executionId', async (req, res) => {
    try {
        const { executionId } = req.params;
        const status = await getIrrigationStatus(executionId);
        if (!status) {
            return res.status(404).json({
                error: 'Execution not found',
                executionId
            });
        }
        res.json(status);
    }
    catch (error) {
        logger_1.logger.error('Failed to get irrigation status:', error);
        res.status(500).json({
            error: error.message
        });
    }
});
router.post('/stop/:executionId', async (req, res) => {
    try {
        const { executionId } = req.params;
        const { reason } = req.body;
        logger_1.logger.info(`Stopping irrigation execution ${executionId}: ${reason}`);
        const status = await getIrrigationStatus(executionId);
        if (!status) {
            return res.status(404).json({
                error: 'Execution not found',
                executionId
            });
        }
        const closeResults = [];
        for (const gate of status.gates) {
            try {
                await scada_gate_control_service_1.scadaGateControlService.controlGate(gate.gateId, {
                    targetOpening: 0,
                    mode: 'manual',
                    reason: `Stop execution: ${reason}`
                });
                closeResults.push({
                    gateId: gate.gateId,
                    status: 'closed'
                });
            }
            catch (error) {
                closeResults.push({
                    gateId: gate.gateId,
                    status: 'failed',
                    error: error instanceof Error ? error.message : 'Unknown error'
                });
            }
        }
        stopIrrigationMonitoring(executionId);
        res.json({
            success: true,
            executionId,
            status: 'stopped',
            reason,
            gatesClosed: closeResults,
            waterDelivered: status.schedule.waterDelivered,
            efficiency: status.monitoring.efficiency
        });
    }
    catch (error) {
        logger_1.logger.error('Failed to stop irrigation:', error);
        res.status(500).json({
            error: error.message
        });
    }
});
async function determineGatesForSections(sections) {
    const sectionGateMapping = {
        'section-1A': ['MG-01', 'SG-01'],
        'section-1B': ['MG-02', 'SG-02'],
        'section-2A': ['MG-03', 'SG-03'],
        'section-2B': ['MG-04', 'SG-04']
    };
    const gates = [];
    for (const section of sections) {
        const gateIds = sectionGateMapping[section] || [];
        for (const gateId of gateIds) {
            gates.push({
                gateId,
                position: 100,
                priority: gateId.startsWith('MG') ? 1 : 2
            });
        }
    }
    return gates;
}
async function getCurrentWaterLevels() {
    try {
        const response = await axios_1.default.get('http://localhost:3003/api/water-level/latest');
        return {
            upstream: response.data.upstream || 4.5,
            downstream: response.data.downstream || 3.2
        };
    }
    catch (error) {
        return {
            upstream: 4.5,
            downstream: 3.2
        };
    }
}
async function adjustGateOpenings(gates, waterLevels, targetFlow) {
    const adjustedGates = [];
    for (const gate of gates) {
        const headDifference = waterLevels.upstream - waterLevels.downstream;
        const baseFlow = calculateFlowForGate(100, waterLevels.upstream);
        const requiredOpening = Math.min(100, (targetFlow / gates.length / baseFlow) * 100);
        adjustedGates.push({
            ...gate,
            position: Math.round(requiredOpening),
            estimatedFlow: calculateFlowForGate(requiredOpening, waterLevels.upstream)
        });
    }
    return adjustedGates;
}
function calculateFlowForGate(opening, upstreamLevel) {
    const C = 0.6;
    const g = 9.81;
    const gateArea = 2.0;
    const effectiveArea = gateArea * (opening / 100);
    const head = upstreamLevel;
    return C * effectiveArea * Math.sqrt(2 * g * head) * 3600;
}
function calculateEfficiency(actualFlow, targetFlow) {
    if (targetFlow === 0)
        return 0;
    return Math.min(100, (actualFlow / targetFlow) * 100);
}
const irrigationMonitors = new Map();
function startIrrigationMonitoring(executionId, targetVolume, duration) {
    const monitor = {
        executionId,
        targetVolume,
        duration,
        startTime: Date.now(),
        delivered: 0,
        flowReadings: []
    };
    const interval = setInterval(() => {
        const elapsed = (Date.now() - monitor.startTime) / 1000;
        if (elapsed >= duration) {
            clearInterval(interval);
            monitor.status = 'completed';
        }
        else {
            monitor.delivered = (elapsed / duration) * targetVolume;
        }
    }, 5000);
    monitor.interval = interval;
    irrigationMonitors.set(executionId, monitor);
}
function stopIrrigationMonitoring(executionId) {
    const monitor = irrigationMonitors.get(executionId);
    if (monitor) {
        clearInterval(monitor.interval);
        monitor.status = 'stopped';
    }
}
async function getIrrigationStatus(executionId) {
    const monitor = irrigationMonitors.get(executionId);
    if (!monitor)
        return null;
    const elapsed = (Date.now() - monitor.startTime) / 1000;
    const progress = Math.min(100, (elapsed / monitor.duration) * 100);
    return {
        executionId,
        status: monitor.status || 'active',
        schedule: {
            waterTarget: monitor.targetVolume,
            waterDelivered: monitor.delivered,
            progress
        },
        gates: [],
        monitoring: {
            upstream_level: 4.5,
            downstream_level: 3.2,
            total_flow: 210.7,
            efficiency: 92.5
        }
    };
}
exports.default = router;
exports.irrigationRouter = router;
//# sourceMappingURL=irrigation.routes.js.map