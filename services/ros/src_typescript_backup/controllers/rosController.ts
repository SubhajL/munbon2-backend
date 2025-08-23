import { Request, Response, NextFunction } from 'express';
import { calculationService } from '../services/calculationService';
import { kcService } from '../services/kcService';
import { et0Service } from '../services/et0Service';
import { rainfallService } from '../services/rainfallService';
import { excelService } from '../services/excelService';
import { reportService } from '../services/reportService';
import { queueService } from '../services/queueService';
import { AppError } from '../middleware/errorHandler';
import { logger } from '../utils/logger';
import { ROSCalculationInput } from '../types';

class ROSController {
  /**
   * Calculate water demand
   */
  async calculateWaterDemand(req: Request, res: Response, next: NextFunction) {
    try {
      const input: ROSCalculationInput = {
        ...req.body,
        calculationDate: new Date(req.body.calculationDate),
        plantings: req.body.plantings.map((p: any) => ({
          ...p,
          plantingDate: new Date(p.plantingDate)
        }))
      };

      const result = await calculationService.calculateWaterDemand(input);

      res.json({
        success: true,
        data: result,
        timestamp: new Date().toISOString()
      });
    } catch (error) {
      next(error);
    }
  }

  /**
   * Batch calculate for multiple scenarios
   */
  async batchCalculate(req: Request, res: Response, next: NextFunction) {
    try {
      const { scenarios } = req.body;
      
      if (!Array.isArray(scenarios) || scenarios.length === 0) {
        throw new AppError('Scenarios array is required', 400);
      }

      // Queue the batch job
      const job = await queueService.addCalculationJob({
        type: 'batch-calculation',
        scenarios: scenarios
      });

      res.json({
        success: true,
        data: {
          jobId: job.id,
          status: 'queued',
          scenarioCount: scenarios.length
        },
        timestamp: new Date().toISOString()
      });
    } catch (error) {
      next(error);
    }
  }

  /**
   * Import Kc data from Excel
   */
  async importKcData(req: Request, res: Response, next: NextFunction) {
    try {
      if (!req.file) {
        throw new AppError('Excel file is required', 400);
      }

      const data = await excelService.parseKcData(req.file.buffer);
      await kcService.importKcData(data);

      res.json({
        success: true,
        data: {
          recordsImported: data.length,
          crops: [...new Set(data.map(d => d.cropType))]
        },
        timestamp: new Date().toISOString()
      });
    } catch (error) {
      next(error);
    }
  }

  /**
   * Import ET0 data from Excel
   */
  async importET0Data(req: Request, res: Response, next: NextFunction) {
    try {
      if (!req.file) {
        throw new AppError('Excel file is required', 400);
      }

      const data = await excelService.parseET0Data(req.file.buffer);
      await et0Service.importET0Data(data);

      res.json({
        success: true,
        data: {
          recordsImported: data.length
        },
        timestamp: new Date().toISOString()
      });
    } catch (error) {
      next(error);
    }
  }

  /**
   * Import rainfall data from Excel
   */
  async importRainfallData(req: Request, res: Response, next: NextFunction) {
    try {
      if (!req.file) {
        throw new AppError('Excel file is required', 400);
      }

      const data = await excelService.parseRainfallData(req.file.buffer);
      await rainfallService.importRainfallData(data);

      res.json({
        success: true,
        data: {
          recordsImported: data.length
        },
        timestamp: new Date().toISOString()
      });
    } catch (error) {
      next(error);
    }
  }

  /**
   * Get Kc curve for a crop
   */
  async getKcCurve(req: Request, res: Response, next: NextFunction) {
    try {
      const { cropType } = req.params;
      const curve = await kcService.getKcCurve(cropType);

      res.json({
        success: true,
        data: {
          cropType,
          curve
        },
        timestamp: new Date().toISOString()
      });
    } catch (error) {
      next(error);
    }
  }

  /**
   * Get annual ET0 pattern
   */
  async getAnnualET0(req: Request, res: Response, next: NextFunction) {
    try {
      const year = req.query.year ? parseInt(req.query.year as string) : undefined;
      const pattern = await et0Service.getAnnualET0Pattern(year);

      res.json({
        success: true,
        data: {
          year: year || new Date().getFullYear(),
          pattern
        },
        timestamp: new Date().toISOString()
      });
    } catch (error) {
      next(error);
    }
  }

  /**
   * Get annual rainfall pattern
   */
  async getAnnualRainfall(req: Request, res: Response, next: NextFunction) {
    try {
      const year = req.query.year ? parseInt(req.query.year as string) : undefined;
      const pattern = await rainfallService.getAnnualRainfallPattern(year);

      res.json({
        success: true,
        data: {
          year: year || new Date().getFullYear(),
          pattern
        },
        timestamp: new Date().toISOString()
      });
    } catch (error) {
      next(error);
    }
  }

  /**
   * Generate report
   */
  async generateReport(req: Request, res: Response, next: NextFunction) {
    try {
      const reportRequest = req.body;
      
      const job = await queueService.addReportJob(reportRequest);

      res.json({
        success: true,
        data: {
          reportId: job.id,
          status: 'queued'
        },
        timestamp: new Date().toISOString()
      });
    } catch (error) {
      next(error);
    }
  }

  /**
   * Get report status
   */
  async getReport(req: Request, res: Response, next: NextFunction) {
    try {
      const { reportId } = req.params;
      const report = await reportService.getReportStatus(reportId);

      res.json({
        success: true,
        data: report,
        timestamp: new Date().toISOString()
      });
    } catch (error) {
      next(error);
    }
  }

  /**
   * Download report
   */
  async downloadReport(req: Request, res: Response, next: NextFunction) {
    try {
      const { reportId } = req.params;
      const { stream, filename, contentType } = await reportService.getReportFile(reportId);

      res.setHeader('Content-Type', contentType);
      res.setHeader('Content-Disposition', `attachment; filename="${filename}"`);
      
      stream.pipe(res);
    } catch (error) {
      next(error);
    }
  }

  /**
   * Upload Excel file for processing
   */
  async uploadExcelFile(req: Request, res: Response, next: NextFunction) {
    try {
      if (!req.file) {
        throw new AppError('Excel file is required', 400);
      }

      const job = await queueService.addExcelProcessingJob({
        filename: req.file.originalname,
        buffer: req.file.buffer,
        userId: (req as any).userId || 'anonymous'
      });

      res.json({
        success: true,
        data: {
          jobId: job.id,
          status: 'queued',
          filename: req.file.originalname
        },
        timestamp: new Date().toISOString()
      });
    } catch (error) {
      next(error);
    }
  }

  /**
   * Get processing status
   */
  async getProcessingStatus(req: Request, res: Response, next: NextFunction) {
    try {
      const { jobId } = req.params;
      const job = await queueService.getJobStatus(jobId);

      if (!job) {
        throw new AppError('Job not found', 404);
      }

      res.json({
        success: true,
        data: {
          jobId: job.id,
          status: await job.getState(),
          progress: job.progress(),
          result: job.returnvalue,
          error: job.failedReason
        },
        timestamp: new Date().toISOString()
      });
    } catch (error) {
      next(error);
    }
  }

  /**
   * Get calculation history
   */
  async getCalculationHistory(req: Request, res: Response, next: NextFunction) {
    try {
      const { page = 1, limit = 10, startDate, endDate } = req.query;
      
      const history = await calculationService.getCalculationHistory({
        page: parseInt(page as string),
        limit: parseInt(limit as string),
        startDate: startDate ? new Date(startDate as string) : undefined,
        endDate: endDate ? new Date(endDate as string) : undefined
      });

      res.json({
        success: true,
        data: history,
        timestamp: new Date().toISOString()
      });
    } catch (error) {
      next(error);
    }
  }

  /**
   * Get calculation details
   */
  async getCalculationDetails(req: Request, res: Response, next: NextFunction) {
    try {
      const { calculationId } = req.params;
      const details = await calculationService.getCalculationById(calculationId);

      if (!details) {
        throw new AppError('Calculation not found', 404);
      }

      res.json({
        success: true,
        data: details,
        timestamp: new Date().toISOString()
      });
    } catch (error) {
      next(error);
    }
  }

  /**
   * Get demand pattern visualization data
   */
  async getDemandPattern(req: Request, res: Response, next: NextFunction) {
    try {
      const { cropType, year, period = 'monthly' } = req.query;
      
      const pattern = await calculationService.getDemandPattern({
        cropType: cropType as string,
        year: year ? parseInt(year as string) : new Date().getFullYear(),
        period: period as 'daily' | 'weekly' | 'monthly'
      });

      res.json({
        success: true,
        data: pattern,
        timestamp: new Date().toISOString()
      });
    } catch (error) {
      next(error);
    }
  }

  /**
   * Get seasonal analysis
   */
  async getSeasonalAnalysis(req: Request, res: Response, next: NextFunction) {
    try {
      const { year } = req.query;
      
      const analysis = await calculationService.getSeasonalAnalysis(
        year ? parseInt(year as string) : new Date().getFullYear()
      );

      res.json({
        success: true,
        data: analysis,
        timestamp: new Date().toISOString()
      });
    } catch (error) {
      next(error);
    }
  }

  /**
   * Get available crops
   */
  async getAvailableCrops(req: Request, res: Response, next: NextFunction) {
    try {
      const crops = await kcService.getAvailableCrops();

      res.json({
        success: true,
        data: crops,
        timestamp: new Date().toISOString()
      });
    } catch (error) {
      next(error);
    }
  }

  /**
   * Get crop information
   */
  async getCropInfo(req: Request, res: Response, next: NextFunction) {
    try {
      const { cropType } = req.params;
      const info = await kcService.getCropInfo(cropType);

      res.json({
        success: true,
        data: info,
        timestamp: new Date().toISOString()
      });
    } catch (error) {
      next(error);
    }
  }
}

export const rosController = new ROSController();