"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.WeatherCondition = exports.AlertSeverity = exports.WeatherAlertType = exports.StationType = exports.WeatherDataSource = void 0;
var WeatherDataSource;
(function (WeatherDataSource) {
    WeatherDataSource["TMD"] = "TMD";
    WeatherDataSource["AOS"] = "AOS";
    WeatherDataSource["OPENWEATHER"] = "OPENWEATHER";
    WeatherDataSource["CUSTOM"] = "CUSTOM";
    WeatherDataSource["AGGREGATED"] = "AGGREGATED";
})(WeatherDataSource || (exports.WeatherDataSource = WeatherDataSource = {}));
var StationType;
(function (StationType) {
    StationType["SYNOPTIC"] = "SYNOPTIC";
    StationType["AUTOMATIC"] = "AUTOMATIC";
    StationType["AERONAUTICAL"] = "AERONAUTICAL";
    StationType["AGRICULTURAL"] = "AGRICULTURAL";
    StationType["RAIN_GAUGE"] = "RAIN_GAUGE";
})(StationType || (exports.StationType = StationType = {}));
var WeatherAlertType;
(function (WeatherAlertType) {
    WeatherAlertType["EXTREME_HEAT"] = "EXTREME_HEAT";
    WeatherAlertType["EXTREME_COLD"] = "EXTREME_COLD";
    WeatherAlertType["HEAVY_RAIN"] = "HEAVY_RAIN";
    WeatherAlertType["STRONG_WIND"] = "STRONG_WIND";
    WeatherAlertType["FROST_WARNING"] = "FROST_WARNING";
    WeatherAlertType["DROUGHT_WARNING"] = "DROUGHT_WARNING";
    WeatherAlertType["STORM_WARNING"] = "STORM_WARNING";
    WeatherAlertType["HAIL_WARNING"] = "HAIL_WARNING";
})(WeatherAlertType || (exports.WeatherAlertType = WeatherAlertType = {}));
var AlertSeverity;
(function (AlertSeverity) {
    AlertSeverity["INFO"] = "info";
    AlertSeverity["WARNING"] = "warning";
    AlertSeverity["CRITICAL"] = "critical";
})(AlertSeverity || (exports.AlertSeverity = AlertSeverity = {}));
var WeatherCondition;
(function (WeatherCondition) {
    WeatherCondition["CLEAR"] = "clear";
    WeatherCondition["PARTLY_CLOUDY"] = "partly_cloudy";
    WeatherCondition["CLOUDY"] = "cloudy";
    WeatherCondition["OVERCAST"] = "overcast";
    WeatherCondition["LIGHT_RAIN"] = "light_rain";
    WeatherCondition["MODERATE_RAIN"] = "moderate_rain";
    WeatherCondition["HEAVY_RAIN"] = "heavy_rain";
    WeatherCondition["THUNDERSTORM"] = "thunderstorm";
    WeatherCondition["FOG"] = "fog";
    WeatherCondition["HAZE"] = "haze";
})(WeatherCondition || (exports.WeatherCondition = WeatherCondition = {}));
//# sourceMappingURL=weather.model.js.map