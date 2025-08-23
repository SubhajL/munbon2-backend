export declare class EToDataService {
    /**
     * Get monthly ETo value
     */
    getMonthlyETo(aosStation: string, province: string, month: number): Promise<number>;
    /**
     * Get all monthly ETo values for a station
     */
    getAllMonthlyETo(aosStation?: string, province?: string): Promise<Array<{
        month: number;
        etoValue: number;
    }>>;
    /**
     * Calculate daily ETo from monthly value
     */
    calculateDailyETo(monthlyETo: number): number;
    /**
     * Calculate weekly ETo from monthly value
     * Special handling for weeks that span months
     */
    calculateWeeklyETo(currentMonthETo: number, nextMonthETo: number | null, weekSpansMonths: boolean): number;
    /**
     * Upload ETo data from Excel (to be implemented)
     */
    uploadEToData(data: Array<{
        aosStation: string;
        province: string;
        month: number;
        etoValue: number;
    }>): Promise<void>;
}
export declare const etoDataService: EToDataService;
//# sourceMappingURL=eto-data.service.d.ts.map