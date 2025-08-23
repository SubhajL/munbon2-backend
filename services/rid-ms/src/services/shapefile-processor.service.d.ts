import { ShapeFileMetadata, ProcessingResult } from '../types';
export declare class ShapeFileProcessorService {
    private static instance;
    private databaseService;
    private kafkaService;
    private constructor();
    static getInstance(): ShapeFileProcessorService;
    processShapeFile(filePath: string, metadata: Partial<ShapeFileMetadata>): Promise<ProcessingResult>;
    private extractZipFile;
    private readShapeFile;
    private processParcels;
    private transformCoordinates;
    private determineWaterDemandMethod;
    private calculateBoundingBox;
    private archiveFile;
    cleanupOldFiles(): Promise<void>;
}
//# sourceMappingURL=shapefile-processor.service.d.ts.map