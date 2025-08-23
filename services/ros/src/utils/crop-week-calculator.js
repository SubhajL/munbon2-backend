"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.calculateCropWeek = calculateCropWeek;
exports.getCalendarWeekFromCropWeek = getCalendarWeekFromCropWeek;
exports.getCurrentCropWeekInfo = getCurrentCropWeekInfo;
exports.calculatePlantingDateFromCropWeek = calculatePlantingDateFromCropWeek;
exports.isValidCropWeek = isValidCropWeek;
const dayjs_1 = __importDefault(require("dayjs"));
const weekOfYear_1 = __importDefault(require("dayjs/plugin/weekOfYear"));
dayjs_1.default.extend(weekOfYear_1.default);
/**
 * Calculate crop week based on planting date
 * @param plantingDate - The date when the crop was planted
 * @param currentDate - The current date (optional, defaults to today)
 * @returns The crop week (1-based) or null if before planting
 */
function calculateCropWeek(plantingDate, currentDate = new Date()) {
    const planting = (0, dayjs_1.default)(plantingDate).startOf('day');
    const current = (0, dayjs_1.default)(currentDate).startOf('day');
    // If current date is before planting date, return null
    if (current.isBefore(planting)) {
        return null;
    }
    // Calculate the difference in days
    const daysDiff = current.diff(planting, 'day');
    // Calculate crop week (1-based)
    // Week 1 = days 0-6, Week 2 = days 7-13, etc.
    const cropWeek = Math.floor(daysDiff / 7) + 1;
    return cropWeek;
}
/**
 * Calculate calendar week and year for a given crop week from planting date
 * @param plantingDate - The date when the crop was planted
 * @param cropWeek - The crop week (1-based)
 * @returns Object with calendarWeek and calendarYear
 */
function getCalendarWeekFromCropWeek(plantingDate, cropWeek) {
    // Calculate the date for this crop week
    const targetDate = (0, dayjs_1.default)(plantingDate).add(cropWeek - 1, 'week');
    return {
        calendarWeek: targetDate.week(),
        calendarYear: targetDate.year()
    };
}
/**
 * Get current crop week and calendar info
 * @param plantingDate - The date when the crop was planted
 * @returns Object with cropWeek, calendarWeek, and calendarYear
 */
function getCurrentCropWeekInfo(plantingDate) {
    const currentDate = new Date();
    const cropWeek = calculateCropWeek(plantingDate, currentDate);
    const current = (0, dayjs_1.default)(currentDate);
    return {
        cropWeek,
        calendarWeek: current.week(),
        calendarYear: current.year()
    };
}
/**
 * Calculate planting date from current crop week
 * @param cropWeek - Current crop week (1-based)
 * @param currentDate - Current date (optional, defaults to today)
 * @returns The estimated planting date
 */
function calculatePlantingDateFromCropWeek(cropWeek, currentDate = new Date()) {
    // Subtract (cropWeek - 1) weeks from current date
    return (0, dayjs_1.default)(currentDate)
        .subtract(cropWeek - 1, 'week')
        .startOf('week')
        .toDate();
}
/**
 * Validate if crop week is within valid range for crop type
 * @param cropType - Type of crop
 * @param cropWeek - Crop week to validate
 * @returns boolean indicating if valid
 */
function isValidCropWeek(cropType, cropWeek) {
    const maxWeeks = {
        rice: 16, // ~4 months
        corn: 14, // ~3.5 months
        sugarcane: 52 // ~12 months
    };
    const maxWeek = maxWeeks[cropType] || 16; // Default to 16 weeks
    return cropWeek >= 1 && cropWeek <= maxWeek;
}
//# sourceMappingURL=crop-week-calculator.js.map