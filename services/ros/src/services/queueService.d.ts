import Bull from 'bull';
declare class QueueService {
    private calculationQueue;
    private reportQueue;
    private excelQueue;
    constructor();
    /**
     * Initialize queue processors
     */
    private setupProcessors;
    /**
     * Setup queue event handlers
     */
    private setupQueueEvents;
    /**
     * Add calculation job
     */
    addCalculationJob(data: any): Promise<Bull.Job>;
    /**
     * Add report job
     */
    addReportJob(data: any): Promise<Bull.Job>;
    /**
     * Add Excel processing job
     */
    addExcelProcessingJob(data: any): Promise<Bull.Job>;
    /**
     * Get job status
     */
    getJobStatus(jobId: string): Promise<Bull.Job | null>;
    /**
     * Get queue statistics
     */
    getQueueStats(): Promise<{
        calculation: Bull.JobCounts;
        report: Bull.JobCounts;
        excel: Bull.JobCounts;
    }>;
    /**
     * Clean old jobs
     */
    cleanOldJobs(): Promise<void>;
}
declare let queueService: QueueService;
export declare const initializeQueues: () => Promise<void>;
export { queueService };
//# sourceMappingURL=queueService.d.ts.map