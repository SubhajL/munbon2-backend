"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const express_1 = require("express");
const area_controller_1 = require("@controllers/area.controller");
const validate_request_1 = require("@middleware/validate-request");
const area_validation_1 = require("@utils/validation/area.validation");
const router = (0, express_1.Router)();
// Get area statistics
router.get('/statistics', area_controller_1.areaController.getAreaStatistics);
// Create new area
router.post('/', (0, validate_request_1.validateRequest)(area_validation_1.areaValidation.createArea), area_controller_1.areaController.createArea);
// Import multiple areas
router.post('/import', (0, validate_request_1.validateRequest)(area_validation_1.areaValidation.importAreas), area_controller_1.areaController.importAreas);
// Get area by ID
router.get('/:areaId', (0, validate_request_1.validateRequest)(area_validation_1.areaValidation.getAreaById), area_controller_1.areaController.getAreaById);
// Update area
router.put('/:areaId', (0, validate_request_1.validateRequest)(area_validation_1.areaValidation.updateArea), area_controller_1.areaController.updateArea);
// Delete area
router.delete('/:areaId', (0, validate_request_1.validateRequest)(area_validation_1.areaValidation.deleteArea), area_controller_1.areaController.deleteArea);
// Get areas by type
router.get('/type/:areaType', (0, validate_request_1.validateRequest)(area_validation_1.areaValidation.getAreasByType), area_controller_1.areaController.getAreasByType);
// Get child areas
router.get('/:areaId/children', (0, validate_request_1.validateRequest)(area_validation_1.areaValidation.getChildAreas), area_controller_1.areaController.getChildAreas);
// Get area hierarchy
router.get('/hierarchy/:projectId', (0, validate_request_1.validateRequest)(area_validation_1.areaValidation.getAreaHierarchy), area_controller_1.areaController.getAreaHierarchy);
// Calculate total area
router.get('/:areaId/total-area', (0, validate_request_1.validateRequest)(area_validation_1.areaValidation.calculateTotalArea), area_controller_1.areaController.calculateTotalArea);
exports.default = router;
//# sourceMappingURL=area.routes.js.map