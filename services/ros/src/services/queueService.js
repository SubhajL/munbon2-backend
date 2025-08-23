"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.queueService = exports.initializeQueues = void 0;
const bull_1 = __importDefault(require("bull"));
const logger_1 = require("../utils/logger");
const calculationService_1 = require("./calculationService");
const excelService_1 = require("./excelService");
const reportService_1 = require("./reportService");
class QueueService {
    calculationQueue;
    reportQueue;
    excelQueue;
    constructor() {
        const redisConfig = {
            host: process.env.REDIS_HOST || 'localhost',
            port: parseInt(process.env.REDIS_PORT || '6379'),
            password: process.env.REDIS_PASSWORD,
            db: parseInt(process.env.REDIS_DB || '0')
        };
        this.calculationQueue = new bull_1.default('ros-calculations', { redis: redisConfig });
        this.reportQueue = new bull_1.default('ros-reports', { redis: redisConfig });
        this.excelQueue = new bull_1.default('ros-excel', { redis: redisConfig });
        this.setupProcessors();
    }
    /**
     * Initialize queue processors
     */
    setupProcessors() {
        // Calculation queue processor
        this.calculationQueue.process(parseInt(process.env.QUEUE_CONCURRENCY || '5'), async (job) => {
            logger_1.logger.info(`Processing calculation job ${job.id}`);
            try {
                const { type, data } = job.data;
                if (type === 'single-calculation') {
                    return await calculationService_1.calculationService.calculateWaterDemand(data);
                }
                else if (type === 'batch-calculation') {
                    const results = [];
                    const { scenarios } = data;
                    for (let i = 0; i < scenarios.length; i++) {
                        await job.progress((i / scenarios.length) * 100);
                        const result = await calculationService_1.calculationService.calculateWaterDemand(scenarios[i]);
                        results.push(result);
                    }
                    return results;
                }
                throw new Error(`Unknown calculation type: ${type}`);
            }
            catch (error) {
                logger_1.logger.error(`Calculation job ${job.id} failed:`, error);
                throw error;
            }
        });
        // Report queue processor
        this.reportQueue.process(parseInt(process.env.QUEUE_CONCURRENCY || '5'), async (job) => {
            logger_1.logger.info(`Processing report job ${job.id}`);
            try {
                const { calculationId, format, options } = job.data;
                await job.progress(10);
                const calculation = await calculationService_1.calculationService.getCalculationById(calculationId);
                if (!calculation) {
                    throw new Error('Calculation not found');
                }
                await job.progress(30);
                let report;
                switch (format) {
                    case 'pdf':
                        report = await reportService_1.reportService.generatePDFReport(calculation, options);
                        break;
                    case 'excel':
                        report = await reportService_1.reportService.generateExcelReport(calculation, options);
                        break;
                    case 'csv':
                        report = await reportService_1.reportService.generateCSVReport(calculation, options);
                        break;
                    default:
                        throw new Error(`Unknown report format: ${format}`);
                }
                await job.progress(90);
                // Save report
                const savedReport = await reportService_1.reportService.saveReport({
                    calculationId,
                    format,
                    data: report,
                    metadata: {
                        generatedAt: new Date(),
                        options
                    }
                });
                await job.progress(100);
                return savedReport;
            }
            catch (error) {
                logger_1.logger.error(`Report job ${job.id} failed:`, error);
                throw error;
            }
        });
        // Excel processing queue
        this.excelQueue.process(parseInt(process.env.QUEUE_CONCURRENCY || '5'), async (job) => {
            logger_1.logger.info(`Processing Excel job ${job.id}`);
            try {
                const { filename, buffer, userId } = job.data;
                await job.progress(10);
                // Parse Excel file
                const parsedData = await excelService_1.excelService.parseROSExcelFile(Buffer.from(buffer));
                await job.progress(30);
                // Prepare calculation input
                const calculationInput = {
                    cropType: parsedData.cropType,
                    plantings: parsedData.plantingSchedule,
                    calculationDate: new Date(),
                    calculationPeriod: 'weekly',
                    nonAgriculturalDemands: parsedData.nonAgriculturalDemands
                };
                await job.progress(50);
                // Calculate water demand
                const result = await calculationService_1.calculationService.calculateWaterDemand(calculationInput);
                await job.progress(80);
                // Save results
                const savedResult = await calculationService_1.calculationService.saveCalculation({
                    ...result,
                    metadata: {
                        ...result.metadata,
                        sourceFile: filename,
                        uploadedBy: userId,
                        parameters: parsedData.parameters
                    }
                });
                await job.progress(100);
                return {
                    calculationId: savedResult.id,
                    filename,
                    results: result
                };
            }
            catch (error) {
                logger_1.logger.error(`Excel job ${job.id} failed:`, error);
                throw error;
            }
        });
        // Queue event handlers
        this.setupQueueEvents();
    }
    /**
     * Setup queue event handlers
     */
    setupQueueEvents() {
        const queues = [this.calculationQueue, this.reportQueue, this.excelQueue];
        queues.forEach((queue) => {
            queue.on('completed', (job, result) => {
                logger_1.logger.info(`Job ${job.id} completed in queue ${queue.name}`);
            });
            queue.on('failed', (job, err) => {
                logger_1.logger.error(`Job ${job.id} failed in queue ${queue.name}:`, err);
            });
            queue.on('stalled', (job) => {
                logger_1.logger.warn(`Job ${job.id} stalled in queue ${queue.name}`);
            });
            queue.on('progress', (job, progress) => {
                logger_1.logger.debug(`Job ${job.id} progress in queue ${queue.name}: ${progress}%`);
            });
        });
    }
    /**
     * Add calculation job
     */
    async addCalculationJob(data) {
        const job = await this.calculationQueue.add(data, {
            attempts: parseInt(process.env.QUEUE_MAX_RETRIES || '3'),
            backoff: {
                type: 'exponential',
                delay: 2000
            },
            removeOnComplete: true,
            removeOnFail: false
        });
        logger_1.logger.info(`Added calculation job ${job.id}`);
        return job;
    }
    /**
     * Add report job
     */
    async addReportJob(data) {
        const job = await this.reportQueue.add(data, {
            attempts: parseInt(process.env.QUEUE_MAX_RETRIES || '3'),
            backoff: {
                type: 'exponential',
                delay: 2000
            },
            removeOnComplete: false, // Keep for download
            removeOnFail: false
        });
        logger_1.logger.info(`Added report job ${job.id}`);
        return job;
    }
    /**
     * Add Excel processing job
     */
    async addExcelProcessingJob(data) {
        const job = await this.excelQueue.add(data, {
            attempts: parseInt(process.env.QUEUE_MAX_RETRIES || '3'),
            backoff: {
                type: 'exponential',
                delay: 2000
            },
            removeOnComplete: false,
            removeOnFail: false
        });
        logger_1.logger.info(`Added Excel processing job ${job.id}`);
        return job;
    }
    /**
     * Get job status
     */
    async getJobStatus(jobId) {
        // Check all queues
        let job = await this.calculationQueue.getJob(jobId);
        if (job)
            return job;
        job = await this.reportQueue.getJob(jobId);
        if (job)
            return job;
        job = await this.excelQueue.getJob(jobId);
        return job;
    }
    /**
     * Get queue statistics
     */
    async getQueueStats() {
        const [calculation, report, excel] = await Promise.all([
            this.calculationQueue.getJobCounts(),
            this.reportQueue.getJobCounts(),
            this.excelQueue.getJobCounts()
        ]);
        return { calculation, report, excel };
    }
    /**
     * Clean old jobs
     */
    async cleanOldJobs() {
        const grace = 24 * 60 * 60 * 1000; // 24 hours
        await Promise.all([
            this.calculationQueue.clean(grace, 'completed'),
            this.calculationQueue.clean(grace, 'failed'),
            this.reportQueue.clean(grace * 7, 'completed'), // Keep reports for 7 days
            this.reportQueue.clean(grace, 'failed'),
            this.excelQueue.clean(grace, 'completed'),
            this.excelQueue.clean(grace, 'failed')
        ]);
        logger_1.logger.info('Cleaned old jobs from queues');
    }
}
// Initialize queues
let queueService;
const initializeQueues = async () => {
    exports.queueService = queueService = new QueueService();
    // Schedule periodic cleanup
    setInterval(() => {
        queueService.cleanOldJobs().catch((error) => {
            logger_1.logger.error('Error cleaning old jobs:', error);
        });
    }, 60 * 60 * 1000); // Every hour
};
exports.initializeQueues = initializeQueues;
//# sourceMappingURL=queueService.js.map