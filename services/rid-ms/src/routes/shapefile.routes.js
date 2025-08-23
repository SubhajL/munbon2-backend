"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.shapeFileRoutes = void 0;
const express_1 = require("express");
const multer_1 = __importDefault(require("multer"));
const path_1 = __importDefault(require("path"));
const uuid_1 = require("uuid");
const express_validator_1 = require("express-validator");
const shapefile_controller_1 = require("../controllers/shapefile.controller");
const config_1 = require("../config");
const auth_middleware_1 = require("../middleware/auth.middleware");
const router = (0, express_1.Router)();
const controller = new shapefile_controller_1.ShapeFileController();
const storage = multer_1.default.diskStorage({
    destination: async (req, file, cb) => {
        cb(null, config_1.config.fileProcessing.uploadDir);
    },
    filename: (req, file, cb) => {
        const uniqueName = `${(0, uuid_1.v4)()}${path_1.default.extname(file.originalname)}`;
        cb(null, uniqueName);
    },
});
const upload = (0, multer_1.default)({
    storage,
    limits: {
        fileSize: config_1.config.fileProcessing.maxFileSize,
    },
    fileFilter: (req, file, cb) => {
        const ext = path_1.default.extname(file.originalname).toLowerCase();
        if (config_1.config.fileProcessing.allowedFileTypes.includes(ext)) {
            cb(null, true);
        }
        else {
            cb(new Error(`File type ${ext} is not allowed`));
        }
    },
});
const validateRequest = (req, res, next) => {
    const errors = (0, express_validator_1.validationResult)(req);
    if (!errors.isEmpty()) {
        return res.status(400).json({ errors: errors.array() });
    }
    next();
};
router.post('/upload', auth_middleware_1.authMiddleware, upload.single('shapefile'), [
    (0, express_validator_1.body)('description').optional().isString().trim(),
    (0, express_validator_1.body)('waterDemandMethod')
        .optional()
        .isIn(['RID-MS', 'ROS', 'AWD'])
        .withMessage('Water demand method must be RID-MS, ROS, or AWD'),
    (0, express_validator_1.body)('processingInterval')
        .optional()
        .isIn(['daily', 'weekly', 'bi-weekly'])
        .withMessage('Processing interval must be daily, weekly, or bi-weekly'),
], validateRequest, controller.uploadShapeFile.bind(controller));
router.get('/:id', auth_middleware_1.authMiddleware, [
    (0, express_validator_1.param)('id').isUUID().withMessage('Invalid shape file ID'),
], validateRequest, controller.getShapeFileMetadata.bind(controller));
router.get('/', auth_middleware_1.authMiddleware, [
    (0, express_validator_1.query)('status')
        .optional()
        .isIn(['pending', 'processing', 'processed', 'failed'])
        .withMessage('Invalid status'),
    (0, express_validator_1.query)('page').optional().isInt({ min: 1 }).toInt(),
    (0, express_validator_1.query)('limit').optional().isInt({ min: 1, max: 100 }).toInt(),
    (0, express_validator_1.query)('sortBy')
        .optional()
        .isIn(['uploadDate', 'processedDate', 'fileSize', 'featureCount'])
        .withMessage('Invalid sort field'),
    (0, express_validator_1.query)('sortOrder')
        .optional()
        .isIn(['asc', 'desc'])
        .withMessage('Sort order must be asc or desc'),
], validateRequest, controller.listShapeFiles.bind(controller));
router.get('/:id/parcels', auth_middleware_1.authMiddleware, [
    (0, express_validator_1.param)('id').isUUID().withMessage('Invalid shape file ID'),
    (0, express_validator_1.query)('zone').optional().isString(),
    (0, express_validator_1.query)('cropType').optional().isString(),
    (0, express_validator_1.query)('waterDemandMethod')
        .optional()
        .isIn(['RID-MS', 'ROS', 'AWD']),
    (0, express_validator_1.query)('page').optional().isInt({ min: 1 }).toInt(),
    (0, express_validator_1.query)('limit').optional().isInt({ min: 1, max: 1000 }).toInt(),
], validateRequest, controller.getShapeFileParcels.bind(controller));
router.get('/:id/export/geojson', auth_middleware_1.authMiddleware, [
    (0, express_validator_1.param)('id').isUUID().withMessage('Invalid shape file ID'),
    (0, express_validator_1.query)('includeWaterDemand')
        .optional()
        .isBoolean()
        .toBoolean(),
], validateRequest, controller.exportAsGeoJSON.bind(controller));
router.get('/:id/statistics', auth_middleware_1.authMiddleware, [
    (0, express_validator_1.param)('id').isUUID().withMessage('Invalid shape file ID'),
], validateRequest, controller.getShapeFileStatistics.bind(controller));
router.delete('/:id', auth_middleware_1.authMiddleware, [
    (0, express_validator_1.param)('id').isUUID().withMessage('Invalid shape file ID'),
], validateRequest, controller.deleteShapeFile.bind(controller));
router.post('/:id/reprocess', auth_middleware_1.authMiddleware, [
    (0, express_validator_1.param)('id').isUUID().withMessage('Invalid shape file ID'),
], validateRequest, controller.reprocessShapeFile.bind(controller));
exports.shapeFileRoutes = router;
//# sourceMappingURL=shapefile.routes.js.map