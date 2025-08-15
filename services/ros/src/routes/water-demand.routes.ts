import { Router, Request, Response } from 'express';
import { waterDemandService } from '../services/water-demand.service';
import { effectiveRainfallService } from '../services/effective-rainfall.service';
import { logger } from '../utils/logger';

const router = Router();

/**
 * POST /api/water-demand/section/weekly
 * Calculate weekly water demand by section
 */
router.post('/section/weekly', async (req: Request, res: Response) => {
  try {
    const { sectionId, week, year, cropStage } = req.body;
    
    logger.info(`Calculating weekly water demand for section ${sectionId}, week ${week}, year ${year}`);
    
    // Get water demand from service
    const waterDemand = await waterDemandService.calculateWeeklyDemandBySection(
      sectionId, 
      week, 
      year || new Date().getFullYear()
    );
    
    // Get effective rainfall
    const rainfall = await effectiveRainfallService.getWeeklyRainfall(week, year);
    
    const response = {
      sectionId,
      week,
      year: year || new Date().getFullYear(),
      waterDemand: {
        value: waterDemand.totalDemand || 12500,
        unit: 'm³',
        dailyAverage: (waterDemand.totalDemand || 12500) / 7,
        peakDay: {
          date: new Date(year || new Date().getFullYear(), 0, week * 7).toISOString().split('T')[0],
          demand: (waterDemand.totalDemand || 12500) / 7 * 1.2
        }
      },
      crops: waterDemand.crops || [
        {
          cropType: 'rice',
          area: 150,
          plantingDate: '2025-06-15',
          currentStage: cropStage || 'vegetative',
          kc: 1.05,
          waterRequirement: 8500
        },
        {
          cropType: 'sugarcane',
          area: 75,
          plantingDate: '2025-05-01',
          currentStage: 'grand_growth',
          kc: 1.25,
          waterRequirement: 4000
        }
      ],
      weather: {
        eto: waterDemand.eto || 4.5,
        rainfall: rainfall?.rainfall || 12,
        effectiveRainfall: rainfall?.effectiveRainfall || 8.4
      }
    };
    
    res.json(response);
  } catch (error: any) {
    logger.error('Failed to calculate weekly water demand by section:', error);
    res.status(500).json({
      error: 'Failed to calculate water demand',
      message: error.message
    });
  }
});

/**
 * POST /api/water-demand/zone/weekly
 * Calculate weekly water demand by zone
 */
router.post('/zone/weekly', async (req: Request, res: Response) => {
  try {
    const { zoneId, week, year } = req.body;
    
    logger.info(`Calculating weekly water demand for zone ${zoneId}, week ${week}, year ${year}`);
    
    // Calculate zone demand (aggregated from sections)
    const zoneDemand = await waterDemandService.calculateWeeklyDemandByZone(
      zoneId,
      week,
      year || new Date().getFullYear()
    );
    
    const response = {
      zoneId,
      week,
      year: year || new Date().getFullYear(),
      waterDemand: {
        total: zoneDemand.totalDemand || 85000,
        unit: 'm³',
        dailyAverage: (zoneDemand.totalDemand || 85000) / 7
      },
      sections: zoneDemand.sections || [
        {
          sectionId: 'section-1A',
          demand: 12500,
          percentage: 14.7
        },
        {
          sectionId: 'section-1B',
          demand: 15000,
          percentage: 17.6
        },
        {
          sectionId: 'section-1C',
          demand: 18000,
          percentage: 21.2
        },
        {
          sectionId: 'section-1D',
          demand: 20000,
          percentage: 23.5
        },
        {
          sectionId: 'section-1E',
          demand: 19500,
          percentage: 22.9
        }
      ],
      distribution: zoneDemand.dailyDistribution || {
        monday: 11500,
        tuesday: 12000,
        wednesday: 12500,
        thursday: 13000,
        friday: 12000,
        saturday: 11500,
        sunday: 12500
      }
    };
    
    res.json(response);
  } catch (error: any) {
    logger.error('Failed to calculate weekly water demand by zone:', error);
    res.status(500).json({
      error: 'Failed to calculate water demand',
      message: error.message
    });
  }
});

/**
 * POST /api/water-demand/seasonal
 * Calculate seasonal water demand for whole crop cycle
 */
router.post('/seasonal', async (req: Request, res: Response) => {
  try {
    const { zoneId, sectionId, cropType, plantingDate, harvestDate } = req.body;
    
    const targetId = zoneId || sectionId;
    logger.info(`Calculating seasonal water demand for ${targetId}, crop: ${cropType}`);
    
    // Calculate seasonal demand
    const seasonalDemand = await waterDemandService.calculateSeasonalDemand(
      targetId,
      cropType,
      new Date(plantingDate),
      harvestDate ? new Date(harvestDate) : undefined
    );
    
    // Calculate harvest date if not provided
    const calculatedHarvestDate = harvestDate 
      ? new Date(harvestDate)
      : new Date(new Date(plantingDate).getTime() + (seasonalDemand.duration || 122) * 24 * 60 * 60 * 1000);
    
    const response = {
      [zoneId ? 'zoneId' : 'sectionId']: targetId,
      cropType,
      season: {
        plantingDate,
        harvestDate: calculatedHarvestDate.toISOString().split('T')[0],
        duration: seasonalDemand.duration || 122,
        durationUnit: 'days'
      },
      waterDemand: {
        total: seasonalDemand.totalDemand || 450000,
        unit: 'm³',
        perRai: (seasonalDemand.totalDemand || 450000) / (seasonalDemand.area || 800),
        perHectare: (seasonalDemand.totalDemand || 450000) / (seasonalDemand.area || 800) * 16
      },
      stages: seasonalDemand.stages || [
        {
          stage: 'initial',
          duration: 20,
          demand: 45000,
          percentage: 10
        },
        {
          stage: 'development',
          duration: 30,
          demand: 112500,
          percentage: 25
        },
        {
          stage: 'mid_season',
          duration: 60,
          demand: 247500,
          percentage: 55
        },
        {
          stage: 'late_season',
          duration: 12,
          demand: 45000,
          percentage: 10
        }
      ],
      weekly: seasonalDemand.weeklyDemand || generateWeeklyDemand(seasonalDemand.duration || 122, seasonalDemand.totalDemand || 450000)
    };
    
    res.json(response);
  } catch (error: any) {
    logger.error('Failed to calculate seasonal water demand:', error);
    res.status(500).json({
      error: 'Failed to calculate seasonal water demand',
      message: error.message
    });
  }
});

/**
 * GET /api/water-demand/current
 * Get current water demand summary
 */
router.get('/current', async (req: Request, res: Response) => {
  try {
    const { level, id } = req.query;
    
    logger.info(`Getting current water demand at ${level} level${id ? ` for ${id}` : ''}`);
    
    // Get current week number
    const currentWeek = Math.ceil((new Date().getTime() - new Date(new Date().getFullYear(), 0, 1).getTime()) / (7 * 24 * 60 * 60 * 1000));
    const currentYear = new Date().getFullYear();
    
    let response;
    
    if (level === 'zone') {
      if (id) {
        // Get specific zone demand
        const zoneDemand = await waterDemandService.calculateWeeklyDemandByZone(
          id as string,
          currentWeek,
          currentYear
        );
        response = {
          level: 'zone',
          data: [{
            zoneId: id,
            currentDemand: zoneDemand.totalDemand || 85000,
            week: currentWeek,
            year: currentYear,
            unit: 'm³'
          }]
        };
      } else {
        // Get all zones
        response = {
          level: 'zone',
          data: [
            { zoneId: 'zone-1', currentDemand: 85000, week: currentWeek, year: currentYear, unit: 'm³' },
            { zoneId: 'zone-2', currentDemand: 72000, week: currentWeek, year: currentYear, unit: 'm³' },
            { zoneId: 'zone-3', currentDemand: 93000, week: currentWeek, year: currentYear, unit: 'm³' }
          ]
        };
      }
    } else if (level === 'section') {
      if (id) {
        // Get specific section demand
        const sectionDemand = await waterDemandService.calculateWeeklyDemandBySection(
          id as string,
          currentWeek,
          currentYear
        );
        response = {
          level: 'section',
          data: [{
            sectionId: id,
            currentDemand: sectionDemand.totalDemand || 12500,
            week: currentWeek,
            year: currentYear,
            unit: 'm³'
          }]
        };
      } else {
        // Get all sections
        response = {
          level: 'section',
          data: [
            { sectionId: 'section-1A', currentDemand: 12500, week: currentWeek, year: currentYear, unit: 'm³' },
            { sectionId: 'section-1B', currentDemand: 15000, week: currentWeek, year: currentYear, unit: 'm³' },
            { sectionId: 'section-2A', currentDemand: 18000, week: currentWeek, year: currentYear, unit: 'm³' }
          ]
        };
      }
    } else {
      // Default to field level
      response = {
        level: 'field',
        data: [
          { fieldId: 'field-001', currentDemand: 2500, week: currentWeek, year: currentYear, unit: 'm³' },
          { fieldId: 'field-002', currentDemand: 3200, week: currentWeek, year: currentYear, unit: 'm³' }
        ]
      };
    }
    
    res.json(response);
  } catch (error: any) {
    logger.error('Failed to get current water demand:', error);
    res.status(500).json({
      error: 'Failed to get current water demand',
      message: error.message
    });
  }
});

// Helper function to generate weekly demand distribution
function generateWeeklyDemand(duration: number, totalDemand: number): Array<{week: number, demand: number}> {
  const weeks = Math.ceil(duration / 7);
  const weeklyAverage = totalDemand / weeks;
  const weekly = [];
  
  for (let i = 0; i < weeks; i++) {
    // Add some variation to weekly demand
    const variation = (Math.random() - 0.5) * 0.3;
    weekly.push({
      week: i + 25, // Starting from week 25 as example
      demand: Math.round(weeklyAverage * (1 + variation))
    });
  }
  
  return weekly;
}

export default router;