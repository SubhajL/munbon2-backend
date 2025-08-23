"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.parcelsRoutes = void 0;
const express_1 = require("express");
const express_validator_1 = require("express-validator");
const parcels_controller_1 = require("../controllers/parcels.controller");
const async_handler_1 = require("../middleware/async-handler");
const router = (0, express_1.Router)();
const controller = new parcels_controller_1.ParcelsController();
router.get('/', [
    (0, express_validator_1.query)('zone').optional().isString().trim(),
    (0, express_validator_1.query)('cropType').optional().isString().trim(),
    (0, express_validator_1.query)('ownerName').optional().isString().trim(),
    (0, express_validator_1.query)('waterDemandMethod').optional().isIn(['RID-MS', 'ROS', 'AWD']),
    (0, express_validator_1.query)('limit').optional().isInt({ min: 1, max: 1000 }).toInt(),
    (0, express_validator_1.query)('offset').optional().isInt({ min: 0 }).toInt(),
    (0, express_validator_1.query)('sortBy').optional().isIn(['parcelId', 'zone', 'areaRai', 'createdAt']),
    (0, express_validator_1.query)('sortOrder').optional().isIn(['asc', 'desc']),
], (0, async_handler_1.asyncHandler)(controller.listParcels));
router.get('/search', [
    (0, express_validator_1.query)('q').notEmpty().isString().trim(),
    (0, express_validator_1.query)('searchFields').optional().isString(),
    (0, express_validator_1.query)('limit').optional().isInt({ min: 1, max: 100 }).toInt(),
], (0, async_handler_1.asyncHandler)(controller.searchParcels));
router.get('/at-date', [
    (0, express_validator_1.query)('date').notEmpty().isISO8601(),
    (0, express_validator_1.query)('zone').optional().isString().trim(),
    (0, express_validator_1.query)('limit').optional().isInt({ min: 1, max: 1000 }).toInt(),
    (0, express_validator_1.query)('offset').optional().isInt({ min: 0 }).toInt(),
], (0, async_handler_1.asyncHandler)(controller.getParcelsAtDate));
router.get('/:id', [
    (0, express_validator_1.param)('id').isUUID(),
], (0, async_handler_1.asyncHandler)(controller.getParcelById));
router.get('/history/:parcelId', [
    (0, express_validator_1.param)('parcelId').notEmpty().isString(),
], (0, async_handler_1.asyncHandler)(controller.getParcelHistory));
router.put('/:id', [
    (0, express_validator_1.param)('id').isUUID(),
    (0, express_validator_1.body)('cropType').optional().isString().trim(),
    (0, express_validator_1.body)('waterDemandMethod').optional().isIn(['RID-MS', 'ROS', 'AWD']),
    (0, express_validator_1.body)('ownerName').optional().isString().trim(),
    (0, express_validator_1.body)('plantingDate').optional().isISO8601(),
    (0, express_validator_1.body)('harvestDate').optional().isISO8601(),
], (0, async_handler_1.asyncHandler)(controller.updateParcel));
exports.parcelsRoutes = router;
//# sourceMappingURL=parcels.routes.js.map