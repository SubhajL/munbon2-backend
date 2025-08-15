#!/usr/bin/env ts-node
/**
 * Example script to demonstrate water demand calculation using ROS service
 * This shows how to calculate water demand based on:
 * - ETo (Reference Evapotranspiration)
 * - Kc (Crop Coefficient)
 * - Area in Rai
 * - Effective Rainfall (optional)
 * - Water Level (optional)
 */
interface WaterDemandCalculation {
    cropType: string;
    cropWeek: number;
    areaRai: number;
    monthlyETo: number;
    kcValue: number;
    percolation: number;
    effectiveRainfall?: number;
    weeklyETo: number;
    cropWaterDemandMm: number;
    cropWaterDemandM3: number;
    netWaterDemandMm?: number;
    netWaterDemandM3?: number;
}
/**
 * Calculate water demand using FAO method
 */
declare function calculateWaterDemand(params: {
    cropType: string;
    cropWeek: number;
    areaRai: number;
    monthlyETo: number;
    kcValue: number;
    effectiveRainfall?: number;
}): WaterDemandCalculation;
/**
 * Example: Rice cultivation in May (wet season)
 */
declare function exampleRiceWaterDemand(): void;
/**
 * Example: Sugarcane cultivation calculation
 */
declare function exampleSugarcaneWaterDemand(): void;
/**
 * Example: Calculate seasonal water demand
 */
declare function calculateSeasonalDemand(): void;
//# sourceMappingURL=calculate-water-demand-example.d.ts.map