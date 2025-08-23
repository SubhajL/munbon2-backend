"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.awdManagementRouter = void 0;
const express_1 = require("express");
const awd_management_controller_1 = require("../controllers/awd-management.controller");
exports.awdManagementRouter = (0, express_1.Router)();
exports.awdManagementRouter.post('/initialize', awd_management_controller_1.awdManagementController.initializeField);
exports.awdManagementRouter.get('/decision/:fieldId', awd_management_controller_1.awdManagementController.getControlDecision);
exports.awdManagementRouter.post('/section/start-dates', awd_management_controller_1.awdManagementController.updateSectionStartDates);
exports.awdManagementRouter.get('/schedule/:plantingMethod', awd_management_controller_1.awdManagementController.getSchedule);
//# sourceMappingURL=awd-management.routes.js.map