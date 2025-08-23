"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.zonesRoutes = void 0;
const express_1 = require("express");
const express_validator_1 = require("express-validator");
const zones_controller_1 = require("../controllers/zones.controller");
const async_handler_1 = require("../middleware/async-handler");
const router = (0, express_1.Router)();
const controller = new zones_controller_1.ZonesController();
router.get('/', [
    (0, express_validator_1.query)('includeStats').optional().isBoolean().toBoolean(),
], (0, async_handler_1.asyncHandler)(controller.listZones));
router.get('/:zone/parcels', [
    (0, express_validator_1.param)('zone').notEmpty().isString().trim(),
    (0, express_validator_1.query)('cropType').optional().isString().trim(),
    (0, express_validator_1.query)('waterDemandMethod').optional().isIn(['RID-MS', 'ROS', 'AWD']),
    (0, express_validator_1.query)('limit').optional().isInt({ min: 1, max: 1000 }).toInt(),
    (0, express_validator_1.query)('offset').optional().isInt({ min: 0 }).toInt(),
], (0, async_handler_1.asyncHandler)(controller.getZoneParcels));
router.get('/:zone/summary', [
    (0, express_validator_1.param)('zone').notEmpty().isString().trim(),
    (0, express_validator_1.query)('date').optional().isISO8601(),
], (0, async_handler_1.asyncHandler)(controller.getZoneSummary));
router.get('/:zone/geojson', [
    (0, express_validator_1.param)('zone').notEmpty().isString().trim(),
    (0, express_validator_1.query)('includeWaterDemand').optional().isBoolean().toBoolean(),
    (0, express_validator_1.query)('simplify').optional().isBoolean().toBoolean(),
    (0, express_validator_1.query)('precision').optional().isInt({ min: 0, max: 10 }).toInt(),
], (0, async_handler_1.asyncHandler)(controller.getZoneGeoJSON));
router.get('/:zone/changes', [
    (0, express_validator_1.param)('zone').notEmpty().isString().trim(),
    (0, express_validator_1.query)('startDate').notEmpty().isISO8601(),
    (0, express_validator_1.query)('endDate').notEmpty().isISO8601(),
], (0, async_handler_1.asyncHandler)(controller.getZoneChanges));
exports.zonesRoutes = router;
//# sourceMappingURL=zones.routes.js.map