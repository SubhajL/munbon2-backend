interface ProcessOptions {
    buffer: Buffer;
    fileName: string;
    uploadId: string;
}
interface ParsedParcel {
    parcelId: string;
    geometry: any;
    area: number;
    zoneId: string;
    subZone?: string;
    ownerName?: string;
    ownerId?: string;
    cropType?: string;
    landUseType?: string;
    attributes: any;
    ridAttributes?: {
        parcelAreaRai?: number;
        dataDateProcess?: string;
        startInt?: string;
        wpet?: number;
        age?: number;
        wprod?: number;
        plantId?: string;
        yieldAtMcKgpr?: number;
        seasonIrrM3PerRai?: number;
        autoNote?: string;
        stageAge?: number;
        lat?: number;
        lon?: number;
        subMember?: number;
    };
}
export declare class ShapeFileProcessor {
    private readonly tempDir;
    constructor();
    processShapeFile(options: ProcessOptions): Promise<ParsedParcel[]>;
    private parseShapeFiles;
    private transformCoordinates;
    private extractParcelProperties;
    private cleanupDirectory;
}
export {};
//# sourceMappingURL=shapefile-processor.d.ts.map