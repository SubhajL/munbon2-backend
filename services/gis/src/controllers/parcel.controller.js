"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.parcelController = void 0;
const parcel_service_1 = require("../services/parcel.service");
const api_error_1 = require("../utils/api-error");
class ParcelController {
    async getAllParcels(req, res, next) {
        try {
            const { page = 1, limit = 100, includeGeometry = false, zoneId, landUseType, irrigationStatus } = req.query;
            const parcels = await parcel_service_1.parcelService.getAllParcels({
                page: Number(page),
                limit: Number(limit),
                includeGeometry: includeGeometry === 'true',
                filters: {
                    zoneId: zoneId,
                    landUseType: landUseType,
                    irrigationStatus: irrigationStatus,
                },
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
    async getParcelById(req, res, next) {
        try {
            const { id } = req.params;
            const parcel = await parcel_service_1.parcelService.getParcelById(id);
            if (!parcel) {
                throw new api_error_1.ApiError(404, 'Parcel not found');
            }
            res.json({
                success: true,
                data: parcel,
            });
        }
        catch (error) {
            next(error);
        }
    }
    async queryParcels(req, res, next) {
        try {
            const parcels = await parcel_service_1.parcelService.queryParcels(req.body);
            res.json({
                success: true,
                data: parcels,
                count: parcels.length,
            });
        }
        catch (error) {
            next(error);
        }
    }
    async getParcelHistory(req, res, next) {
        try {
            const { id } = req.params;
            const { startDate, endDate } = req.query;
            const history = await parcel_service_1.parcelService.getParcelHistory(id, {
                startDate: startDate,
                endDate: endDate,
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
    async getParcelsByOwner(req, res, next) {
        try {
            const { ownerId } = req.params;
            const { page = 1, limit = 50 } = req.query;
            const parcels = await parcel_service_1.parcelService.getParcelsByOwner(ownerId, {
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
    async getCropPlan(req, res, next) {
        try {
            const { id } = req.params;
            const { season, year } = req.query;
            const cropPlan = await parcel_service_1.parcelService.getCropPlan(id, {
                season: season,
                year: year ? Number(year) : new Date().getFullYear(),
            });
            res.json({
                success: true,
                data: cropPlan,
            });
        }
        catch (error) {
            next(error);
        }
    }
    async updateCropPlan(req, res, next) {
        try {
            const { id } = req.params;
            const cropPlan = await parcel_service_1.parcelService.updateCropPlan(id, req.body);
            res.json({
                success: true,
                data: cropPlan,
                message: 'Crop plan updated successfully',
            });
        }
        catch (error) {
            next(error);
        }
    }
    async createParcel(req, res, next) {
        try {
            const parcel = await parcel_service_1.parcelService.createParcel(req.body);
            res.status(201).json({
                success: true,
                data: parcel,
                message: 'Parcel created successfully',
            });
        }
        catch (error) {
            next(error);
        }
    }
    async updateParcel(req, res, next) {
        try {
            const { id } = req.params;
            const parcel = await parcel_service_1.parcelService.updateParcel(id, req.body);
            res.json({
                success: true,
                data: parcel,
                message: 'Parcel updated successfully',
            });
        }
        catch (error) {
            next(error);
        }
    }
    async updateParcelGeometry(req, res, next) {
        try {
            const { id } = req.params;
            const { geometry } = req.body;
            const parcel = await parcel_service_1.parcelService.updateParcelGeometry(id, geometry);
            res.json({
                success: true,
                data: parcel,
                message: 'Parcel geometry updated successfully',
            });
        }
        catch (error) {
            next(error);
        }
    }
    async transferOwnership(req, res, next) {
        try {
            const { id } = req.params;
            const { newOwnerId, transferDate, notes } = req.body;
            const result = await parcel_service_1.parcelService.transferOwnership(id, {
                newOwnerId,
                transferDate,
                notes,
                transferredBy: req.user?.id,
            });
            res.json({
                success: true,
                data: result,
                message: 'Ownership transferred successfully',
            });
        }
        catch (error) {
            next(error);
        }
    }
    async deleteParcel(req, res, next) {
        try {
            const { id } = req.params;
            await parcel_service_1.parcelService.deleteParcel(id);
            res.json({
                success: true,
                message: 'Parcel deleted successfully',
            });
        }
        catch (error) {
            next(error);
        }
    }
    async bulkImportParcels(req, res, next) {
        try {
            const { format = 'geojson', zoneId } = req.query;
            const result = await parcel_service_1.parcelService.bulkImportParcels(req.body, {
                format: format,
                zoneId: zoneId,
            });
            res.json({
                success: true,
                data: result,
                message: `Successfully imported ${result.imported} parcels`,
            });
        }
        catch (error) {
            next(error);
        }
    }
    async bulkUpdateParcels(req, res, next) {
        try {
            const { parcels } = req.body;
            const result = await parcel_service_1.parcelService.bulkUpdateParcels(parcels);
            res.json({
                success: true,
                data: result,
                message: `Successfully updated ${result.updated} parcels`,
            });
        }
        catch (error) {
            next(error);
        }
    }
    async mergeParcels(req, res, next) {
        try {
            const { parcelIds, newParcelData } = req.body;
            const mergedParcel = await parcel_service_1.parcelService.mergeParcels(parcelIds, newParcelData);
            res.json({
                success: true,
                data: mergedParcel,
                message: 'Parcels merged successfully',
            });
        }
        catch (error) {
            next(error);
        }
    }
    async splitParcel(req, res, next) {
        try {
            const { id } = req.params;
            const { splitGeometries, splitData } = req.body;
            const newParcels = await parcel_service_1.parcelService.splitParcel(id, {
                splitGeometries,
                splitData,
            });
            res.json({
                success: true,
                data: newParcels,
                message: 'Parcel split successfully',
            });
        }
        catch (error) {
            next(error);
        }
    }
}
exports.parcelController = new ParcelController();
//# sourceMappingURL=parcel.controller.js.map