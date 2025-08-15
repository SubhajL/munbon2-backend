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
  // Input parameters
  cropType: string;
  cropWeek: number;
  areaRai: number;
  monthlyETo: number;
  kcValue: number;
  percolation: number;
  effectiveRainfall?: number;

  // Calculated values
  weeklyETo: number;
  cropWaterDemandMm: number;
  cropWaterDemandM3: number;
  netWaterDemandMm?: number;
  netWaterDemandM3?: number;
}

/**
 * Calculate water demand using FAO method
 */
function calculateWaterDemand(params: {
  cropType: string;
  cropWeek: number;
  areaRai: number;
  monthlyETo: number;
  kcValue: number;
  effectiveRainfall?: number;
}): WaterDemandCalculation {
  // Constants
  const PERCOLATION_MM_PER_WEEK = 14; // mm/week for clay soil
  const RAI_TO_M3_FACTOR = 1.6; // 1 rai = 1,600 m²; 1 mm = 0.001 m = 1.6 m³/rai

  // Calculate weekly ETo from monthly value
  const weeklyETo = params.monthlyETo / 4;

  // Calculate crop water demand
  // Formula: (ETo × Kc) + Percolation
  const cropWaterDemandMm = (weeklyETo * params.kcValue) + PERCOLATION_MM_PER_WEEK;
  
  // Convert to cubic meters
  const cropWaterDemandM3 = cropWaterDemandMm * params.areaRai * RAI_TO_M3_FACTOR;

  // Calculate net water demand if rainfall data is available
  let netWaterDemandMm: number | undefined;
  let netWaterDemandM3: number | undefined;
  
  if (params.effectiveRainfall !== undefined) {
    netWaterDemandMm = Math.max(0, cropWaterDemandMm - params.effectiveRainfall);
    netWaterDemandM3 = netWaterDemandMm * params.areaRai * RAI_TO_M3_FACTOR;
  }

  return {
    cropType: params.cropType,
    cropWeek: params.cropWeek,
    areaRai: params.areaRai,
    monthlyETo: params.monthlyETo,
    kcValue: params.kcValue,
    percolation: PERCOLATION_MM_PER_WEEK,
    effectiveRainfall: params.effectiveRainfall,
    weeklyETo,
    cropWaterDemandMm,
    cropWaterDemandM3,
    netWaterDemandMm,
    netWaterDemandM3,
  };
}

/**
 * Example: Rice cultivation in May (wet season)
 */
function exampleRiceWaterDemand() {
  console.log('=== Rice Water Demand Calculation Example ===\n');

  // Example parameters for rice in May (Week 5 of crop growth)
  const params = {
    cropType: 'rice',
    cropWeek: 5,
    areaRai: 1000, // 1,000 rai field
    monthlyETo: 156.0, // May ETo for Nakhon Ratchasima (mm/month)
    kcValue: 1.10, // Kc for rice week 5 (development stage)
    effectiveRainfall: 5.2, // Effective rainfall in mm/week
  };

  const result = calculateWaterDemand(params);

  console.log('Input Parameters:');
  console.log(`- Crop Type: ${result.cropType}`);
  console.log(`- Crop Week: ${result.cropWeek}`);
  console.log(`- Area: ${result.areaRai.toLocaleString()} rai`);
  console.log(`- Monthly ETo: ${result.monthlyETo} mm`);
  console.log(`- Kc Value: ${result.kcValue}`);
  console.log(`- Effective Rainfall: ${result.effectiveRainfall} mm/week`);
  console.log('\nCalculated Values:');
  console.log(`- Weekly ETo: ${result.weeklyETo.toFixed(1)} mm`);
  console.log(`- Crop Water Demand: ${result.cropWaterDemandMm.toFixed(1)} mm/week`);
  console.log(`- Crop Water Demand: ${result.cropWaterDemandM3.toLocaleString()} m³/week`);
  console.log(`- Net Water Demand: ${result.netWaterDemandMm?.toFixed(1)} mm/week`);
  console.log(`- Net Water Demand: ${result.netWaterDemandM3?.toLocaleString()} m³/week`);
  console.log('\n' + '='.repeat(50) + '\n');
}

/**
 * Example: Sugarcane cultivation calculation
 */
function exampleSugarcaneWaterDemand() {
  console.log('=== Sugarcane Water Demand Calculation Example ===\n');

  const params = {
    cropType: 'sugarcane',
    cropWeek: 20, // Mid-season stage
    areaRai: 500,
    monthlyETo: 148.8, // July ETo
    kcValue: 1.25, // Kc for sugarcane mid-season
    effectiveRainfall: 15.3, // Higher rainfall in July
  };

  const result = calculateWaterDemand(params);

  console.log('Input Parameters:');
  console.log(`- Crop Type: ${result.cropType}`);
  console.log(`- Crop Week: ${result.cropWeek}`);
  console.log(`- Area: ${result.areaRai.toLocaleString()} rai`);
  console.log(`- Monthly ETo: ${result.monthlyETo} mm`);
  console.log(`- Kc Value: ${result.kcValue}`);
  console.log(`- Effective Rainfall: ${result.effectiveRainfall} mm/week`);
  console.log('\nCalculated Values:');
  console.log(`- Weekly ETo: ${result.weeklyETo.toFixed(1)} mm`);
  console.log(`- Crop Water Demand: ${result.cropWaterDemandMm.toFixed(1)} mm/week`);
  console.log(`- Crop Water Demand: ${result.cropWaterDemandM3.toLocaleString()} m³/week`);
  console.log(`- Net Water Demand: ${result.netWaterDemandMm?.toFixed(1)} mm/week`);
  console.log(`- Net Water Demand: ${result.netWaterDemandM3?.toLocaleString()} m³/week`);
  console.log('\n' + '='.repeat(50) + '\n');
}

/**
 * Example: Calculate seasonal water demand
 */
function calculateSeasonalDemand() {
  console.log('=== Seasonal Water Demand Calculation (Rice - 16 weeks) ===\n');

  const areaRai = 1000;
  let totalCropDemand = 0;
  let totalNetDemand = 0;
  let totalRainfall = 0;

  // Simulate 16 weeks of rice cultivation
  const riceCropWeeks = 16;
  const kcValues = [
    1.05, 1.05, 1.05, 1.05, // Initial stage (4 weeks)
    1.10, 1.15, 1.20, 1.20, // Development stage (4 weeks)
    1.20, 1.20, 1.20, 1.20, // Mid-season stage (4 weeks)
    1.15, 1.10, 1.00, 0.90  // Late season stage (4 weeks)
  ];

  console.log('Week | Kc   | ETo  | Demand(mm) | Rain(mm) | Net(mm) | Net(m³)');
  console.log('-'.repeat(65));

  for (let week = 1; week <= riceCropWeeks; week++) {
    // Simulate changing ETo and rainfall through the season
    const monthlyETo = 140 + (week * 2); // Increases through season
    const effectiveRainfall = Math.max(0, 20 - week); // Decreases through season

    const result = calculateWaterDemand({
      cropType: 'rice',
      cropWeek: week,
      areaRai,
      monthlyETo,
      kcValue: kcValues[week - 1],
      effectiveRainfall,
    });

    totalCropDemand += result.cropWaterDemandMm;
    totalNetDemand += result.netWaterDemandMm || 0;
    totalRainfall += effectiveRainfall;

    console.log(
      `${week.toString().padStart(3)} | ` +
      `${result.kcValue.toFixed(2)} | ` +
      `${result.weeklyETo.toFixed(0).padStart(4)} | ` +
      `${result.cropWaterDemandMm.toFixed(1).padStart(10)} | ` +
      `${effectiveRainfall.toFixed(1).padStart(8)} | ` +
      `${(result.netWaterDemandMm || 0).toFixed(1).padStart(7)} | ` +
      `${(result.netWaterDemandM3 || 0).toLocaleString().padStart(10)}`
    );
  }

  console.log('-'.repeat(65));
  console.log('\nSeasonal Summary:');
  console.log(`- Total Crop Water Demand: ${totalCropDemand.toFixed(1)} mm`);
  console.log(`- Total Crop Water Demand: ${(totalCropDemand * areaRai * 1.6).toLocaleString()} m³`);
  console.log(`- Total Effective Rainfall: ${totalRainfall.toFixed(1)} mm`);
  console.log(`- Total Net Water Demand: ${totalNetDemand.toFixed(1)} mm`);
  console.log(`- Total Net Water Demand: ${(totalNetDemand * areaRai * 1.6).toLocaleString()} m³`);
}

// Run examples
console.log('Water Demand Calculation Examples - ROS Service\n');
console.log('Formula: Water Demand = (Weekly ETo × Kc) + Percolation - Effective Rainfall\n');

exampleRiceWaterDemand();
exampleSugarcaneWaterDemand();
calculateSeasonalDemand();

console.log('\nNote: These calculations follow FAO-56 guidelines for irrigation water requirements.');
console.log('Actual values should be obtained from the ROS database for specific locations and dates.');