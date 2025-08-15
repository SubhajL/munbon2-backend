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

function calculateWithLandPreparation(): void {
  console.log('=== Water Demand Calculation WITH Land Preparation ===\n');
  
  // Constants
  const RAI_TO_M3_FACTOR = 1.6;
  
  // Land preparation values from Excel
  const landPrepData = {
    rice: 100,      // mm/season (from Excel น้ำเตรียมแปลง)
    corn: 50,       // mm/season (estimated)
    sugarcane: 50   // mm/season (estimated)
  };

  // Example 1: Rice 1,000 rai
  console.log('Example 1: Rice Cultivation (1,000 rai)');
  console.log('----------------------------------------');
  
  const riceLandPrep = landPrepData.rice;
  const riceArea = 1000;
  const riceLandPrepM3 = riceLandPrep * riceArea * RAI_TO_M3_FACTOR;
  
  // Seasonal demand (from previous calculation)
  const riceSeasonalDemandMm = 922.5;  // 16 weeks of crop growth
  const riceSeasonalDemandM3 = 1476040;
  
  // Total with land preparation
  const riceTotalMm = riceLandPrep + riceSeasonalDemandMm;
  const riceTotalM3 = riceLandPrepM3 + riceSeasonalDemandM3;
  const riceLandPrepPercent = (riceLandPrep / riceTotalMm) * 100;
  
  console.log(`Land Preparation:`);
  console.log(`  - Water required: ${riceLandPrep} mm`);
  console.log(`  - Volume: ${riceLandPrepM3.toLocaleString()} m³`);
  console.log(`  - Duration: 1 week before planting`);
  console.log(`\nCrop Growth (16 weeks):`);
  console.log(`  - Water required: ${riceSeasonalDemandMm} mm`);
  console.log(`  - Volume: ${riceSeasonalDemandM3.toLocaleString()} m³`);
  console.log(`\nTotal Season Requirement:`);
  console.log(`  - Total water: ${riceTotalMm.toFixed(1)} mm`);
  console.log(`  - Total volume: ${riceTotalM3.toLocaleString()} m³`);
  console.log(`  - Land prep is ${riceLandPrepPercent.toFixed(1)}% of total\n`);

  // Example 2: Comparison of all crops
  console.log('Example 2: Land Preparation Comparison');
  console.log('--------------------------------------');
  console.log('Crop       | Area (rai) | Prep (mm) | Prep (m³)    | % of Total');
  console.log('-----------|------------|-----------|--------------|------------');
  
  const crops = [
    { 
      type: 'Rice', 
      area: 1000, 
      prepMm: landPrepData.rice,
      seasonalMm: 922.5 
    },
    { 
      type: 'Corn', 
      area: 500, 
      prepMm: landPrepData.corn,
      seasonalMm: 750.0  // Estimated
    },
    { 
      type: 'Sugarcane', 
      area: 200, 
      prepMm: landPrepData.sugarcane,
      seasonalMm: 1500.0  // Estimated for 52 weeks
    }
  ];

  crops.forEach(crop => {
    const prepM3 = crop.prepMm * crop.area * RAI_TO_M3_FACTOR;
    const totalMm = crop.prepMm + crop.seasonalMm;
    const prepPercent = (crop.prepMm / totalMm) * 100;
    
    console.log(
      `${crop.type.padEnd(10)} | ` +
      `${crop.area.toString().padStart(10)} | ` +
      `${crop.prepMm.toString().padStart(9)} | ` +
      `${prepM3.toLocaleString().padStart(12)} | ` +
      `${prepPercent.toFixed(1).padStart(10)}%`
    );
  });

  console.log('\n=== Weekly Schedule Example (Rice) ===');
  console.log('Week | Phase              | Water Demand (mm) | Volume (m³)');
  console.log('-----|--------------------|--------------------|-------------');
  console.log('  0  | Land Preparation   |             100.0  |     160,000');
  console.log('  1  | Initial Stage      |              41.0  |      65,600');
  console.log('  2  | Initial Stage      |              41.8  |      66,880');
  console.log('  3  | Initial Stage      |              42.3  |      67,680');
  console.log('  4  | Initial Stage      |              48.9  |      78,240');
  console.log('  5  | Development        |              56.9  |      91,040');
  console.log(' ... | ...                |              ...   |         ...');
  console.log(' 16  | Late Season        |              48.7  |      77,920');
  console.log('-----|--------------------|--------------------|-------------');
  console.log('Total|                    |           1,022.5  |   1,636,040');
}

function compareWithoutLandPreparation(): void {
  console.log('\n\n=== Comparison: With vs Without Land Preparation ===\n');
  
  const scenarios = [
    { crop: 'Rice', area: 1000, prepMm: 100, seasonalMm: 922.5 },
    { crop: 'Rice', area: 5000, prepMm: 100, seasonalMm: 922.5 },
    { crop: 'Rice', area: 10000, prepMm: 100, seasonalMm: 922.5 }
  ];

  console.log('Area (rai) | Without Prep (m³) | With Prep (m³) | Difference (m³) | % Increase');
  console.log('-----------|-------------------|----------------|-----------------|------------');

  scenarios.forEach(s => {
    const withoutPrepM3 = s.seasonalMm * s.area * 1.6;
    const prepM3 = s.prepMm * s.area * 1.6;
    const withPrepM3 = withoutPrepM3 + prepM3;
    const diffM3 = prepM3;
    const percentIncrease = (prepM3 / withoutPrepM3) * 100;

    console.log(
      `${s.area.toLocaleString().padStart(10)} | ` +
      `${withoutPrepM3.toLocaleString().padStart(17)} | ` +
      `${withPrepM3.toLocaleString().padStart(14)} | ` +
      `${diffM3.toLocaleString().padStart(15)} | ` +
      `${percentIncrease.toFixed(1).padStart(10)}%`
    );
  });

  console.log('\nKey Findings:');
  console.log('- Land preparation adds 100 mm (160 m³/rai) for rice');
  console.log('- This represents approximately 10.8% additional water requirement');
  console.log('- Must be delivered 1 week before planting');
  console.log('- Critical for soil saturation and puddling in rice fields');
}

// Run examples
console.log('Land Preparation Water Demand Analysis');
console.log('Based on ROS Excel data: น้ำเตรียมแปลง\n');

calculateWithLandPreparation();
compareWithoutLandPreparation();

console.log('\n\nNote: Land preparation water is essential for:');
console.log('- Rice: Soil saturation, puddling, and initial flooding');
console.log('- Corn/Sugarcane: Pre-irrigation for optimal planting conditions');
console.log('\nThis water must be available BEFORE the crop season begins.');