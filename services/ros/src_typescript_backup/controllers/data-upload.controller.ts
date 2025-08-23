import { Request, Response, NextFunction } from 'express';
import { excelImportService } from '@services/excel-import.service';
import { logger } from '@utils/logger';
import fs from 'fs/promises';

class DataUploadController {
  /**
   * Upload and import ETo data from Excel
   */
  async uploadEToData(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      if (!req.file) {
        res.status(400).json({
          success: false,
          message: 'No file uploaded',
        });
        return;
      }

      // Validate file
      const validation = excelImportService.validateEToExcel(req.file.path);
      if (!validation.valid) {
        // Clean up uploaded file
        await fs.unlink(req.file.path);
        res.status(400).json({
          success: false,
          message: 'Invalid Excel file',
          errors: validation.errors,
        });
        return;
      }

      // Import data
      const result = await excelImportService.importEToData(req.file.path);

      // Clean up uploaded file
      await fs.unlink(req.file.path);

      if (result.success) {
        res.status(200).json(result);
      } else {
        res.status(400).json(result);
      }
    } catch (error) {
      logger.error('Error uploading ETo data', error);
      // Clean up file if exists
      if (req.file) {
        await fs.unlink(req.file.path).catch(() => {});
      }
      next(error);
    }
  }

  /**
   * Upload and import Kc data from Excel
   */
  async uploadKcData(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      if (!req.file) {
        res.status(400).json({
          success: false,
          message: 'No file uploaded',
        });
        return;
      }

      // Validate file
      const validation = excelImportService.validateKcExcel(req.file.path);
      if (!validation.valid) {
        // Clean up uploaded file
        await fs.unlink(req.file.path);
        res.status(400).json({
          success: false,
          message: 'Invalid Excel file',
          errors: validation.errors,
        });
        return;
      }

      // Import data
      const result = await excelImportService.importKcData(req.file.path);

      // Clean up uploaded file
      await fs.unlink(req.file.path);

      if (result.success) {
        res.status(200).json(result);
      } else {
        res.status(400).json(result);
      }
    } catch (error) {
      logger.error('Error uploading Kc data', error);
      // Clean up file if exists
      if (req.file) {
        await fs.unlink(req.file.path).catch(() => {});
      }
      next(error);
    }
  }

  /**
   * Download ETo template Excel file
   */
  async downloadEToTemplate(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      // Create template Excel file
      const XLSX = await import('xlsx');
      const workbook = XLSX.utils.book_new();

      // Create ETo sheet with headers
      const headers = ['Station', 'Province', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                      'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
      const sampleData = [
        headers,
        ['นครราชสีมา', 'นครราชสีมา', 108.5, 122.4, 151.9, 156.0, 148.8, 132.0, 
         130.2, 127.1, 114.0, 108.5, 102.0, 99.2],
      ];

      const ws = XLSX.utils.aoa_to_sheet(sampleData);
      XLSX.utils.book_append_sheet(workbook, ws, 'ETo');

      // Write to buffer
      const buffer = XLSX.write(workbook, { type: 'buffer', bookType: 'xlsx' });

      res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
      res.setHeader('Content-Disposition', 'attachment; filename=eto-template.xlsx');
      res.send(buffer);
    } catch (error) {
      logger.error('Error creating ETo template', error);
      next(error);
    }
  }

  /**
   * Download Kc template Excel file
   */
  async downloadKcTemplate(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      // Create template Excel file
      const XLSX = await import('xlsx');
      const workbook = XLSX.utils.book_new();

      // Create Kc sheet with headers
      const headers = ['Crop Type'];
      for (let i = 1; i <= 16; i++) {
        headers.push(`Week ${i}`);
      }

      const sampleData = [
        headers,
        ['rice', 1.05, 1.05, 1.05, 1.05, 1.10, 1.15, 1.20, 1.20, 
         1.20, 1.20, 1.20, 1.15, 1.10, 1.00, 0.95, 0.90],
        ['corn', 0.30, 0.30, 0.40, 0.50, 0.60, 0.75, 0.90, 1.05, 
         1.20, 1.20, 1.20, 1.10, 1.00, 0.85, 0.70, 0.60],
      ];

      const ws = XLSX.utils.aoa_to_sheet(sampleData);
      XLSX.utils.book_append_sheet(workbook, ws, 'Kc');

      // Write to buffer
      const buffer = XLSX.write(workbook, { type: 'buffer', bookType: 'xlsx' });

      res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
      res.setHeader('Content-Disposition', 'attachment; filename=kc-template.xlsx');
      res.send(buffer);
    } catch (error) {
      logger.error('Error creating Kc template', error);
      next(error);
    }
  }
}

export const dataUploadController = new DataUploadController();