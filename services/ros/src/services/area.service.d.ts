import { AreaInfo, AreaType } from '@types/index';
export declare class AreaService {
    /**
     * Create a new area
     */
    createArea(area: AreaInfo): Promise<AreaInfo>;
    /**
     * Get area by ID
     */
    getAreaById(areaId: string): Promise<AreaInfo | null>;
    /**
     * Get all areas by type
     */
    getAreasByType(areaType: AreaType): Promise<AreaInfo[]>;
    /**
     * Get child areas of a parent
     */
    getChildAreas(parentAreaId: string): Promise<AreaInfo[]>;
    /**
     * Update area information
     */
    updateArea(areaId: string, updates: Partial<AreaInfo>): Promise<AreaInfo | null>;
    /**
     * Get area hierarchy (project -> zones -> sections)
     */
    getAreaHierarchy(projectId: string): Promise<any>;
    /**
     * Calculate total area for a parent (sum of child areas)
     */
    calculateTotalArea(parentAreaId: string): Promise<number>;
    /**
     * Delete area (cascade to child areas)
     */
    deleteArea(areaId: string): Promise<boolean>;
    /**
     * Import areas from data
     */
    importAreas(areas: AreaInfo[]): Promise<{
        success: number;
        failed: number;
    }>;
    /**
     * Get area statistics
     */
    getAreaStatistics(): Promise<{
        totalProjects: number;
        totalZones: number;
        totalSections: number;
        totalAreaRai: number;
    }>;
    /**
     * Map database row to AreaInfo
     */
    private mapRowToAreaInfo;
}
export declare const areaService: AreaService;
//# sourceMappingURL=area.service.d.ts.map