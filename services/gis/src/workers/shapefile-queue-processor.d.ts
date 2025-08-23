export declare class ShapeFileQueueProcessor {
    private sqs;
    private shapeFileService;
    private isRunning;
    private queueUrl;
    constructor();
    start(): Promise<void>;
    stop(): Promise<void>;
    private pollQueue;
    private processMessage;
}
//# sourceMappingURL=shapefile-queue-processor.d.ts.map