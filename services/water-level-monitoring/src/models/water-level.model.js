"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.AlertSeverity = exports.WaterLevelAlertType = void 0;
var WaterLevelAlertType;
(function (WaterLevelAlertType) {
    WaterLevelAlertType["LOW_WATER"] = "LOW_WATER";
    WaterLevelAlertType["CRITICAL_LOW_WATER"] = "CRITICAL_LOW_WATER";
    WaterLevelAlertType["HIGH_WATER"] = "HIGH_WATER";
    WaterLevelAlertType["CRITICAL_HIGH_WATER"] = "CRITICAL_HIGH_WATER";
    WaterLevelAlertType["RAPID_INCREASE"] = "RAPID_INCREASE";
    WaterLevelAlertType["RAPID_DECREASE"] = "RAPID_DECREASE";
    WaterLevelAlertType["SENSOR_OFFLINE"] = "SENSOR_OFFLINE";
    WaterLevelAlertType["BATTERY_LOW"] = "BATTERY_LOW";
    WaterLevelAlertType["SIGNAL_WEAK"] = "SIGNAL_WEAK";
})(WaterLevelAlertType || (exports.WaterLevelAlertType = WaterLevelAlertType = {}));
var AlertSeverity;
(function (AlertSeverity) {
    AlertSeverity["INFO"] = "info";
    AlertSeverity["WARNING"] = "warning";
    AlertSeverity["CRITICAL"] = "critical";
})(AlertSeverity || (exports.AlertSeverity = AlertSeverity = {}));
//# sourceMappingURL=water-level.model.js.map