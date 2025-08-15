import { timescalePool, postgisPool } from '../config/database';
import { WaterRequirementValidation } from '../models/sensor-zone-mapping';
import { sensorZoneMappingService } from './sensor-zone-mapping.service';
import dayjs from 'dayjs';

interface CropWaterRequirement {
  cropType: string;
  cropWeek: number;
  requiredDepthCm: number;
  optimalMoisturePct: {
    surface: { min: number; max: number };
    deep: { min: number; max: number };
  };
}

export class WaterValidationService {
  // Simplified crop water requirements (in reality, would come from ROS service)
  private readonly cropRequirements: Record<string, CropWaterRequirement[]> = {
    'rice': [
      { cropType: 'rice', cropWeek: 1, requiredDepthCm: 5, optimalMoisturePct: { surface: { min: 80, max: 100 }, deep: { min: 70, max: 90 } } },
      { cropType: 'rice', cropWeek: 2, requiredDepthCm: 10, optimalMoisturePct: { surface: { min: 80, max: 100 }, deep: { min: 70, max: 90 } } },
      { cropType: 'rice', cropWeek: 3, requiredDepthCm: 15, optimalMoisturePct: { surface: { min: 80, max: 100 }, deep: { min: 70, max: 90 } } },
      // ... more weeks
    ],
    'sugarcane': [
      { cropType: 'sugarcane', cropWeek: 1, requiredDepthCm: 3, optimalMoisturePct: { surface: { min: 60, max: 80 }, deep: { min: 50, max: 70 } } },
      { cropType: 'sugarcane', cropWeek: 2, requiredDepthCm: 5, optimalMoisturePct: { surface: { min: 60, max: 80 }, deep: { min: 50, max: 70 } } },
      // ... more weeks
    ]
  };

  /**
   * Validate water levels in a zone against crop requirements
   */
  async validateZoneWaterLevel(
    zoneCode: string,
    cropType: string,
    cropWeek: number
  ): Promise<WaterRequirementValidation> {
    // Get zone sensor data
    const zoneStatus = await sensorZoneMappingService.getSensorsByZone(zoneCode);
    
    // Get crop requirements
    const requirements = this.getCropRequirement(cropType, cropWeek);
    if (!requirements) {
      throw new Error(`No water requirements found for ${cropType} week ${cropWeek}`);
    }

    // Calculate actual water level (average of all sensors in zone)
    const actualWaterLevel = zoneStatus.averageWaterLevel || 0;
    
    // Calculate moisture status
    const avgSurfaceMoisture = zoneStatus.moistureSensors.length > 0
      ? zoneStatus.moistureSensors.reduce((sum, s) => sum + s.moistureSurfacePct, 0) / zoneStatus.moistureSensors.length
      : 0;
    
    const avgDeepMoisture = zoneStatus.moistureSensors.length > 0
      ? zoneStatus.moistureSensors.reduce((sum, s) => sum + s.moistureDeepPct, 0) / zoneStatus.moistureSensors.length
      : 0;

    // Determine validation status
    let validationStatus: 'sufficient' | 'deficit' | 'excess' = 'sufficient';
    let deficitCm: number | undefined;
    let excessCm: number | undefined;
    
    if (actualWaterLevel < requirements.requiredDepthCm) {
      validationStatus = 'deficit';
      deficitCm = requirements.requiredDepthCm - actualWaterLevel;
    } else if (actualWaterLevel > requirements.requiredDepthCm * 1.5) {
      validationStatus = 'excess';
      excessCm = actualWaterLevel - (requirements.requiredDepthCm * 1.5);
    }

    // Check moisture status
    const moistureOptimal = 
      avgSurfaceMoisture >= requirements.optimalMoisturePct.surface.min &&
      avgSurfaceMoisture <= requirements.optimalMoisturePct.surface.max &&
      avgDeepMoisture >= requirements.optimalMoisturePct.deep.min &&
      avgDeepMoisture <= requirements.optimalMoisturePct.deep.max;

    // Generate recommendations
    const recommendations = this.generateRecommendations(
      validationStatus,
      deficitCm,
      excessCm,
      moistureOptimal,
      zoneStatus.totalSensors
    );

    return {
      zoneCode,
      cropType,
      cropWeek,
      requiredWaterLevelCm: requirements.requiredDepthCm,
      actualWaterLevelCm: actualWaterLevel,
      moistureStatus: {
        surface: avgSurfaceMoisture,
        deep: avgDeepMoisture,
        optimal: moistureOptimal
      },
      validationStatus,
      deficitCm,
      excessCm,
      recommendations,
      timestamp: new Date()
    };
  }

  /**
   * Get historical water validation data
   */
  async getHistoricalValidation(
    zoneCode: string,
    startDate: Date,
    endDate: Date
  ): Promise<any[]> {
    // This would query stored validation results
    // For now, returning empty array as placeholder
    return [];
  }

  /**
   * Validate water across multiple zones
   */
  async validateMultipleZones(
    zoneCodes: string[],
    cropType: string,
    cropWeek: number
  ): Promise<WaterRequirementValidation[]> {
    const validations = await Promise.all(
      zoneCodes.map(zoneCode => 
        this.validateZoneWaterLevel(zoneCode, cropType, cropWeek)
      )
    );
    
    return validations;
  }

  /**
   * Get crop water requirement
   */
  private getCropRequirement(
    cropType: string, 
    cropWeek: number
  ): CropWaterRequirement | undefined {
    const cropReqs = this.cropRequirements[cropType.toLowerCase()];
    if (!cropReqs) return undefined;
    
    return cropReqs.find(req => req.cropWeek === cropWeek);
  }

  /**
   * Generate recommendations based on validation results
   */
  private generateRecommendations(
    status: 'sufficient' | 'deficit' | 'excess',
    deficitCm?: number,
    excessCm?: number,
    moistureOptimal?: boolean,
    sensorCount?: number
  ): string[] {
    const recommendations: string[] = [];

    // Water level recommendations
    if (status === 'deficit' && deficitCm) {
      recommendations.push(`Increase water supply by ${deficitCm.toFixed(1)} cm`);
      recommendations.push('Check upstream gate operations');
      if (deficitCm > 10) {
        recommendations.push('URGENT: Critical water shortage detected');
      }
    } else if (status === 'excess' && excessCm) {
      recommendations.push(`Reduce water supply by ${excessCm.toFixed(1)} cm`);
      recommendations.push('Consider opening drainage gates');
      if (excessCm > 20) {
        recommendations.push('WARNING: Risk of flooding');
      }
    }

    // Moisture recommendations
    if (moistureOptimal === false) {
      recommendations.push('Soil moisture levels are not optimal');
      recommendations.push('Adjust irrigation schedule');
    }

    // Sensor coverage recommendations
    if (sensorCount === 0 || sensorCount === undefined) {
      recommendations.push('No sensors in this zone - deploy mobile sensors for validation');
    } else if (sensorCount < 2) {
      recommendations.push('Limited sensor coverage - consider deploying additional sensors');
    }

    return recommendations;
  }

  /**
   * Get zones requiring immediate attention
   */
  async getZonesRequiringAttention(cropType: string, cropWeek: number): Promise<any[]> {
    // Get all active zones
    const zonesQuery = `
      SELECT DISTINCT zone_code 
      FROM gis.irrigation_zones 
      WHERE zone_type = 'irrigation'
    `;
    const zonesResult = await postgisPool.query(zonesQuery);
    
    const validations = await this.validateMultipleZones(
      zonesResult.rows.map(r => r.zone_code),
      cropType,
      cropWeek
    );

    // Filter zones with deficit or excess
    return validations.filter(v => v.validationStatus !== 'sufficient')
      .sort((a, b) => {
        // Prioritize by deficit amount
        const aDeficit = a.deficitCm || 0;
        const bDeficit = b.deficitCm || 0;
        return bDeficit - aDeficit;
      });
  }
}

export const waterValidationService = new WaterValidationService();