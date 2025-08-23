"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.awdRouter = void 0;
const express_1 = require("express");
const fields_routes_1 = require("./fields.routes");
const sensors_routes_1 = require("./sensors.routes");
const irrigation_routes_1 = require("./irrigation.routes");
const analytics_routes_1 = require("./analytics.routes");
const schedules_routes_1 = require("./schedules.routes");
const awd_management_routes_1 = require("./awd-management.routes");
const irrigation_control_routes_1 = __importDefault(require("./irrigation-control.routes"));
const monitoring_dashboard_routes_1 = __importDefault(require("./monitoring-dashboard.routes"));
exports.awdRouter = (0, express_1.Router)();
exports.awdRouter.use('/fields', fields_routes_1.fieldsRouter);
exports.awdRouter.use('/sensors', sensors_routes_1.sensorsRouter);
exports.awdRouter.use('/irrigation', irrigation_routes_1.irrigationRouter);
exports.awdRouter.use('/analytics', analytics_routes_1.analyticsRouter);
exports.awdRouter.use('/schedules', schedules_routes_1.schedulesRouter);
exports.awdRouter.use('/management', awd_management_routes_1.awdManagementRouter);
exports.awdRouter.use('/control', irrigation_control_routes_1.default);
exports.awdRouter.use('/monitoring', monitoring_dashboard_routes_1.default);
exports.awdRouter.get('/status', async (_req, res) => {
    res.json({
        status: 'operational',
        activeFields: 0,
        totalWaterSaved: 0,
        timestamp: new Date().toISOString(),
    });
});
exports.awdRouter.get('/recommendations', async (_req, res) => {
    res.json({
        recommendations: [],
        timestamp: new Date().toISOString(),
    });
});
//# sourceMappingURL=awd.routes.js.map