"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.canalController = void 0;
const canal_service_1 = require("../services/canal.service");
const api_error_1 = require("../utils/api-error");
class CanalController {
    async getAllCanals(req, res, next) {
        try {
            const { page = 1, limit = 100, includeGeometry = false, type, status, level } = req.query;
            const canals = await canal_service_1.canalService.getAllCanals({
                page: Number(page),
                limit: Number(limit),
                includeGeometry: includeGeometry === 'true',
                filters: {
                    type: type,
                    status: status,
                    level: level ? Number(level) : undefined,
                },
            });
            res.json({
                success: true,
                data: canals,
            });
        }
        catch (error) {
            next(error);
        }
    }
    async getCanalById(req, res, next) {
        try {
            const { id } = req.params;
            const canal = await canal_service_1.canalService.getCanalById(id);
            if (!canal) {
                throw new api_error_1.ApiError(404, 'Canal not found');
            }
            res.json({
                success: true,
                data: canal,
            });
        }
        catch (error) {
            next(error);
        }
    }
    async queryCanals(req, res, next) {
        try {
            const canals = await canal_service_1.canalService.queryCanals(req.body);
            res.json({
                success: true,
                data: canals,
                count: canals.length,
            });
        }
        catch (error) {
            next(error);
        }
    }
    async getFlowHistory(req, res, next) {
        try {
            const { id } = req.params;
            const { startDate, endDate, interval = '1h' } = req.query;
            const history = await canal_service_1.canalService.getFlowHistory(id, {
                startDate: startDate,
                endDate: endDate,
                interval: interval,
            });
            res.json({
                success: true,
                data: history,
            });
        }
        catch (error) {
            next(error);
        }
    }
    async getConnectedGates(req, res, next) {
        try {
            const { id } = req.params;
            const gates = await canal_service_1.canalService.getConnectedGates(id);
            res.json({
                success: true,
                data: gates,
                count: gates.length,
            });
        }
        catch (error) {
            next(error);
        }
    }
    async getNetworkTopology(req, res, next) {
        try {
            const { startNodeId, depth = 3 } = req.query;
            const topology = await canal_service_1.canalService.getNetworkTopology({
                startNodeId: startNodeId,
                depth: Number(depth),
            });
            res.json({
                success: true,
                data: topology,
            });
        }
        catch (error) {
            next(error);
        }
    }
    async updateCanalStatus(req, res, next) {
        try {
            const { id } = req.params;
            const { status, reason } = req.body;
            const canal = await canal_service_1.canalService.updateCanalStatus(id, {
                status,
                reason,
                updatedBy: req.user?.id,
            });
            res.json({
                success: true,
                data: canal,
                message: 'Canal status updated successfully',
            });
        }
        catch (error) {
            next(error);
        }
    }
    async updateFlowRate(req, res, next) {
        try {
            const { id } = req.params;
            const { flowRate, measuredAt, sensorId } = req.body;
            const result = await canal_service_1.canalService.updateFlowRate(id, {
                flowRate,
                measuredAt,
                sensorId,
                recordedBy: req.user?.id,
            });
            res.json({
                success: true,
                data: result,
                message: 'Flow rate recorded successfully',
            });
        }
        catch (error) {
            next(error);
        }
    }
    async getMaintenanceHistory(req, res, next) {
        try {
            const { id } = req.params;
            const { page = 1, limit = 20 } = req.query;
            const history = await canal_service_1.canalService.getMaintenanceHistory(id, {
                page: Number(page),
                limit: Number(limit),
            });
            res.json({
                success: true,
                data: history,
            });
        }
        catch (error) {
            next(error);
        }
    }
    async createCanal(req, res, next) {
        try {
            const canal = await canal_service_1.canalService.createCanal(req.body);
            res.status(201).json({
                success: true,
                data: canal,
                message: 'Canal created successfully',
            });
        }
        catch (error) {
            next(error);
        }
    }
    async updateCanal(req, res, next) {
        try {
            const { id } = req.params;
            const canal = await canal_service_1.canalService.updateCanal(id, req.body);
            res.json({
                success: true,
                data: canal,
                message: 'Canal updated successfully',
            });
        }
        catch (error) {
            next(error);
        }
    }
    async updateCanalGeometry(req, res, next) {
        try {
            const { id } = req.params;
            const { geometry } = req.body;
            const canal = await canal_service_1.canalService.updateCanalGeometry(id, geometry);
            res.json({
                success: true,
                data: canal,
                message: 'Canal geometry updated successfully',
            });
        }
        catch (error) {
            next(error);
        }
    }
    async deleteCanal(req, res, next) {
        try {
            const { id } = req.params;
            await canal_service_1.canalService.deleteCanal(id);
            res.json({
                success: true,
                message: 'Canal deleted successfully',
            });
        }
        catch (error) {
            next(error);
        }
    }
    async analyzeNetwork(req, res, next) {
        try {
            const { sourceId, targetIds, analysisType } = req.body;
            const analysis = await canal_service_1.canalService.analyzeNetwork({
                sourceId,
                targetIds,
                analysisType,
            });
            res.json({
                success: true,
                data: analysis,
            });
        }
        catch (error) {
            next(error);
        }
    }
    async optimizeFlow(req, res, next) {
        try {
            const { constraints, objectives } = req.body;
            const optimization = await canal_service_1.canalService.optimizeFlow({
                constraints,
                objectives,
            });
            res.json({
                success: true,
                data: optimization,
            });
        }
        catch (error) {
            next(error);
        }
    }
    async identifyBottlenecks(req, res, next) {
        try {
            const { threshold = 0.8, includeRecommendations = true } = req.query;
            const bottlenecks = await canal_service_1.canalService.identifyBottlenecks({
                threshold: Number(threshold),
                includeRecommendations: includeRecommendations === 'true',
            });
            res.json({
                success: true,
                data: bottlenecks,
                count: bottlenecks.length,
            });
        }
        catch (error) {
            next(error);
        }
    }
    async bulkImportCanals(req, res, next) {
        try {
            const { format = 'geojson' } = req.query;
            const result = await canal_service_1.canalService.bulkImportCanals(req.body, format);
            res.json({
                success: true,
                data: result,
                message: `Successfully imported ${result.imported} canals`,
            });
        }
        catch (error) {
            next(error);
        }
    }
    async bulkUpdateCanals(req, res, next) {
        try {
            const { canals } = req.body;
            const result = await canal_service_1.canalService.bulkUpdateCanals(canals);
            res.json({
                success: true,
                data: result,
                message: `Successfully updated ${result.updated} canals`,
            });
        }
        catch (error) {
            next(error);
        }
    }
}
exports.canalController = new CanalController();
//# sourceMappingURL=canal.controller.js.map