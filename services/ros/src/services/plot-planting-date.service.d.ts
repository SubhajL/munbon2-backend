import { PlotInfo, PlotCropSchedule, UpdatePlotPlantingDateInput, BatchUpdatePlantingDatesInput, PlotCurrentCropView } from '@/types/plot.types';
declare class PlotPlantingDateService {
    /**
     * Update planting date for a single plot
     */
    updatePlotPlantingDate(input: UpdatePlotPlantingDateInput): Promise<PlotInfo>;
    /**
     * Batch update planting dates for multiple plots
     */
    batchUpdatePlantingDates(input: BatchUpdatePlantingDatesInput): Promise<number>;
    /**
     * Get plots by planting date range
     */
    getPlotsByPlantingDateRange(startDate: Date, endDate: Date, zoneId?: string): Promise<PlotCurrentCropView[]>;
    /**
     * Get upcoming planting schedules
     */
    getUpcomingPlantingSchedules(daysAhead?: number): Promise<PlotCropSchedule[]>;
    /**
     * Update crop status (e.g., from active to harvested)
     */
    updateCropStatus(plotId: string, status: string): Promise<void>;
    /**
     * Get plots ready for harvest
     */
    getPlotsReadyForHarvest(daysWindow?: number): Promise<PlotCurrentCropView[]>;
}
export declare const plotPlantingDateService: PlotPlantingDateService;
export {};
//# sourceMappingURL=plot-planting-date.service.d.ts.map