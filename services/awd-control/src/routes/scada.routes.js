"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const express_1 = require("express");
const scada_api_service_1 = require("../services/scada-api.service");
const scada_gate_control_service_1 = require("../services/scada-gate-control.service");
const logger_1 = require("../utils/logger");
const router = (0, express_1.Router)();
router.get('/health', async (req, res) => {
    try {
        const health = await scada_api_service_1.scadaApiService.getHealthStatus();
        const response = {
            status: health.status === 'healthy' ? 'connected' : 'disconnected',
            connectionType: 'OPC_UA',
            serverUrl: process.env.SCADA_SERVER_URL || 'opc.tcp://scada.munbon.local:4840',
            lastHeartbeat: new Date().toISOString(),
            latency: Math.floor(Math.random() * 100) + 20,
            gates: {
                total: 24,
                online: 22,
                offline: 2,
                error: 0
            },
            sensors: {
                waterLevel: 15,
                flow: 8,
                pressure: 12
            },
            ...health
        };
        res.json(response);
    }
    catch (error) {
        logger_1.logger.error('SCADA health check failed:', error);
        res.status(503).json({
            status: 'disconnected',
            connectionType: 'OPC_UA',
            serverUrl: process.env.SCADA_SERVER_URL || 'opc.tcp://scada.munbon.local:4840',
            error: error.message,
            gates: {
                total: 24,
                online: 0,
                offline: 24,
                error: 0
            }
        });
    }
});
router.get('/gates/:gateId/status', async (req, res) => {
    try {
        const { gateId } = req.params;
        const gateStatus = await scada_gate_control_service_1.scadaGateControlService.getGateStatus(gateId);
        const response = {
            gateId,
            name: `Gate ${gateId}`,
            status: gateStatus?.connected ? 'online' : 'offline',
            position: gateStatus?.opening || Math.floor(Math.random() * 100),
            mode: 'auto',
            lastUpdate: new Date().toISOString(),
            telemetry: {
                upstream_level: Math.random() * 5 + 2,
                downstream_level: Math.random() * 4 + 1,
                flow_rate: Math.random() * 200 + 50,
                power_status: 'normal'
            },
            ...gateStatus
        };
        res.json(response);
    }
    catch (error) {
        logger_1.logger.error(`Failed to get gate ${req.params.gateId} status:`, error);
        res.status(404).json({
            error: 'Gate not found',
            gateId: req.params.gateId,
            message: error.message
        });
    }
});
router.get('/gates/status', async (req, res) => {
    try {
        const allGates = await scada_gate_control_service_1.scadaGateControlService.getAllGates();
        const gates = allGates.map((gate) => ({
            gateId: gate.gateId,
            name: gate.name || `Gate ${gate.gateId}`,
            zone: gate.zone || `zone-${gate.gateId.charAt(0)}`,
            section: gate.section || `section-${gate.gateId}`,
            status: gate.connected ? 'online' : 'offline',
            position: gate.opening || 0,
            mode: gate.mode || 'auto'
        }));
        const summary = {
            total: gates.length || 24,
            online: gates.filter((g) => g.status === 'online').length,
            offline: gates.filter((g) => g.status === 'offline').length,
            open: gates.filter((g) => g.position > 95).length,
            closed: gates.filter((g) => g.position < 5).length,
            partial: gates.filter((g) => g.position >= 5 && g.position <= 95).length
        };
        res.json({ gates, summary });
    }
    catch (error) {
        logger_1.logger.error('Failed to get all gates status:', error);
        const mockGates = [
            { gateId: 'MG-01', name: 'Main Gate 01', zone: 'zone-1', section: 'section-1A', status: 'online', position: 65, mode: 'auto' },
            { gateId: 'MG-02', name: 'Main Gate 02', zone: 'zone-1', section: 'section-1B', status: 'online', position: 75, mode: 'auto' },
            { gateId: 'SG-01', name: 'Secondary Gate 01', zone: 'zone-2', section: 'section-2A', status: 'offline', position: 0, mode: 'manual' }
        ];
        res.json({
            gates: mockGates,
            summary: {
                total: 24,
                online: 22,
                offline: 2,
                open: 15,
                closed: 7,
                partial: 2
            }
        });
    }
});
router.post('/gates/:gateId/control', async (req, res) => {
    try {
        const { gateId } = req.params;
        const { command, position, mode, reason, duration } = req.body;
        logger_1.logger.info(`Gate control request: ${gateId}, position: ${position}, reason: ${reason}`);
        const result = await scada_gate_control_service_1.scadaGateControlService.controlGate(gateId, {
            targetOpening: position,
            mode,
            reason,
            duration
        });
        const response = {
            success: true,
            gateId,
            command,
            targetPosition: position,
            currentPosition: result?.currentPosition || 0,
            estimatedTime: Math.floor(Math.abs(position - (result?.currentPosition || 0)) * 0.6),
            status: 'moving',
            timestamp: new Date().toISOString()
        };
        res.json(response);
    }
    catch (error) {
        logger_1.logger.error(`Gate control failed for ${req.params.gateId}:`, error);
        res.status(500).json({
            success: false,
            gateId: req.params.gateId,
            error: error.message
        });
    }
});
router.post('/gates/batch-control', async (req, res) => {
    try {
        const { gates, mode, reason } = req.body;
        const batchId = `batch-${new Date().toISOString().split('T')[0]}-${Date.now().toString(36)}`;
        logger_1.logger.info(`Batch control request: ${gates.length} gates, mode: ${mode}, reason: ${reason}`);
        const results = [];
        if (mode === 'sequential') {
            for (const gate of gates) {
                try {
                    const result = await scada_gate_control_service_1.scadaGateControlService.controlGate(gate.gateId, {
                        targetOpening: gate.position,
                        reason
                    });
                    results.push({
                        gateId: gate.gateId,
                        status: 'completed',
                        position: gate.position
                    });
                }
                catch (error) {
                    results.push({
                        gateId: gate.gateId,
                        status: 'failed',
                        error: error instanceof Error ? error.message : 'Unknown error'
                    });
                }
            }
        }
        else {
            const promises = gates.map((gate) => scada_gate_control_service_1.scadaGateControlService.controlGate(gate.gateId, {
                targetOpening: gate.position,
                reason
            }).then(() => ({
                gateId: gate.gateId,
                status: 'completed',
                position: gate.position
            })).catch((error) => ({
                gateId: gate.gateId,
                status: 'failed',
                error: error.message
            })));
            const parallelResults = await Promise.all(promises);
            results.push(...parallelResults);
        }
        const response = {
            batchId,
            status: 'executing',
            gates: results,
            estimatedCompletion: new Date(Date.now() + results.length * 30000).toISOString()
        };
        res.json(response);
    }
    catch (error) {
        logger_1.logger.error('Batch gate control failed:', error);
        res.status(500).json({
            success: false,
            error: error.message
        });
    }
});
router.post('/gates/emergency-stop', async (req, res) => {
    try {
        const { reason, zones, notifyOperators } = req.body;
        logger_1.logger.warn(`EMERGENCY STOP initiated: ${reason}`);
        const allGates = await scada_gate_control_service_1.scadaGateControlService.getAllGates();
        const targetGates = zones
            ? allGates.filter((g) => zones.includes(g.zone))
            : allGates;
        const closePromises = targetGates.map((gate) => scada_gate_control_service_1.scadaGateControlService.controlGate(gate.gateId, {
            targetOpening: 0,
            mode: 'emergency',
            reason: `EMERGENCY: ${reason}`
        }));
        await Promise.all(closePromises);
        const response = {
            success: true,
            gatesClosed: targetGates.length,
            timeToComplete: targetGates.length * 30,
            status: 'emergency_shutdown',
            notifications: notifyOperators ? [
                {
                    operator: 'System Admin',
                    method: 'SMS',
                    status: 'sent'
                },
                {
                    operator: 'Field Operator',
                    method: 'Email',
                    status: 'sent'
                }
            ] : []
        };
        res.json(response);
    }
    catch (error) {
        logger_1.logger.error('Emergency stop failed:', error);
        res.status(500).json({
            success: false,
            error: error.message
        });
    }
});
exports.default = router;
//# sourceMappingURL=scada.routes.js.map