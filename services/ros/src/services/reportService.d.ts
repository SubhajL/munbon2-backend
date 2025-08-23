import fs from 'fs/promises';
export declare class ReportService {
    private reportDir;
    constructor();
    /**
     * Ensure report directory exists
     */
    private ensureReportDirectory;
    /**
     * Generate PDF report
     */
    generatePDFReport(calculation: any, options?: {
        includeCharts?: boolean;
        includeHistorical?: boolean;
        language?: 'en' | 'th';
    }): Promise<Buffer>;
    /**
     * Generate Excel report
     */
    generateExcelReport(calculation: any, options?: {
        includeHistorical?: boolean;
        dateRange?: {
            start: Date;
            end: Date;
        };
    }): Promise<Buffer>;
    /**
     * Generate CSV report
     */
    generateCSVReport(calculation: any, options?: {}): Promise<string>;
    /**
     * Format calculation for Excel/CSV export
     */
    private formatCalculationForExcel;
    /**
     * Save report to database and filesystem
     */
    saveReport(reportData: {
        calculationId: string;
        format: string;
        data: Buffer | string;
        metadata: any;
    }): Promise<any>;
    /**
     * Get report status
     */
    getReportStatus(reportId: string): Promise<any>;
    /**
     * Get report file for download
     */
    getReportFile(reportId: string): Promise<{
        stream: fs.ReadStream;
        filename: string;
        contentType: string;
    }>;
    /**
     * Get content type for format
     */
    private getContentType;
    /**
     * Clean old reports
     */
    cleanOldReports(daysToKeep?: number): Promise<void>;
}
export declare const reportService: ReportService;
//# sourceMappingURL=reportService.d.ts.map