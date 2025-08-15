#!/usr/bin/env ts-node
/**
 * Test script to demonstrate land preparation water calculation
 * Based on Excel data: น้ำเตรียมแปลง = 100 mm/season for rice
 */
interface LandPreparationExample {
    cropType: string;
    areaRai: number;
    preparationWaterMm: number;
    preparationWaterM3: number;
    totalSeasonalDemandMm: number;
    totalSeasonalDemandM3: number;
    landPrepPercentage: number;
}
declare function calculateWithLandPreparation(): void;
declare function compareWithoutLandPreparation(): void;
//# sourceMappingURL=test-land-preparation.d.ts.map