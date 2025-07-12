import { calculationService } from '../../src/services/calculationService';
import { kcService } from '../../src/services/kcService';
import { et0Service } from '../../src/services/et0Service';
import { rainfallService } from '../../src/services/rainfallService';
import { ROSCalculationInput } from '../../src/types';

jest.mock('../../src/services/kcService');
jest.mock('../../src/services/et0Service');
jest.mock('../../src/services/rainfallService');

describe('CalculationService', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('calculateWaterDemand', () => {
    it('should calculate water demand correctly', async () => {
      // Mock dependencies
      (kcService.getCropDuration as jest.Mock).mockResolvedValue(17);
      (kcService.getKc as jest.Mock).mockResolvedValue(1.15);
      (et0Service.getET0 as jest.Mock).mockResolvedValue(4.0); // 4mm/day
      (rainfallService.getEffectiveRainfall as jest.Mock).mockResolvedValue({
        amount_mm: 2.0,
        amount_m3: 3200
      });

      const input: ROSCalculationInput = {
        cropType: 'ข้าว กข.(นาดำ)',
        plantings: [{
          plantingDate: new Date('2024-11-01'),
          areaRai: 1000
        }],
        calculationDate: new Date('2024-11-15'),
        calculationPeriod: 'daily',
        nonAgriculturalDemands: {
          domestic: 5000,
          industrial: 2000
        }
      };

      const result = await calculationService.calculateWaterDemand(input);

      expect(result).toBeDefined();
      expect(result.cropDetails.totalAreaRai).toBe(1000);
      expect(result.cropDetails.weightedKc).toBe(1.15);
      expect(result.cropDetails.et0).toBe(4.0);
      
      // Water requirement: (Kc * ET0) + percolation
      // (1.15 * 4.0) + 2.0 = 6.6 mm
      expect(result.waterRequirement.total_mm).toBeCloseTo(6.6, 1);
      
      // Net irrigation: Water requirement - effective rainfall
      expect(result.netIrrigation.amount_mm).toBeCloseTo(4.6, 1);
      
      // Non-agricultural demand
      expect(result.nonAgriculturalDemand_m3).toBe(7000);
    });

    it('should handle multiple plantings with area-weighted Kc', async () => {
      // Mock different Kc values for different growth stages
      (kcService.getCropDuration as jest.Mock).mockResolvedValue(17);
      (kcService.getKc as jest.Mock)
        .mockResolvedValueOnce(1.10) // Week 3
        .mockResolvedValueOnce(1.15); // Week 2
      
      (et0Service.getET0 as jest.Mock).mockResolvedValue(4.0);
      (rainfallService.getEffectiveRainfall as jest.Mock).mockResolvedValue({
        amount_mm: 2.0,
        amount_m3: 4800
      });

      const input: ROSCalculationInput = {
        cropType: 'ข้าว กข.(นาดำ)',
        plantings: [{
          plantingDate: new Date('2024-11-01'),
          areaRai: 1000
        }, {
          plantingDate: new Date('2024-11-08'),
          areaRai: 500
        }],
        calculationDate: new Date('2024-11-15'),
        calculationPeriod: 'daily'
      };

      const result = await calculationService.calculateWaterDemand(input);

      expect(result.cropDetails.totalAreaRai).toBe(1500);
      
      // Weighted Kc = (1000 * 1.10 + 500 * 1.15) / 1500 = 1.117
      expect(result.cropDetails.weightedKc).toBeCloseTo(1.117, 3);
    });

    it('should validate input parameters', async () => {
      const invalidInput = {
        cropType: '',
        plantings: [],
        calculationDate: new Date(),
        calculationPeriod: 'daily'
      } as ROSCalculationInput;

      await expect(calculationService.calculateWaterDemand(invalidInput))
        .rejects.toThrow('Crop type is required');
    });

    it('should use cache for repeated calculations', async () => {
      // Mock dependencies
      (kcService.getCropDuration as jest.Mock).mockResolvedValue(17);
      (kcService.getKc as jest.Mock).mockResolvedValue(1.15);
      (et0Service.getET0 as jest.Mock).mockResolvedValue(4.0);
      (rainfallService.getEffectiveRainfall as jest.Mock).mockResolvedValue({
        amount_mm: 2.0,
        amount_m3: 3200
      });

      const input: ROSCalculationInput = (global as any).testUtils.generateMockCalculationInput();

      // First call
      const result1 = await calculationService.calculateWaterDemand(input);
      
      // Second call (should use cache)
      const result2 = await calculationService.calculateWaterDemand(input);

      expect(result1).toEqual(result2);
      
      // Kc service should only be called once due to caching
      expect(kcService.getKc).toHaveBeenCalledTimes(1);
    });
  });

  describe('calculatePlantingDetails', () => {
    it('should skip plantings that have not started yet', async () => {
      (kcService.getCropDuration as jest.Mock).mockResolvedValue(17);
      
      const input: ROSCalculationInput = {
        cropType: 'ข้าว กข.(นาดำ)',
        plantings: [{
          plantingDate: new Date('2024-12-01'), // Future date
          areaRai: 1000
        }],
        calculationDate: new Date('2024-11-15'),
        calculationPeriod: 'daily'
      };

      const result = await calculationService.calculateWaterDemand(input);
      
      expect(result.cropDetails.totalAreaRai).toBe(0);
      expect(result.cropDetails.activeGrowthStages).toHaveLength(0);
    });

    it('should skip plantings that have already been harvested', async () => {
      (kcService.getCropDuration as jest.Mock).mockResolvedValue(17);
      
      const input: ROSCalculationInput = {
        cropType: 'ข้าว กข.(นาดำ)',
        plantings: [{
          plantingDate: new Date('2024-01-01'), // Very old planting
          areaRai: 1000
        }],
        calculationDate: new Date('2024-11-15'),
        calculationPeriod: 'daily'
      };

      const result = await calculationService.calculateWaterDemand(input);
      
      expect(result.cropDetails.totalAreaRai).toBe(0);
      expect(result.cropDetails.activeGrowthStages).toHaveLength(0);
    });
  });
});