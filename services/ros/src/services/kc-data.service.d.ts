import { CropType } from '@types/index';
export declare class KcDataService {
    /**
     * Get Kc value for specific crop and week
     */
    getKcValue(cropType: CropType, cropWeek: number): Promise<number>;
    /**
     * Get all Kc values for a crop type
     */
    getAllKcValues(cropType: CropType): Promise<Array<{
        cropWeek: number;
        kcValue: number;
    }>>;
    /**
     * Get total crop weeks for a crop type
     */
    getTotalCropWeeks(cropType: CropType): Promise<number>;
    /**
     * Upload Kc data from Excel (to be implemented)
     */
    uploadKcData(data: Array<{
        cropType: CropType;
        cropWeek: number;
        kcValue: number;
    }>): Promise<void>;
    /**
     * Get crop information summary
     */
    getCropSummary(): Promise<Array<{
        cropType: CropType;
        totalWeeks: number;
        kcRange: {
            min: number;
            max: number;
        };
    }>>;
}
export declare const kcDataService: KcDataService;
//# sourceMappingURL=kc-data.service.d.ts.map