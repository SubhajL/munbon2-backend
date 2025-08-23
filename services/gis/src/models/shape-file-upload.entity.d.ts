export declare enum UploadStatus {
    PENDING = "pending",
    PROCESSING = "processing",
    COMPLETED = "completed",
    FAILED = "failed"
}
export declare class ShapeFileUpload {
    id: string;
    uploadId: string;
    fileName: string;
    s3Key: string;
    status: UploadStatus;
    metadata?: Record<string, any>;
    error?: string;
    parcelCount?: number;
    uploadedAt: Date;
    updatedAt: Date;
    completedAt?: Date;
}
//# sourceMappingURL=shape-file-upload.entity.d.ts.map