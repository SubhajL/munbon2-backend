interface UploadOptions {
    file: Express.Multer.File;
    waterDemandMethod: 'RID-MS' | 'ROS' | 'AWD';
    processingInterval: 'daily' | 'weekly' | 'bi-weekly';
    metadata?: any;
}
export declare class ShapeFileService {
    private s3;
    private sqs;
    private processor;
    private geopackageProcessor;
    constructor();
    processUpload(options: UploadOptions): Promise<{
        uploadId: any;
        fileName: string;
        status: string;
        uploadedAt: string;
        message: string;
    }>;
    processShapeFileFromQueue(message: any): Promise<void>;
    private storeUploadRecord;
    private updateUploadStatus;
    private storeParcels;
    listUploads(options: any): Promise<{
        uploads: never[];
        total: number;
        page: any;
        limit: any;
    }>;
    getUploadStatus(uploadId: string): Promise<null>;
    getUploadParcels(uploadId: string): Promise<never[]>;
    deleteUpload(uploadId: string): Promise<void>;
}
export {};
//# sourceMappingURL=shapefile.service.d.ts.map