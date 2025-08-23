export declare class ET0Service {
    /**
     * Get ET0 value for a specific date and period
     */
    getET0(date: Date, period: 'daily' | 'weekly' | 'monthly'): Promise<number>;
    /**
     * Convert monthly ET0 to different periods
     */
    private convertET0ToPeriod;
    /**
     * Get default ET0 values by month (mm/month)
     */
    private getDefaultET0;
    /**
     * Import ET0 data from Excel structure
     */
    importET0Data(data: Array<{
        location?: string;
        year: number;
        month: number;
        et0Value: number;
        source?: string;
    }>): Promise<void>;
    /**
     * Calculate ET0 using Penman-Monteith (future enhancement)
     */
    calculateET0PenmanMonteith(params: {
        temperature: number;
        humidity: number;
        windSpeed: number;
        solarRadiation: number;
        latitude: number;
        elevation: number;
        date: Date;
    }): Promise<number>;
    /**
     * Get annual ET0 pattern
     */
    getAnnualET0Pattern(year?: number): Promise<Array<{
        month: number;
        monthName: string;
        et0: number;
    }>>;
}
export declare const et0Service: ET0Service;
//# sourceMappingURL=et0Service.d.ts.map