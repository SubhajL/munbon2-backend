import { logger } from '../utils/logger';
import { AppError } from '../middleware/errorHandler';
import { RainfallModel } from '../models/rainfallModel';

export class RainfallService {
  private readonly RAI_TO_M2 = 1600;

  /**
   * Get effective rainfall for a specific date and area
   */
  async getEffectiveRainfall(
    date: Date,
    period: 'daily' | 'weekly' | 'monthly',
    areaRai: number
  ): Promise<{
    amount_mm: number;
    amount_m3: number;
  }> {
    try {
      const month = date.getMonth() + 1;
      const year = date.getFullYear();

      // Get rainfall data
      const rainfallData = await RainfallModel.findOne({
        month: month,
        year: year
      });

      let effectiveRainfall_mm: number;

      if (rainfallData) {
        effectiveRainfall_mm = rainfallData.effectiveRainfall;
      } else {
        // Use default values
        effectiveRainfall_mm = this.getDefaultEffectiveRainfall(month);
      }

      // Convert to requested period
      const periodRainfall_mm = this.convertRainfallToPeriod(effectiveRainfall_mm, period);

      // Convert to m³
      // Formula from Excel: (mm/1000) * area_rai * 1600 * days
      const daysInPeriod = period === 'daily' ? 1 : period === 'weekly' ? 7 : 30;
      const amount_m3 = (periodRainfall_mm / 1000) * areaRai * this.RAI_TO_M2 * daysInPeriod;

      return {
        amount_mm: periodRainfall_mm,
        amount_m3: amount_m3
      };
    } catch (error) {
      logger.error('Error getting effective rainfall:', error);
      throw new AppError('Failed to retrieve rainfall data', 500);
    }
  }

  /**
   * Convert monthly rainfall to different periods
   */
  private convertRainfallToPeriod(
    monthlyRainfall: number,
    period: 'daily' | 'weekly' | 'monthly'
  ): number {
    switch (period) {
      case 'daily':
        return monthlyRainfall / 30;
      case 'weekly':
        return monthlyRainfall / 4; // Weekly average
      case 'monthly':
        return monthlyRainfall;
      default:
        return monthlyRainfall;
    }
  }

  /**
   * Get default effective rainfall by month (mm)
   */
  private getDefaultEffectiveRainfall(month: number): number {
    // Default effective rainfall for paddy in Thailand (mm/month)
    const defaultRainfall: Record<number, number> = {
      1: 10,    // January - Dry season
      2: 15,    // February
      3: 30,    // March
      4: 80,    // April - Start of rainy season
      5: 150,   // May
      6: 180,   // June
      7: 200,   // July - Peak rainy season
      8: 210,   // August
      9: 180,   // September
      10: 100,  // October
      11: 30,   // November
      12: 15    // December
    };

    return defaultRainfall[month] || 50;
  }

  /**
   * Import rainfall data from Excel
   */
  async importRainfallData(data: Array<{
    location?: string;
    year: number;
    month: number;
    totalRainfall: number;
    effectiveRainfall: number;
    numberOfRainyDays?: number;
  }>): Promise<void> {
    try {
      // Clear existing data for the years
      const years = [...new Set(data.map(d => d.year))];
      await RainfallModel.deleteMany({ year: { $in: years } });

      // Insert new data
      await RainfallModel.insertMany(data);
      
      logger.info(`Imported ${data.length} rainfall records`);
    } catch (error) {
      logger.error('Error importing rainfall data:', error);
      throw new AppError('Failed to import rainfall data', 500);
    }
  }

  /**
   * Calculate effective rainfall from total rainfall
   * Using FAO method for paddy fields
   */
  calculateEffectiveRainfall(totalRainfall: number): number {
    // FAO method for paddy fields
    // Effective rainfall = 0.8 * (P - 5) for P > 75 mm/month
    // Effective rainfall = 0.6 * P for P <= 75 mm/month
    
    if (totalRainfall > 75) {
      return 0.8 * (totalRainfall - 5);
    } else {
      return 0.6 * totalRainfall;
    }
  }

  /**
   * Get annual rainfall pattern
   */
  async getAnnualRainfallPattern(year?: number): Promise<Array<{
    month: number;
    monthName: string;
    totalRainfall: number;
    effectiveRainfall: number;
  }>> {
    const targetYear = year || new Date().getFullYear();
    
    try {
      const data = await RainfallModel.find({ year: targetYear })
        .sort({ month: 1 });

      const monthNames = [
        'January', 'February', 'March', 'April', 'May', 'June',
        'July', 'August', 'September', 'October', 'November', 'December'
      ];

      if (data.length === 0) {
        // Return default pattern
        return monthNames.map((name, index) => ({
          month: index + 1,
          monthName: name,
          totalRainfall: this.getDefaultTotalRainfall(index + 1),
          effectiveRainfall: this.getDefaultEffectiveRainfall(index + 1)
        }));
      }

      return data.map(d => ({
        month: d.month,
        monthName: monthNames[d.month - 1],
        totalRainfall: d.totalRainfall,
        effectiveRainfall: d.effectiveRainfall
      }));
    } catch (error) {
      logger.error('Error getting annual rainfall pattern:', error);
      throw new AppError('Failed to retrieve rainfall pattern', 500);
    }
  }

  /**
   * Get default total rainfall (for reference)
   */
  private getDefaultTotalRainfall(month: number): number {
    // Typical total rainfall for Thailand (mm/month)
    const defaultTotal: Record<number, number> = {
      1: 15,    // January
      2: 25,    // February
      3: 50,    // March
      4: 125,   // April
      5: 225,   // May
      6: 275,   // June
      7: 300,   // July
      8: 315,   // August
      9: 275,   // September
      10: 150,  // October
      11: 45,   // November
      12: 20    // December
    };

    return defaultTotal[month] || 100;
  }
}

export const rainfallService = new RainfallService();