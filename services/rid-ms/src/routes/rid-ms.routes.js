"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.ridMsRoutes = void 0;
const express_1 = require("express");
const express_validator_1 = require("express-validator");
const rid_ms_controller_1 = require("../controllers/rid-ms.controller");
const auth_middleware_1 = require("../middleware/auth.middleware");
const router = (0, express_1.Router)();
const controller = new rid_ms_controller_1.RidMsController();
const validateRequest = (req, res, next) => {
    const errors = (0, express_validator_1.validationResult)(req);
    if (!errors.isEmpty()) {
        return res.status(400).json({ errors: errors.array() });
    }
    next();
};
router.get('/shapefiles', auth_middleware_1.authMiddleware, [
    (0, express_validator_1.query)('status')
        .optional()
        .isIn(['pending', 'processing', 'processed', 'failed']),
    (0, express_validator_1.query)('limit').optional().isInt({ min: 1, max: 100 }).toInt(),
    (0, express_validator_1.query)('lastKey').optional().isString(),
], validateRequest, controller.getShapeFiles.bind(controller));
router.get('/shapefiles/:id', auth_middleware_1.authMiddleware, [
    (0, express_validator_1.param)('id').isString().withMessage('Invalid shape file ID'),
], validateRequest, controller.getShapeFileById.bind(controller));
router.get('/shapefiles/:shapeFileId/parcels', auth_middleware_1.authMiddleware, [
    (0, express_validator_1.param)('shapeFileId').isString(),
    (0, express_validator_1.query)('limit').optional().isInt({ min: 1, max: 1000 }).toInt(),
    (0, express_validator_1.query)('lastKey').optional().isString(),
], validateRequest, controller.getParcelsByShapeFile.bind(controller));
router.get('/zones/:zone/parcels', auth_middleware_1.authMiddleware, [
    (0, express_validator_1.param)('zone').isString(),
    (0, express_validator_1.query)('waterDemandMethod')
        .optional()
        .isIn(['RID-MS', 'ROS', 'AWD']),
    (0, express_validator_1.query)('limit').optional().isInt({ min: 1, max: 1000 }).toInt(),
    (0, express_validator_1.query)('lastKey').optional().isString(),
], validateRequest, controller.getParcelsByZone.bind(controller));
router.get('/parcels/:parcelId/water-demand', auth_middleware_1.authMiddleware, [
    (0, express_validator_1.param)('parcelId').isString(),
], validateRequest, controller.getParcelWaterDemand.bind(controller));
router.get('/zones/:zone/water-demand-summary', auth_middleware_1.authMiddleware, [
    (0, express_validator_1.param)('zone').isString(),
], validateRequest, controller.getWaterDemandSummaryByZone.bind(controller));
router.get('/shapefiles/:shapeFileId/geojson', auth_middleware_1.authMiddleware, [
    (0, express_validator_1.param)('shapeFileId').isString(),
    (0, express_validator_1.query)('includeWaterDemand').optional().isBoolean().toBoolean(),
], validateRequest, controller.getGeoJSON.bind(controller));
router.post('/upload-url', auth_middleware_1.authMiddleware, [
    (0, express_validator_1.body)('fileName').isString().withMessage('fileName is required'),
    (0, express_validator_1.body)('waterDemandMethod')
        .optional()
        .isIn(['RID-MS', 'ROS', 'AWD']),
    (0, express_validator_1.body)('processingInterval')
        .optional()
        .isIn(['daily', 'weekly', 'bi-weekly']),
], validateRequest, controller.getUploadUrl.bind(controller));
router.put('/parcels/water-demand-method', auth_middleware_1.authMiddleware, [
    (0, express_validator_1.body)('parcelIds')
        .isArray({ min: 1 })
        .withMessage('parcelIds must be a non-empty array'),
    (0, express_validator_1.body)('parcelIds.*').isString(),
    (0, express_validator_1.body)('method')
        .isIn(['RID-MS', 'ROS', 'AWD'])
        .withMessage('Method must be RID-MS, ROS, or AWD'),
], validateRequest, controller.updateWaterDemandMethod.bind(controller));
exports.ridMsRoutes = router;
//# sourceMappingURL=rid-ms.routes.js.map