const { AWDControlService } = require('../../src/services/awdControlService');

describe('AWDControlService', () => {
  let service;
  const mockConfig = {
    minWaterLevelCm: 5,
    maxWaterLevelCm: 15,
    dryingPeriodDays: 7
  };

  beforeEach(() => {
    service = new AWDControlService(mockConfig);
    // Reset any cached data
    service.lastIrrigationDates = new Map();
  });

  describe('evaluateAWDStatus', () => {
    it('should trigger irrigation when water level is below minimum', () => {
      const result = service.evaluateAWDStatus('SF01', 3);

      expect(result.action).toBe('ON');
      expect(result.reason).toBe('Water level below minimum threshold');
      expect(result.currentValue).toBe(3);
      expect(result.thresholds.min).toBe(5);
      expect(result.thresholds.max).toBe(15);
    });

    it('should stop irrigation when water level reaches maximum', () => {
      const result = service.evaluateAWDStatus('SF02', 16);

      expect(result.action).toBe('OFF');
      expect(result.reason).toBe('Water level at or above maximum threshold');
      expect(result.currentValue).toBe(16);
    });

    it('should maintain current state when water level is in acceptable range', () => {
      const result = service.evaluateAWDStatus('SF03', 10);

      expect(result.action).toBe('MAINTAIN');
      expect(result.reason).toBe('Water level within acceptable range');
      expect(result.currentValue).toBe(10);
    });

    it('should use override thresholds when provided', () => {
      const overrides = {
        minWaterLevelCm: 8,
        maxWaterLevelCm: 20
      };

      const result = service.evaluateAWDStatus('SF04', 7, overrides);

      expect(result.action).toBe('ON');
      expect(result.reason).toBe('Water level below minimum threshold');
      expect(result.thresholds.min).toBe(8);
      expect(result.thresholds.max).toBe(20);
    });

    it('should handle multiple plots with different override thresholds without interference', () => {
      const plot1Overrides = {
        minWaterLevelCm: 3,
        maxWaterLevelCm: 10
      };
      const plot2Overrides = {
        minWaterLevelCm: 8,
        maxWaterLevelCm: 20
      };

      const result1 = service.evaluateAWDStatus('PLOT1', 5, plot1Overrides);
      const result2 = service.evaluateAWDStatus('PLOT2', 5, plot2Overrides);

      expect(result1.action).toBe('MAINTAIN');
      expect(result1.thresholds.min).toBe(3);
      expect(result1.thresholds.max).toBe(10);

      expect(result2.action).toBe('ON');
      expect(result2.thresholds.min).toBe(8);
      expect(result2.thresholds.max).toBe(20);
    });

    it('should fall back to config when no overrides provided', () => {
      const result = service.evaluateAWDStatus('SF05', 10);

      expect(result.thresholds.min).toBe(5);
      expect(result.thresholds.max).toBe(15);
    });
  });

  describe('calculateAWDTarget', () => {
    it('should calculate target level based on current deficit', () => {
      const target = service.calculateAWDTarget('SF01', 2);
      expect(target).toBe(15); // Should target max level
    });

    it('should not exceed maximum water level', () => {
      const target = service.calculateAWDTarget('SF02', 14);
      expect(target).toBe(15);
    });

    it('should calculate proportional target for moderate deficit', () => {
      const target = service.calculateAWDTarget('SF03', 8);
      // With 8cm current and 5cm min, we're 3cm above minimum
      // Should add some water but not to max
      expect(target).toBeGreaterThan(8);
      expect(target).toBeLessThanOrEqual(15);
    });

    it('should respect override max threshold', () => {
      const overrides = {
        minWaterLevelCm: 3,
        maxWaterLevelCm: 25
      };

      const target = service.calculateAWDTarget('SF04', 10, overrides);
      expect(target).toBe(25);
    });

    it('should use different override max for different plots', () => {
      const overrides1 = { minWaterLevelCm: 5, maxWaterLevelCm: 18 };
      const overrides2 = { minWaterLevelCm: 3, maxWaterLevelCm: 22 };

      const target1 = service.calculateAWDTarget('PLOT1', 8, overrides1);
      const target2 = service.calculateAWDTarget('PLOT2', 8, overrides2);

      expect(target1).toBe(18);
      expect(target2).toBe(22);
    });

    it('should fall back to config max when no overrides', () => {
      const target = service.calculateAWDTarget('SF05', 8);
      expect(target).toBe(15); // config max
    });
  });

  describe('shouldStartDryingCycle', () => {
    it('should start drying cycle after specified period', () => {
      const lastIrrigation = new Date();
      lastIrrigation.setDate(lastIrrigation.getDate() - 8); // 8 days ago

      service.lastIrrigationDates.set('SF01', lastIrrigation);

      const shouldDry = service.shouldStartDryingCycle('SF01', 12);
      expect(shouldDry).toBe(true);
    });

    it('should not start drying cycle too soon', () => {
      const lastIrrigation = new Date();
      lastIrrigation.setDate(lastIrrigation.getDate() - 3); // 3 days ago

      service.lastIrrigationDates.set('SF02', lastIrrigation);

      const shouldDry = service.shouldStartDryingCycle('SF02', 12);
      expect(shouldDry).toBe(false);
    });

    it('should not dry if water level is already low', () => {
      const lastIrrigation = new Date();
      lastIrrigation.setDate(lastIrrigation.getDate() - 10); // 10 days ago

      service.lastIrrigationDates.set('SF03', lastIrrigation);

      const shouldDry = service.shouldStartDryingCycle('SF03', 6);
      expect(shouldDry).toBe(false);
    });

    it('should respect override min threshold for low water check', () => {
      const lastIrrigation = new Date();
      lastIrrigation.setDate(lastIrrigation.getDate() - 10); // 10 days ago

      service.lastIrrigationDates.set('SF04', lastIrrigation);

      const overrides = {
        minWaterLevelCm: 10,
        maxWaterLevelCm: 25
      };

      // 12cm > 10cm + 2 = should allow drying
      const shouldDry1 = service.shouldStartDryingCycle('SF04', 12, overrides);
      expect(shouldDry1).toBe(false); // Still too close to min

      // 14cm > 10cm + 2 = should allow drying
      const shouldDry2 = service.shouldStartDryingCycle('SF04', 14, overrides);
      expect(shouldDry2).toBe(true); // Enough buffer above min

      // 11cm <= 10cm + 2 = too low for drying
      const shouldDry3 = service.shouldStartDryingCycle('SF04', 11, overrides);
      expect(shouldDry3).toBe(false); // Too close to min
    });

    it('should use different override min for different plots', () => {
      const lastIrrigation = new Date();
      lastIrrigation.setDate(lastIrrigation.getDate() - 10);

      service.lastIrrigationDates.set('PLOT1', lastIrrigation);
      service.lastIrrigationDates.set('PLOT2', lastIrrigation);

      const overrides1 = { minWaterLevelCm: 3, maxWaterLevelCm: 15 };
      const overrides2 = { minWaterLevelCm: 8, maxWaterLevelCm: 20 };

      // Same water level (7cm), different thresholds
      const shouldDry1 = service.shouldStartDryingCycle('PLOT1', 7, overrides1);
      const shouldDry2 = service.shouldStartDryingCycle('PLOT2', 7, overrides2);

      expect(shouldDry1).toBe(true); // 7cm > 3cm + 2 = ok to dry
      expect(shouldDry2).toBe(false); // 7cm <= 8cm + 2 = too low
    });

    it('should fall back to config when no overrides provided', () => {
      const lastIrrigation = new Date();
      lastIrrigation.setDate(lastIrrigation.getDate() - 10);

      service.lastIrrigationDates.set('SF05', lastIrrigation);

      // With config min=5, 8cm > 5cm + 2 = should allow
      const shouldDry = service.shouldStartDryingCycle('SF05', 8);
      expect(shouldDry).toBe(true);
    });
  });

  describe('calculateFlowRate', () => {
    it('should calculate flow rate from water level changes', () => {
      const readings = [
        { timestamp: new Date('2025-01-01T10:00:00'), waterLevelCm: 5 },
        { timestamp: new Date('2025-01-01T10:10:00'), waterLevelCm: 7 }
      ];

      const flowRate = service.calculateFlowRate(readings, 2500); // 2.5 rai = 2500 m²

      // 2cm rise in 10 minutes over 2500m² = 50m³ = 50,000L in 10min = 5000 L/min
      expect(flowRate).toBe(5000);
    });

    it('should return 0 for insufficient readings', () => {
      const readings = [
        { timestamp: new Date(), waterLevelCm: 5 }
      ];

      const flowRate = service.calculateFlowRate(readings, 2500);
      expect(flowRate).toBe(0);
    });
  });

  describe('getAWDPhase', () => {
    it('should identify flooding phase', () => {
      const phase = service.getAWDPhase(3, true);
      expect(phase).toBe('flooding');
    });

    it('should identify flooded phase', () => {
      const phase = service.getAWDPhase(12, false);
      expect(phase).toBe('flooded');
    });

    it('should identify drying phase', () => {
      service.lastIrrigationDates.set('SF01', new Date('2025-01-01'));
      const phase = service.getAWDPhase(8, false, 'SF01');
      expect(phase).toBe('drying');
    });

    it('should identify dried phase', () => {
      const phase = service.getAWDPhase(4, false);
      expect(phase).toBe('dried');
    });

    it('should use override min threshold to determine dried phase', () => {
      const overrides = {
        minWaterLevelCm: 10,
        maxWaterLevelCm: 25
      };

      // 8cm < 10cm (override min) = dried
      const phase1 = service.getAWDPhase(8, false, null, overrides);
      expect(phase1).toBe('dried');

      // 12cm > 10cm (override min) but no irrigation = drying
      const phase2 = service.getAWDPhase(12, false, null, overrides);
      expect(phase2).toBe('drying');
    });

    it('should use override min threshold to determine flooded phase', () => {
      const overrides = {
        minWaterLevelCm: 2,
        maxWaterLevelCm: 10
      };

      // 8cm > 2cm + 5 = flooded (using override min)
      const phase = service.getAWDPhase(8, false, null, overrides);
      expect(phase).toBe('flooded');
    });

    it('should fall back to config when no overrides provided', () => {
      // With config min=5, 8cm > 5cm = drying (no recent irrigation)
      const phase = service.getAWDPhase(8, false);
      expect(phase).toBe('drying');
    });
  });

  describe('edge cases', () => {
    it('should handle negative water levels', () => {
      const result = service.evaluateAWDStatus('SF04', -5);
      expect(result.action).toBe('ON');
      expect(result.metadata.warning).toBe('Negative water level reading');
    });

    it('should handle extreme water levels', () => {
      const result = service.evaluateAWDStatus('SF05', 100);
      expect(result.action).toBe('OFF');
      expect(result.metadata.warning).toBe('Unusually high water level');
    });
  });
});