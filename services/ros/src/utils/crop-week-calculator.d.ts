/**
 * Calculate crop week based on planting date
 * @param plantingDate - The date when the crop was planted
 * @param currentDate - The current date (optional, defaults to today)
 * @returns The crop week (1-based) or null if before planting
 */
export declare function calculateCropWeek(plantingDate: Date, currentDate?: Date): number | null;
/**
 * Calculate calendar week and year for a given crop week from planting date
 * @param plantingDate - The date when the crop was planted
 * @param cropWeek - The crop week (1-based)
 * @returns Object with calendarWeek and calendarYear
 */
export declare function getCalendarWeekFromCropWeek(plantingDate: Date, cropWeek: number): {
    calendarWeek: number;
    calendarYear: number;
};
/**
 * Get current crop week and calendar info
 * @param plantingDate - The date when the crop was planted
 * @returns Object with cropWeek, calendarWeek, and calendarYear
 */
export declare function getCurrentCropWeekInfo(plantingDate: Date): {
    cropWeek: number | null;
    calendarWeek: number;
    calendarYear: number;
};
/**
 * Calculate planting date from current crop week
 * @param cropWeek - Current crop week (1-based)
 * @param currentDate - Current date (optional, defaults to today)
 * @returns The estimated planting date
 */
export declare function calculatePlantingDateFromCropWeek(cropWeek: number, currentDate?: Date): Date;
/**
 * Validate if crop week is within valid range for crop type
 * @param cropType - Type of crop
 * @param cropWeek - Crop week to validate
 * @returns boolean indicating if valid
 */
export declare function isValidCropWeek(cropType: string, cropWeek: number): boolean;
//# sourceMappingURL=crop-week-calculator.d.ts.map