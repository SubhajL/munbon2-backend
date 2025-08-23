"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.areaController = void 0;
const area_service_1 = require("@services/area.service");
const logger_1 = require("@utils/logger");
class AreaController {
    /**
     * Create a new area
     */
    async createArea(req, res, next) {
        try {
            const areaInfo = req.body;
            const area = await area_service_1.areaService.createArea(areaInfo);
            res.status(201).json({
                success: true,
                data: area,
            });
        }
        catch (error) {
            logger_1.logger.error('Error creating area', error);
            next(error);
        }
    }
    /**
     * Get area by ID
     */
    async getAreaById(req, res, next) {
        try {
            const { areaId } = req.params;
            const area = await area_service_1.areaService.getAreaById(areaId);
            if (!area) {
                res.status(404).json({
                    success: false,
                    message: `Area ${areaId} not found`,
                });
                return;
            }
            res.status(200).json({
                success: true,
                data: area,
            });
        }
        catch (error) {
            logger_1.logger.error('Error getting area', error);
            next(error);
        }
    }
    /**
     * Get areas by type
     */
    async getAreasByType(req, res, next) {
        try {
            const { areaType } = req.params;
            const areas = await area_service_1.areaService.getAreasByType(areaType);
            res.status(200).json({
                success: true,
                data: areas,
                count: areas.length,
            });
        }
        catch (error) {
            logger_1.logger.error('Error getting areas by type', error);
            next(error);
        }
    }
    /**
     * Get child areas
     */
    async getChildAreas(req, res, next) {
        try {
            const { areaId } = req.params;
            const childAreas = await area_service_1.areaService.getChildAreas(areaId);
            res.status(200).json({
                success: true,
                data: childAreas,
                count: childAreas.length,
            });
        }
        catch (error) {
            logger_1.logger.error('Error getting child areas', error);
            next(error);
        }
    }
    /**
     * Update area
     */
    async updateArea(req, res, next) {
        try {
            const { areaId } = req.params;
            const updates = req.body;
            const area = await area_service_1.areaService.updateArea(areaId, updates);
            if (!area) {
                res.status(404).json({
                    success: false,
                    message: `Area ${areaId} not found`,
                });
                return;
            }
            res.status(200).json({
                success: true,
                data: area,
            });
        }
        catch (error) {
            logger_1.logger.error('Error updating area', error);
            next(error);
        }
    }
    /**
     * Delete area
     */
    async deleteArea(req, res, next) {
        try {
            const { areaId } = req.params;
            const deleted = await area_service_1.areaService.deleteArea(areaId);
            if (!deleted) {
                res.status(404).json({
                    success: false,
                    message: `Area ${areaId} not found`,
                });
                return;
            }
            res.status(200).json({
                success: true,
                message: `Area ${areaId} deleted successfully`,
            });
        }
        catch (error) {
            logger_1.logger.error('Error deleting area', error);
            next(error);
        }
    }
    /**
     * Get area hierarchy
     */
    async getAreaHierarchy(req, res, next) {
        try {
            const { projectId } = req.params;
            const hierarchy = await area_service_1.areaService.getAreaHierarchy(projectId);
            res.status(200).json({
                success: true,
                data: hierarchy,
            });
        }
        catch (error) {
            logger_1.logger.error('Error getting area hierarchy', error);
            next(error);
        }
    }
    /**
     * Calculate total area
     */
    async calculateTotalArea(req, res, next) {
        try {
            const { areaId } = req.params;
            const totalArea = await area_service_1.areaService.calculateTotalArea(areaId);
            res.status(200).json({
                success: true,
                data: {
                    parentAreaId: areaId,
                    totalAreaRai: totalArea,
                },
            });
        }
        catch (error) {
            logger_1.logger.error('Error calculating total area', error);
            next(error);
        }
    }
    /**
     * Import areas
     */
    async importAreas(req, res, next) {
        try {
            const areas = req.body.areas;
            if (!Array.isArray(areas)) {
                res.status(400).json({
                    success: false,
                    message: 'Areas must be an array',
                });
                return;
            }
            const result = await area_service_1.areaService.importAreas(areas);
            res.status(200).json({
                success: true,
                data: result,
            });
        }
        catch (error) {
            logger_1.logger.error('Error importing areas', error);
            next(error);
        }
    }
    /**
     * Get area statistics
     */
    async getAreaStatistics(req, res, next) {
        try {
            const stats = await area_service_1.areaService.getAreaStatistics();
            res.status(200).json({
                success: true,
                data: stats,
            });
        }
        catch (error) {
            logger_1.logger.error('Error getting area statistics', error);
            next(error);
        }
    }
}
exports.areaController = new AreaController();
//# sourceMappingURL=area.controller.js.map