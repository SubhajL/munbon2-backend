"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.zoneController = void 0;
const zone_service_1 = require("../services/zone.service");
const api_error_1 = require("../utils/api-error");
class ZoneController {
    async getAllZones(req, res, next) {
        try {
            const { page = 1, limit = 50, includeGeometry = false } = req.query;
            const zones = await zone_service_1.zoneService.getAllZones({
                page: Number(page),
                limit: Number(limit),
                includeGeometry: includeGeometry === 'true',
            });
            res.json({
                success: true,
                data: zones,
            });
        }
        catch (error) {
            next(error);
        }
    }
    async getZoneById(req, res, next) {
        try {
            const { id } = req.params;
            const zone = await zone_service_1.zoneService.getZoneById(id);
            if (!zone) {
                throw new api_error_1.ApiError(404, 'Zone not found');
            }
            res.json({
                success: true,
                data: zone,
            });
        }
        catch (error) {
            next(error);
        }
    }
    async queryZones(req, res, next) {
        try {
            const zones = await zone_service_1.zoneService.queryZones(req.body);
            res.json({
                success: true,
                data: zones,
                count: zones.length,
            });
        }
        catch (error) {
            next(error);
        }
    }
    async getZoneStatistics(req, res, next) {
        try {
            const { id } = req.params;
            const stats = await zone_service_1.zoneService.getZoneStatistics(id);
            res.json({
                success: true,
                data: stats,
            });
        }
        catch (error) {
            next(error);
        }
    }
    async getParcelsInZone(req, res, next) {
        try {
            const { id } = req.params;
            const { page = 1, limit = 100 } = req.query;
            const parcels = await zone_service_1.zoneService.getParcelsInZone(id, {
                page: Number(page),
                limit: Number(limit),
            });
            res.json({
                success: true,
                data: parcels,
            });
        }
        catch (error) {
            next(error);
        }
    }
    async getWaterDistribution(req, res, next) {
        try {
            const { id } = req.params;
            const { startDate, endDate } = req.query;
            const distribution = await zone_service_1.zoneService.getWaterDistribution(id, {
                startDate: startDate,
                endDate: endDate,
            });
            res.json({
                success: true,
                data: distribution,
            });
        }
        catch (error) {
            next(error);
        }
    }
    async createZone(req, res, next) {
        try {
            const zone = await zone_service_1.zoneService.createZone(req.body);
            res.status(201).json({
                success: true,
                data: zone,
                message: 'Zone created successfully',
            });
        }
        catch (error) {
            next(error);
        }
    }
    async updateZone(req, res, next) {
        try {
            const { id } = req.params;
            const zone = await zone_service_1.zoneService.updateZone(id, req.body);
            res.json({
                success: true,
                data: zone,
                message: 'Zone updated successfully',
            });
        }
        catch (error) {
            next(error);
        }
    }
    async updateZoneGeometry(req, res, next) {
        try {
            const { id } = req.params;
            const { geometry } = req.body;
            const zone = await zone_service_1.zoneService.updateZoneGeometry(id, geometry);
            res.json({
                success: true,
                data: zone,
                message: 'Zone geometry updated successfully',
            });
        }
        catch (error) {
            next(error);
        }
    }
    async deleteZone(req, res, next) {
        try {
            const { id } = req.params;
            await zone_service_1.zoneService.deleteZone(id);
            res.json({
                success: true,
                message: 'Zone deleted successfully',
            });
        }
        catch (error) {
            next(error);
        }
    }
    async bulkImportZones(req, res, next) {
        try {
            const { format = 'geojson' } = req.query;
            const result = await zone_service_1.zoneService.bulkImportZones(req.body, format);
            res.json({
                success: true,
                data: result,
                message: `Successfully imported ${result.imported} zones`,
            });
        }
        catch (error) {
            next(error);
        }
    }
    async bulkUpdateZones(req, res, next) {
        try {
            const { zones } = req.body;
            const result = await zone_service_1.zoneService.bulkUpdateZones(zones);
            res.json({
                success: true,
                data: result,
                message: `Successfully updated ${result.updated} zones`,
            });
        }
        catch (error) {
            next(error);
        }
    }
}
exports.zoneController = new ZoneController();
//# sourceMappingURL=zone.controller.js.map