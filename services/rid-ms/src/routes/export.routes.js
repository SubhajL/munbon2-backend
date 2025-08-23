"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.exportRoutes = void 0;
const express_1 = require("express");
const express_validator_1 = require("express-validator");
const export_controller_1 = require("../controllers/export.controller");
const async_handler_1 = require("../middleware/async-handler");
const router = (0, express_1.Router)();
const controller = new export_controller_1.ExportController();
router.get('/parcels/geojson', [
    (0, express_validator_1.query)('zone').optional().isString().trim(),
    (0, express_validator_1.query)('cropType').optional().isString().trim(),
    (0, express_validator_1.query)('waterDemandMethod').optional().isIn(['RID-MS', 'ROS', 'AWD']),
    (0, express_validator_1.query)('includeWaterDemand').optional().isBoolean().toBoolean(),
    (0, express_validator_1.query)('limit').optional().isInt({ min: 1, max: 10000 }).toInt(),
    (0, express_validator_1.query)('simplify').optional().isBoolean().toBoolean(),
    (0, express_validator_1.query)('precision').optional().isInt({ min: 0, max: 10 }).toInt(),
], (0, async_handler_1.asyncHandler)(controller.exportParcelsGeoJSON));
router.get('/zones/geojson', [
    (0, express_validator_1.query)('includeStats').optional().isBoolean().toBoolean(),
    (0, express_validator_1.query)('includeWaterDemand').optional().isBoolean().toBoolean(),
], (0, async_handler_1.asyncHandler)(controller.exportZonesGeoJSON));
router.get('/water-demand/geojson', [
    (0, express_validator_1.query)('zone').optional().isString().trim(),
    (0, express_validator_1.query)('method').optional().isIn(['RID-MS', 'ROS', 'AWD']),
    (0, express_validator_1.query)('date').optional().isISO8601(),
    (0, express_validator_1.query)('resolution').optional().isIn(['high', 'medium', 'low']),
], (0, async_handler_1.asyncHandler)(controller.exportWaterDemandHeatmap));
router.post('/custom', [
    (0, express_validator_1.body)('type').isIn(['parcels', 'zones', 'water-demand']),
    (0, express_validator_1.body)('filters').optional().isObject(),
    (0, express_validator_1.body)('attributes').optional().isArray(),
    (0, express_validator_1.body)('attributes.*').isString(),
    (0, express_validator_1.body)('format').optional().isIn(['geojson', 'csv', 'kml']),
    (0, express_validator_1.body)('simplify').optional().isBoolean(),
    (0, express_validator_1.body)('precision').optional().isInt({ min: 0, max: 10 }),
], (0, async_handler_1.asyncHandler)(controller.customExport));
exports.exportRoutes = router;
//# sourceMappingURL=export.routes.js.map