export declare class ExcelImportService {
    /**
     * Import ETo data from Excel file
     */
    importEToData(filePath: string): Promise<{
        success: boolean;
        message: string;
        count?: number;
    }>;
    /**
     * Import Kc data from Excel file
     */
    importKcData(filePath: string): Promise<{
        success: boolean;
        message: string;
        count?: number;
    }>;
    /**
     * Get month key from row data
     */
    private getMonthKey;
    /**
     * Normalize crop type string to valid CropType
     */
    private normalizeCropType;
    /**
     * Validate Excel file structure for ETo data
     */
    validateEToExcel(filePath: string): {
        valid: boolean;
        errors: string[];
    };
    /**
     * Validate Excel file structure for Kc data
     */
    validateKcExcel(filePath: string): {
        valid: boolean;
        errors: string[];
    };
}
export declare const excelImportService: ExcelImportService;
//# sourceMappingURL=excel-import.service.d.ts.map