import * as XLSX from 'xlsx';
import { etoDataService } from './eto-data.service';
import { kcDataService } from './kc-data.service';
import { CropType } from '@types/index';
import { logger } from '@utils/logger';

export class ExcelImportService {
  /**
   * Import ETo data from Excel file
   */
  async importEToData(filePath: string): Promise<{ success: boolean; message: string; count?: number }> {
    try {
      // Read Excel file
      const workbook = XLSX.readFile(filePath);
      const sheetName = 'ETo'; // Assuming sheet name is 'ETo'
      const worksheet = workbook.Sheets[sheetName];

      if (!worksheet) {
        return { success: false, message: `Sheet '${sheetName}' not found in Excel file` };
      }

      // Convert to JSON
      const data = XLSX.utils.sheet_to_json(worksheet);
      
      // Process and validate data
      const etoRecords: Array<{
        aosStation: string;
        province: string;
        month: number;
        etoValue: number;
      }> = [];

      for (const row of data) {
        // Assuming Excel columns: Station, Province, Month, ETo
        const station = row['Station'] || row['สถานี'] || 'นครราชสีมา';
        const province = row['Province'] || row['จังหวัด'] || 'นครราชสีมา';
        
        // Process monthly columns (Jan-Dec or 1-12)
        for (let month = 1; month <= 12; month++) {
          const monthKey = this.getMonthKey(row, month);
          if (monthKey && row[monthKey] !== undefined) {
            const etoValue = parseFloat(row[monthKey]);
            if (!isNaN(etoValue)) {
              etoRecords.push({
                aosStation: station,
                province: province,
                month: month,
                etoValue: etoValue,
              });
            }
          }
        }
      }

      // Upload to database
      await etoDataService.uploadEToData(etoRecords);

      return {
        success: true,
        message: `Successfully imported ${etoRecords.length} ETo records`,
        count: etoRecords.length,
      };
    } catch (error) {
      logger.error('Failed to import ETo data', error);
      return {
        success: false,
        message: `Import failed: ${error instanceof Error ? error.message : 'Unknown error'}`,
      };
    }
  }

  /**
   * Import Kc data from Excel file
   */
  async importKcData(filePath: string): Promise<{ success: boolean; message: string; count?: number }> {
    try {
      // Read Excel file
      const workbook = XLSX.readFile(filePath);
      const sheetName = 'Kc'; // Assuming sheet name is 'Kc'
      const worksheet = workbook.Sheets[sheetName];

      if (!worksheet) {
        return { success: false, message: `Sheet '${sheetName}' not found in Excel file` };
      }

      // Convert to JSON
      const data = XLSX.utils.sheet_to_json(worksheet);
      
      // Process and validate data
      const kcRecords: Array<{
        cropType: CropType;
        cropWeek: number;
        kcValue: number;
      }> = [];

      for (const row of data) {
        // Assuming Excel columns: Crop Type, Week 1, Week 2, ..., Week N
        const cropTypeRaw = row['Crop Type'] || row['ชนิดพืช'] || row['Crop'] || '';
        const cropType = this.normalizeCropType(cropTypeRaw);

        if (!cropType) {
          continue; // Skip invalid crop types
        }

        // Process weekly columns
        for (let week = 1; week <= 52; week++) {
          const weekKey = `Week ${week}` || `สัปดาห์ ${week}` || `W${week}` || week.toString();
          if (row[weekKey] !== undefined) {
            const kcValue = parseFloat(row[weekKey]);
            if (!isNaN(kcValue)) {
              kcRecords.push({
                cropType: cropType,
                cropWeek: week,
                kcValue: kcValue,
              });
            }
          }
        }
      }

      // Upload to database
      await kcDataService.uploadKcData(kcRecords);

      return {
        success: true,
        message: `Successfully imported ${kcRecords.length} Kc records`,
        count: kcRecords.length,
      };
    } catch (error) {
      logger.error('Failed to import Kc data', error);
      return {
        success: false,
        message: `Import failed: ${error instanceof Error ? error.message : 'Unknown error'}`,
      };
    }
  }

  /**
   * Get month key from row data
   */
  private getMonthKey(row: any, month: number): string | null {
    // Try different month formats
    const monthNames = [
      ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
      ['มกราคม', 'กุมภาพันธ์', 'มีนาคม', 'เมษายน', 'พฤษภาคม', 'มิถุนายน', 
       'กรกฎาคม', 'สิงหาคม', 'กันยายน', 'ตุลาคม', 'พฤศจิกายน', 'ธันวาคม'],
      ['ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.', 
       'ก.ค.', 'ส.ค.', 'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.'],
    ];

    // Check numeric month
    if (row[month.toString()]) {
      return month.toString();
    }

    // Check month names
    for (const names of monthNames) {
      if (row[names[month - 1]]) {
        return names[month - 1];
      }
    }

    return null;
  }

  /**
   * Normalize crop type string to valid CropType
   */
  private normalizeCropType(cropTypeRaw: string): CropType | null {
    const normalized = cropTypeRaw.toLowerCase().trim();
    
    // Map various names to standard crop types
    const cropMap: Record<string, CropType> = {
      'rice': 'rice',
      'ข้าว': 'rice',
      'ข้าวนาปี': 'rice',
      'ข้าวนาปรัง': 'rice',
      'corn': 'corn',
      'maize': 'corn',
      'ข้าวโพด': 'corn',
      'sugarcane': 'sugarcane',
      'sugar cane': 'sugarcane',
      'อ้อย': 'sugarcane',
    };

    return cropMap[normalized] || null;
  }

  /**
   * Validate Excel file structure for ETo data
   */
  validateEToExcel(filePath: string): { valid: boolean; errors: string[] } {
    try {
      const workbook = XLSX.readFile(filePath);
      const errors: string[] = [];

      // Check for ETo sheet
      if (!workbook.Sheets['ETo']) {
        errors.push("Missing 'ETo' worksheet");
      }

      // Additional validation can be added here

      return {
        valid: errors.length === 0,
        errors,
      };
    } catch (error) {
      return {
        valid: false,
        errors: [`Failed to read Excel file: ${error instanceof Error ? error.message : 'Unknown error'}`],
      };
    }
  }

  /**
   * Validate Excel file structure for Kc data
   */
  validateKcExcel(filePath: string): { valid: boolean; errors: string[] } {
    try {
      const workbook = XLSX.readFile(filePath);
      const errors: string[] = [];

      // Check for Kc sheet
      if (!workbook.Sheets['Kc']) {
        errors.push("Missing 'Kc' worksheet");
      }

      // Additional validation can be added here

      return {
        valid: errors.length === 0,
        errors,
      };
    } catch (error) {
      return {
        valid: false,
        errors: [`Failed to read Excel file: ${error instanceof Error ? error.message : 'Unknown error'}`],
      };
    }
  }
}

export const excelImportService = new ExcelImportService();