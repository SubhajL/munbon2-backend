import { ROSCalculationInput, PlantingData } from '../types';
export declare class ExcelService {
    /**
     * Parse Kc data from Excel file
     */
    parseKcData(buffer: Buffer): Promise<Array<{
        cropType: string;
        growthWeek: number;
        kcValue: number;
        growthStage?: string;
    }>>;
    /**
     * Parse ET0 data from Excel file
     */
    parseET0Data(buffer: Buffer): Promise<Array<{
        location?: string;
        year: number;
        month: number;
        et0Value: number;
        source?: string;
    }>>;
    /**
     * Parse rainfall data from Excel file
     */
    parseRainfallData(buffer: Buffer): Promise<Array<{
        location?: string;
        year: number;
        month: number;
        totalRainfall: number;
        effectiveRainfall: number;
        numberOfRainyDays?: number;
    }>>;
    /**
     * Parse complete ROS Excel file
     */
    parseROSExcelFile(buffer: Buffer): Promise<{
        cropType: string;
        plantingSchedule: PlantingData[];
        nonAgriculturalDemands: ROSCalculationInput['nonAgriculturalDemands'];
        parameters: Record<string, any>;
    }>;
    /**
     * Extract planting schedule from paddy sheet
     */
    private extractPlantingSchedule;
    /**
     * Generate Excel report
     */
    generateExcelReport(data: any): Promise<Buffer>;
    /**
     * Get cell value helper
     */
    private getCellValue;
    /**
     * Get numeric cell value helper
     */
    private getNumericCellValue;
    /**
     * Determine growth stage based on week
     */
    private determineGrowthStage;
    /**
     * Generate CSV report
     */
    generateCSVReport(data: any[]): Promise<string>;
}
export declare const excelService: ExcelService;
//# sourceMappingURL=excelService.d.ts.map