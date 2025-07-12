import { logger } from '../utils/logger';
import { AppError } from '../middleware/errorHandler';
import { ET0Model } from '../models/et0Model';

export class ET0Service {
  /**
   * Get ET0 value for a specific date and period
   */
  async getET0(
    date: Date,
    period: 'daily' | 'weekly' | 'monthly'
  ): Promise<number> {
    try {
      const month = date.getMonth() + 1; // 1-12
      const year = date.getFullYear();

      // Try to get from database
      const et0Data = await ET0Model.findOne({
        month: month,
        year: year
      });

      let monthlyET0: number;

      if (et0Data) {
        monthlyET0 = et0Data.et0Value;
      } else {
        // Use default values
        monthlyET0 = this.getDefaultET0(month);
      }

      // Convert to requested period
      return this.convertET0ToPeriod(monthlyET0, period);
    } catch (error) {
      logger.error('Error getting ET0 value:', error);
      throw new AppError('Failed to retrieve ET0 value', 500);
    }
  }

  /**
   * Convert monthly ET0 to different periods
   */
  private convertET0ToPeriod(monthlyET0: number, period: 'daily' | 'weekly' | 'monthly'): number {
    switch (period) {
      case 'daily':
        return monthlyET0 / 30; // Average daily
      case 'weekly':
        return monthlyET0 / 4;  // As per Excel formula
      case 'monthly':
        return monthlyET0;
      default:
        return monthlyET0;
    }
  }

  /**
   * Get default ET0 values by month (mm/month)
   */
  private getDefaultET0(month: number): number {
    // Default ET0 values for Thailand (mm/month)
    const defaultET0: Record<number, number> = {
      1: 120,   // January
      2: 130,   // February
      3: 155,   // March
      4: 165,   // April
      5: 155,   // May
      6: 145,   // June
      7: 140,   // July
      8: 140,   // August
      9: 135,   // September
      10: 130,  // October
      11: 120,  // November
      12: 115   // December
    };

    return defaultET0[month] || 140;
  }

  /**
   * Import ET0 data from Excel structure
   */
  async importET0Data(data: Array<{
    location?: string;
    year: number;
    month: number;
    et0Value: number;
    source?: string;
  }>): Promise<void> {
    try {
      // Clear existing data for the year
      const years = [...new Set(data.map(d => d.year))];
      await ET0Model.deleteMany({ year: { $in: years } });

      // Insert new data
      await ET0Model.insertMany(data);
      
      logger.info(`Imported ${data.length} ET0 records`);
    } catch (error) {
      logger.error('Error importing ET0 data:', error);
      throw new AppError('Failed to import ET0 data', 500);
    }
  }

  /**
   * Calculate ET0 using Penman-Monteith (future enhancement)
   */
  async calculateET0PenmanMonteith(params: {
    temperature: number;
    humidity: number;
    windSpeed: number;
    solarRadiation: number;
    latitude: number;
    elevation: number;
    date: Date;
  }): Promise<number> {
    // This is a placeholder for future Penman-Monteith implementation
    // For now, return lookup value
    return this.getET0(params.date, 'daily');
  }

  /**
   * Get annual ET0 pattern
   */
  async getAnnualET0Pattern(year?: number): Promise<Array<{
    month: number;
    monthName: string;
    et0: number;
  }>> {
    const targetYear = year || new Date().getFullYear();
    
    try {
      const data = await ET0Model.find({ year: targetYear })
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
          et0: this.getDefaultET0(index + 1)
        }));
      }

      return data.map(d => ({
        month: d.month,
        monthName: monthNames[d.month - 1],
        et0: d.et0Value
      }));
    } catch (error) {
      logger.error('Error getting annual ET0 pattern:', error);
      throw new AppError('Failed to retrieve ET0 pattern', 500);
    }
  }
}

export const et0Service = new ET0Service();