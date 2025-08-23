"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.ShapeFileController = void 0;
const shapefile_service_1 = require("../services/shapefile.service");
const api_error_1 = require("../utils/api-error");
class ShapeFileController {
    shapeFileService;
    constructor() {
        this.shapeFileService = new shapefile_service_1.ShapeFileService();
    }
    uploadShapeFile = async (req, res, next) => {
        try {
            if (!req.file) {
                throw new api_error_1.ApiError(400, 'No file uploaded');
            }
            const uploadResult = await this.shapeFileService.processUpload({
                file: req.file,
                waterDemandMethod: req.body.waterDemandMethod || 'RID-MS',
                processingInterval: req.body.processingInterval || 'weekly',
                metadata: {
                    uploadedBy: req.user?.id || 'unknown',
                    description: req.body.description,
                    zone: req.body.zone,
                    ...req.body.metadata,
                },
            });
            res.status(202).json({
                success: true,
                message: 'Shape file uploaded and queued for processing',
                data: uploadResult,
            });
        }
        catch (error) {
            next(error);
        }
    };
    externalUpload = async (req, res, next) => {
        try {
            const authHeader = req.headers.authorization;
            if (!authHeader || !authHeader.startsWith('Bearer ')) {
                throw new api_error_1.ApiError(401, 'Missing authorization header');
            }
            const token = authHeader.substring(7);
            if (token !== process.env.EXTERNAL_UPLOAD_TOKEN) {
                throw new api_error_1.ApiError(403, 'Invalid authorization token');
            }
            if (!req.file) {
                throw new api_error_1.ApiError(400, 'No file uploaded');
            }
            const uploadResult = await this.shapeFileService.processUpload({
                file: req.file,
                waterDemandMethod: req.body.waterDemandMethod || 'RID-MS',
                processingInterval: req.body.processingInterval || 'weekly',
                metadata: {
                    uploadedBy: 'external-api',
                    source: 'rid-ms',
                    description: req.body.description,
                    zone: req.body.zone,
                    ...req.body.metadata,
                },
            });
            res.status(202).json({
                success: true,
                message: 'Shape file uploaded successfully',
                uploadId: uploadResult.uploadId,
                fileName: uploadResult.fileName,
                uploadedAt: uploadResult.uploadedAt,
            });
        }
        catch (error) {
            next(error);
        }
    };
    listUploads = async (req, res, next) => {
        try {
            const { page = 1, limit = 20, status, startDate, endDate } = req.query;
            const uploads = await this.shapeFileService.listUploads({
                page: Number(page),
                limit: Number(limit),
                status: status,
                startDate: startDate,
                endDate: endDate,
            });
            res.json({
                success: true,
                data: uploads,
            });
        }
        catch (error) {
            next(error);
        }
    };
    getUploadStatus = async (req, res, next) => {
        try {
            const { uploadId } = req.params;
            const status = await this.shapeFileService.getUploadStatus(uploadId);
            if (!status) {
                throw new api_error_1.ApiError(404, 'Upload not found');
            }
            res.json({
                success: true,
                data: status,
            });
        }
        catch (error) {
            next(error);
        }
    };
    getUploadParcels = async (req, res, next) => {
        try {
            const { uploadId } = req.params;
            const { format = 'json' } = req.query;
            const parcels = await this.shapeFileService.getUploadParcels(uploadId);
            if (format === 'geojson') {
                res.json({
                    type: 'FeatureCollection',
                    features: parcels.map(parcel => ({
                        type: 'Feature',
                        id: parcel.id,
                        geometry: parcel.geometry,
                        properties: {
                            parcelCode: parcel.parcelCode,
                            zoneId: parcel.zoneId,
                            area: parcel.area,
                            ownerName: parcel.ownerName,
                            landUseType: parcel.landUseType,
                            status: parcel.status,
                        },
                    })),
                });
            }
            else {
                res.json({
                    success: true,
                    data: parcels,
                });
            }
        }
        catch (error) {
            next(error);
        }
    };
    deleteUpload = async (req, res, next) => {
        try {
            const { uploadId } = req.params;
            await this.shapeFileService.deleteUpload(uploadId);
            res.json({
                success: true,
                message: 'Upload and associated parcels deleted successfully',
            });
        }
        catch (error) {
            next(error);
        }
    };
}
exports.ShapeFileController = ShapeFileController;
//# sourceMappingURL=shapefile.controller.js.map