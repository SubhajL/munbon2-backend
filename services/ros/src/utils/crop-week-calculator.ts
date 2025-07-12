import dayjs from 'dayjs';
import weekOfYear from 'dayjs/plugin/weekOfYear';

dayjs.extend(weekOfYear);

/**
 * Calculate crop week based on planting date
 * @param plantingDate - The date when the crop was planted
 * @param currentDate - The current date (optional, defaults to today)
 * @returns The crop week (1-based) or null if before planting
 */
export function calculateCropWeek(plantingDate: Date, currentDate: Date = new Date()): number | null {
  const planting = dayjs(plantingDate).startOf('day');
  const current = dayjs(currentDate).startOf('day');
  
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
export function getCalendarWeekFromCropWeek(
  plantingDate: Date, 
  cropWeek: number
): { calendarWeek: number; calendarYear: number } {
  // Calculate the date for this crop week
  const targetDate = dayjs(plantingDate).add(cropWeek - 1, 'week');
  
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
export function getCurrentCropWeekInfo(plantingDate: Date): {
  cropWeek: number | null;
  calendarWeek: number;
  calendarYear: number;
} {
  const currentDate = new Date();
  const cropWeek = calculateCropWeek(plantingDate, currentDate);
  const current = dayjs(currentDate);
  
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
export function calculatePlantingDateFromCropWeek(
  cropWeek: number, 
  currentDate: Date = new Date()
): Date {
  // Subtract (cropWeek - 1) weeks from current date
  return dayjs(currentDate)
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
export function isValidCropWeek(cropType: string, cropWeek: number): boolean {
  const maxWeeks: Record<string, number> = {
    rice: 16,      // ~4 months
    corn: 14,      // ~3.5 months
    sugarcane: 52  // ~12 months
  };
  
  const maxWeek = maxWeeks[cropType] || 16; // Default to 16 weeks
  return cropWeek >= 1 && cropWeek <= maxWeek;
}