import { Router } from 'express';
import { waterLevelController } from '@controllers/water-level.controller';
import { validateRequest } from '@middleware/validate-request';
import { waterLevelValidation } from '@utils/validation/water-level.validation';
import { waterLevelAggregationService } from '@services/water-level-aggregation.service';
import { logger } from '@utils/logger';

const router = Router();

// Get current water level
router.get(
  '/current/:areaId',
  validateRequest(waterLevelValidation.getCurrentLevel),
  waterLevelController.getCurrentWaterLevel
);

// Add water level measurement
router.post(
  '/',
  validateRequest(waterLevelValidation.addWaterLevel),
  waterLevelController.addWaterLevelMeasurement
);

// Bulk import water level data
router.post(
  '/import',
  validateRequest(waterLevelValidation.importWaterLevels),
  waterLevelController.importWaterLevelData
);

// Get water level history
router.get(
  '/history/:areaId',
  validateRequest(waterLevelValidation.getWaterLevelHistory),
  waterLevelController.getWaterLevelHistory
);

// Update water level data
router.put(
  '/:id',
  validateRequest(waterLevelValidation.updateWaterLevel),
  waterLevelController.updateWaterLevel
);

// Delete water level data
router.delete(
  '/:id',
  validateRequest(waterLevelValidation.deleteWaterLevel),
  waterLevelController.deleteWaterLevel
);

// Get water level statistics
router.get(
  '/statistics/:areaId',
  validateRequest(waterLevelValidation.getWaterLevelStatistics),
  waterLevelController.getWaterLevelStatistics
);

// Get water level trends
router.get(
  '/trends/:areaId',
  validateRequest(waterLevelValidation.getWaterLevelTrends),
  waterLevelController.getWaterLevelTrends
);

// Get aggregated weekly water level
router.get('/weekly', async (req, res) => {
  try {
    const { areaId, areaType, calendarWeek, calendarYear } = req.query;

    if (!areaId || !areaType || !calendarWeek || !calendarYear) {
      return res.status(400).json({
        success: false,
        error: 'Missing required parameters: areaId, areaType, calendarWeek, calendarYear'
      });
    }

    const weeklyLevel = await waterLevelAggregationService.getWeeklyWaterLevel(
      areaId as string,
      areaType as string,
      parseInt(calendarWeek as string),
      parseInt(calendarYear as string)
    );

    if (!weeklyLevel) {
      return res.status(404).json({
        success: false,
        error: 'No water level data found for the specified week'
      });
    }

    res.json({
      success: true,
      data: weeklyLevel
    });
  } catch (error) {
    logger.error('Failed to get weekly water level', error);
    res.status(500).json({
      success: false,
      error: 'Internal server error'
    });
  }
});

// Aggregate water levels for a specific week
router.post('/aggregate', async (req, res) => {
  try {
    const { areaId, areaType, calendarWeek, calendarYear } = req.body;

    if (!areaId || !areaType || !calendarWeek || !calendarYear) {
      return res.status(400).json({
        success: false,
        error: 'Missing required parameters: areaId, areaType, calendarWeek, calendarYear'
      });
    }

    const result = await waterLevelAggregationService.aggregateWeeklyWaterLevel(
      areaId,
      areaType,
      calendarWeek,
      calendarYear
    );

    res.json({
      success: true,
      data: result
    });
  } catch (error) {
    logger.error('Failed to aggregate water levels', error);
    res.status(500).json({
      success: false,
      error: 'Internal server error'
    });
  }
});

// Backfill historical water level aggregations
router.post('/backfill', async (req, res) => {
  try {
    const { areaId, areaType, startWeek, startYear, endWeek, endYear } = req.body;

    if (!areaId || !areaType || !startWeek || !startYear || !endWeek || !endYear) {
      return res.status(400).json({
        success: false,
        error: 'Missing required parameters'
      });
    }

    const processedCount = await waterLevelAggregationService.backfillHistoricalData(
      areaId,
      areaType,
      startWeek,
      startYear,
      endWeek,
      endYear
    );

    res.json({
      success: true,
      data: {
        processedWeeks: processedCount,
        message: `Successfully backfilled ${processedCount} weeks of data`
      }
    });
  } catch (error) {
    logger.error('Failed to backfill water levels', error);
    res.status(500).json({
      success: false,
      error: 'Internal server error'
    });
  }
});

export default router;