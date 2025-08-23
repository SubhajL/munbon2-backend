"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.AlertSeverity = exports.MoistureAlertType = void 0;
var MoistureAlertType;
(function (MoistureAlertType) {
    MoistureAlertType["LOW_MOISTURE"] = "LOW_MOISTURE";
    MoistureAlertType["CRITICAL_LOW_MOISTURE"] = "CRITICAL_LOW_MOISTURE";
    MoistureAlertType["HIGH_MOISTURE"] = "HIGH_MOISTURE";
    MoistureAlertType["FLOOD_DETECTED"] = "FLOOD_DETECTED";
    MoistureAlertType["SENSOR_OFFLINE"] = "SENSOR_OFFLINE";
    MoistureAlertType["BATTERY_LOW"] = "BATTERY_LOW";
})(MoistureAlertType || (exports.MoistureAlertType = MoistureAlertType = {}));
var AlertSeverity;
(function (AlertSeverity) {
    AlertSeverity["INFO"] = "info";
    AlertSeverity["WARNING"] = "warning";
    AlertSeverity["CRITICAL"] = "critical";
})(AlertSeverity || (exports.AlertSeverity = AlertSeverity = {}));
//# sourceMappingURL=moisture.model.js.map