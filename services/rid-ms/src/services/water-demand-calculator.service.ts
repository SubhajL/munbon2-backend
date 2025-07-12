import { logger } from '../utils/logger';
import { ParcelData, WaterDemand, WaterDemandRequest, WaterDemandResponse, ParcelWaterDemand } from '../types';
import { DatabaseService } from './database.service';
import { KafkaService } from './kafka.service';
import { v4 as uuidv4 } from 'uuid';

interface CropCoefficients {
  [cropType: string]: {
    initial: number;
    mid: number;
    late: number;
  };
}

interface IrrigationEfficiencies {
  [method: string]: number;
}

export class WaterDemandCalculatorService {
  private static instance: WaterDemandCalculatorService;
  private databaseService: DatabaseService;
  private kafkaService: KafkaService;

  // Crop coefficients (Kc) for different crops and growth stages
  private readonly cropCoefficients: CropCoefficients = {
    'RICE': { initial: 1.05, mid: 1.20, late: 0.90 },
    'CORN': { initial: 0.30, mid: 1.20, late: 0.60 },
    'SUGARCANE': { initial: 0.40, mid: 1.25, late: 0.75 },
    'CASSAVA': { initial: 0.30, mid: 1.10, late: 0.50 },
    'VEGETABLES': { initial: 0.70, mid: 1.05, late: 0.95 },
    'DEFAULT': { initial: 0.50, mid: 1.00, late: 0.75 },
  };

  // Irrigation efficiency by method
  private readonly irrigationEfficiencies: IrrigationEfficiencies = {
    'RID-MS': 0.65, // Traditional surface irrigation
    'ROS': 0.75,    // Improved management
    'AWD': 0.85,    // Alternate Wet and Dry - most efficient
  };

  // Reference evapotranspiration (ET0) by month for Thailand (mm/day)
  private readonly monthlyET0 = [
    4.0, // January
    4.5, // February
    5.0, // March
    5.5, // April
    5.0, // May
    4.5, // June
    4.0, // July
    4.0, // August
    4.0, // September
    4.0, // October
    3.5, // November
    3.5, // December
  ];

  private constructor() {
    this.databaseService = DatabaseService.getInstance();
    this.kafkaService = KafkaService.getInstance();
  }

  public static getInstance(): WaterDemandCalculatorService {
    if (!WaterDemandCalculatorService.instance) {
      WaterDemandCalculatorService.instance = new WaterDemandCalculatorService();
    }
    return WaterDemandCalculatorService.instance;
  }

  /**
   * Calculate water demand for parcels
   */
  public async calculateWaterDemand(request: WaterDemandRequest): Promise<WaterDemandResponse> {
    const requestId = uuidv4();
    const parcelWaterDemands: ParcelWaterDemand[] = [];

    try {
      // Fetch parcels from database
      const parcels = await this.databaseService.getParcelsByIds(request.parcels);

      // Calculate water demand for each parcel
      for (const parcel of parcels) {
        const waterDemand = await this.calculateParcelWaterDemand(
          parcel,
          request.method,
          request.parameters
        );

        parcelWaterDemands.push({
          parcelId: parcel.parcelId,
          area: parcel.area,
          method: request.method,
          waterDemand,
        });

        // Update parcel with new water demand
        parcel.waterDemandMethod = request.method;
        parcel.waterDemand = waterDemand;
        await this.databaseService.updateParcel(parcel);
      }

      // Calculate totals
      const totalDailyDemand = parcelWaterDemands.reduce(
        (sum, p) => sum + p.waterDemand.dailyDemand,
        0
      );
      const totalWeeklyDemand = parcelWaterDemands.reduce(
        (sum, p) => sum + p.waterDemand.weeklyDemand,
        0
      );
      const totalMonthlyDemand = parcelWaterDemands.reduce(
        (sum, p) => sum + p.waterDemand.monthlyDemand,
        0
      );

      // Publish water demand update event
      await this.kafkaService.publishWaterDemandUpdated({
        requestId,
        parcelsCount: parcelWaterDemands.length,
        totalDailyDemand,
        method: request.method,
        calculatedAt: new Date(),
      });

      return {
        requestId,
        parcels: parcelWaterDemands,
        totalDailyDemand,
        totalWeeklyDemand,
        totalMonthlyDemand,
        calculatedAt: new Date(),
      };

    } catch (error) {
      logger.error('Water demand calculation failed:', error);
      throw error;
    }
  }

  /**
   * Calculate water demand for a single parcel
   */
  private async calculateParcelWaterDemand(
    parcel: ParcelData,
    method: 'RID-MS' | 'ROS' | 'AWD',
    parameters?: any
  ): Promise<WaterDemand> {
    // Get crop coefficient
    const cropType = parameters?.cropType || parcel.cropType || 'DEFAULT';
    const cropCoeff = this.getCropCoefficient(cropType, parcel.plantingDate);

    // Get reference ET for current month
    const currentMonth = new Date().getMonth();
    const et0 = this.monthlyET0[currentMonth];

    // Get irrigation efficiency
    const efficiency = parameters?.irrigationEfficiency || 
                      this.irrigationEfficiencies[method];

    // Calculate crop water requirement (mm/day)
    const cropET = et0 * cropCoeff;

    // Convert to volume (m³/day) considering area and efficiency
    // Formula: Volume = (ET × Area) / (Efficiency × 1000)
    // Note: Area is in m², ET in mm/day, result in m³/day
    const dailyDemand = (cropET * parcel.area) / (efficiency * 1000);

    // Calculate different time periods
    const weeklyDemand = dailyDemand * 7;
    const monthlyDemand = dailyDemand * 30;
    const seasonalDemand = dailyDemand * 120; // Assume 4-month growing season

    // Special adjustments for AWD method
    let adjustedDailyDemand = dailyDemand;
    if (method === 'AWD') {
      // AWD reduces water by 30% during drying periods
      adjustedDailyDemand = dailyDemand * 0.7;
    }

    return {
      method,
      dailyDemand: adjustedDailyDemand,
      weeklyDemand: adjustedDailyDemand * 7,
      monthlyDemand: adjustedDailyDemand * 30,
      seasonalDemand: adjustedDailyDemand * 120,
      cropCoefficient: cropCoeff,
      referenceEvapotranspiration: et0,
      irrigationEfficiency: efficiency,
      lastCalculated: new Date(),
      parameters: {
        cropType,
        area: parcel.area,
        method,
        ...parameters,
      },
    };
  }

  /**
   * Get crop coefficient based on growth stage
   */
  private getCropCoefficient(cropType: string, plantingDate?: Date): number {
    const coefficients = this.cropCoefficients[cropType.toUpperCase()] || 
                        this.cropCoefficients['DEFAULT'];

    if (!plantingDate) {
      // Use mid-season coefficient if no planting date
      return coefficients.mid;
    }

    // Calculate days since planting
    const daysSincePlanting = Math.floor(
      (new Date().getTime() - plantingDate.getTime()) / (1000 * 60 * 60 * 24)
    );

    // Determine growth stage (simplified)
    if (daysSincePlanting < 30) {
      return coefficients.initial;
    } else if (daysSincePlanting < 90) {
      return coefficients.mid;
    } else {
      return coefficients.late;
    }
  }

  /**
   * Calculate water demand for entire zone
   */
  public async calculateZoneWaterDemand(zone: string): Promise<any> {
    const parcels = await this.databaseService.getParcelsByZone(zone);
    
    const statistics = {
      zone,
      totalArea: 0,
      parcelCount: parcels.length,
      waterDemandByMethod: {
        'RID-MS': { count: 0, dailyDemand: 0 },
        'ROS': { count: 0, dailyDemand: 0 },
        'AWD': { count: 0, dailyDemand: 0 },
      },
      cropTypes: {} as Record<string, number>,
      totalDailyDemand: 0,
      totalWeeklyDemand: 0,
      totalMonthlyDemand: 0,
    };

    for (const parcel of parcels) {
      statistics.totalArea += parcel.area;

      // Count by method
      const method = parcel.waterDemandMethod;
      statistics.waterDemandByMethod[method].count++;

      // Calculate water demand if not already calculated
      if (!parcel.waterDemand) {
        parcel.waterDemand = await this.calculateParcelWaterDemand(
          parcel,
          method,
          {}
        );
      }

      statistics.waterDemandByMethod[method].dailyDemand += parcel.waterDemand.dailyDemand;
      statistics.totalDailyDemand += parcel.waterDemand.dailyDemand;
      statistics.totalWeeklyDemand += parcel.waterDemand.weeklyDemand;
      statistics.totalMonthlyDemand += parcel.waterDemand.monthlyDemand;

      // Count crop types
      const cropType = parcel.cropType || 'UNKNOWN';
      statistics.cropTypes[cropType] = (statistics.cropTypes[cropType] || 0) + 1;
    }

    return statistics;
  }

  /**
   * Update water demand for all parcels (scheduled job)
   */
  public async updateAllWaterDemands(): Promise<void> {
    logger.info('Starting scheduled water demand update');

    try {
      const parcels = await this.databaseService.getAllParcels();
      let updated = 0;

      for (const parcel of parcels) {
        try {
          const waterDemand = await this.calculateParcelWaterDemand(
            parcel,
            parcel.waterDemandMethod,
            {}
          );

          parcel.waterDemand = waterDemand;
          await this.databaseService.updateParcel(parcel);
          updated++;

          // Process in batches to avoid overwhelming the system
          if (updated % 100 === 0) {
            logger.info(`Updated water demand for ${updated} parcels`);
          }
        } catch (error) {
          logger.error(`Failed to update water demand for parcel ${parcel.parcelId}:`, error);
        }
      }

      logger.info(`Completed water demand update. Updated ${updated} parcels`);

      // Publish completion event
      await this.kafkaService.publishWaterDemandUpdated({
        requestId: 'scheduled-update',
        parcelsCount: updated,
        totalDailyDemand: 0, // Would need to calculate
        method: 'MIXED',
        calculatedAt: new Date(),
      });

    } catch (error) {
      logger.error('Failed to update water demands:', error);
      throw error;
    }
  }
}