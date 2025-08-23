export declare class WeeklyEToService {
    /**
     * Get weekly ETo value from the weekly table
     * Falls back to monthly average if weekly not found
     */
    getWeeklyETo(calendarWeek: number, calendarYear: number, aosStation?: string, province?: string): Promise<number>;
    /**
     * Populate weekly ETo values from Excel data
     * This is for importing weekly-specific values
     */
    importWeeklyEToData(data: {
        calendarWeek: number;
        calendarYear: number;
        month: number;
        etoValue: number;
        aosStation?: string;
        province?: string;
    }[]): Promise<void>;
}
export declare const weeklyEToService: WeeklyEToService;
//# sourceMappingURL=weekly-eto.service.d.ts.map