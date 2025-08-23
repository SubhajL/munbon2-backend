export declare class ShapeFileProcessor {
    private sqs;
    private s3;
    private db;
    private isRunning;
    private readonly tempDir;
    constructor();
    start(): Promise<void>;
    stop(): Promise<void>;
    private processMessages;
    private processShapeFile;
    private parseShapeFiles;
    private transformCoordinates;
    private storeParcels;
    private updateUploadStatus;
    private updateZoneSummaries;
    private sleep;
}
//# sourceMappingURL=shape-file-processor.d.ts.map