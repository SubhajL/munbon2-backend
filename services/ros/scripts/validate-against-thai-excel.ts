#!/usr/bin/env ts-node

import { waterDemandService } from '../src/services/water-demand.service';
import chalk from 'chalk';

interface ValidationCase {
  name: string;
  input: {
    areaRai: number;
    cropType: 'rice' | 'corn' | 'sugarcane';
    cropWeek: number;
    calendarWeek: number;
    calendarMonth: number;
  };
  expected: {
    monthlyETo: number;
    weeklyETo: number;
    kcValue: number;
    waterDemandMm: number;
    waterDemandM3: number;
  };
}

async function validateCalculations() {
  console.log(chalk.blue('=== Validating ROS Calculations Against Thai Excel ==='));

  const testCases: ValidationCase[] = [
    {
      name: 'Rice Week 5 in May (100 rai)',
      input: {
        areaRai: 100,
        cropType: 'rice',
        cropWeek: 5,
        calendarWeek: 19, // Mid-May
        calendarMonth: 5
      },
      expected: {
        monthlyETo: 145.08,
        weeklyETo: 36.27,
        kcValue: 1.38,
        waterDemandMm: 64.05,
        waterDemandM3: 10248
      }
    },
    {
      name: 'Rice Week 1 in January (100 rai)',
      input: {
        areaRai: 100,
        cropType: 'rice',
        cropWeek: 1,
        calendarWeek: 2, // Early January
        calendarMonth: 1
      },
      expected: {
        monthlyETo: 104.91,
        weeklyETo: 26.23,
        kcValue: 1.03,
        waterDemandMm: 41.01,
        waterDemandM3: 6562
      }
    },
    {
      name: 'Corn Week 7 in July (500 rai)',
      input: {
        areaRai: 500,
        cropType: 'corn',
        cropWeek: 7,
        calendarWeek: 28, // Mid-July
        calendarMonth: 7
      },
      expected: {
        monthlyETo: 132.53,
        weeklyETo: 33.13,
        kcValue: 1.61,
        waterDemandMm: 67.34,
        waterDemandM3: 53872
      }
    },
    {
      name: 'Sugarcane Week 10 in October (1000 rai)',
      input: {
        areaRai: 1000,
        cropType: 'sugarcane',
        cropWeek: 10,
        calendarWeek: 41, // Mid-October
        calendarMonth: 10
      },
      expected: {
        monthlyETo: 117.65,
        weeklyETo: 29.41,
        kcValue: 1.13,
        waterDemandMm: 47.23,
        waterDemandM3: 75568
      }
    }
  ];

  let passCount = 0;
  let failCount = 0;

  for (const testCase of testCases) {
    console.log(chalk.yellow(`\n📋 ${testCase.name}`));
    
    try {
      const result = await waterDemandService.calculateWaterDemand({
        areaId: 'VALIDATION-TEST',
        areaType: 'project',
        areaRai: testCase.input.areaRai,
        cropType: testCase.input.cropType,
        cropWeek: testCase.input.cropWeek,
        calendarWeek: testCase.input.calendarWeek,
        calendarYear: 2025,
        effectiveRainfall: 0,
        waterLevel: 220
      });

      // Validate each component
      console.log('\n  Results:');
      
      // Monthly ETo
      const etoMatch = Math.abs(parseFloat(result.monthlyETo.toString()) - testCase.expected.monthlyETo) < 0.01;
      console.log(`  Monthly ETo: ${result.monthlyETo} ${etoMatch ? '✅' : '❌'} (Expected: ${testCase.expected.monthlyETo})`);

      // Weekly ETo
      const weeklyEtoMatch = Math.abs(result.weeklyETo - testCase.expected.weeklyETo) < 0.01;
      console.log(`  Weekly ETo: ${result.weeklyETo.toFixed(2)} ${weeklyEtoMatch ? '✅' : '❌'} (Expected: ${testCase.expected.weeklyETo})`);

      // Kc Value
      const kcMatch = Math.abs(parseFloat(result.kcValue.toString()) - testCase.expected.kcValue) < 0.001;
      console.log(`  Kc Value: ${result.kcValue} ${kcMatch ? '✅' : '❌'} (Expected: ${testCase.expected.kcValue})`);

      // Water Demand mm
      const demandMmMatch = Math.abs(result.cropWaterDemandMm - testCase.expected.waterDemandMm) < 0.1;
      console.log(`  Water Demand: ${result.cropWaterDemandMm.toFixed(2)} mm ${demandMmMatch ? '✅' : '❌'} (Expected: ${testCase.expected.waterDemandMm} mm)`);

      // Water Demand m³
      const demandM3Match = Math.abs(result.cropWaterDemandM3 - testCase.expected.waterDemandM3) < 10;
      console.log(`  Volume: ${result.cropWaterDemandM3.toFixed(0)} m³ ${demandM3Match ? '✅' : '❌'} (Expected: ${testCase.expected.waterDemandM3} m³)`);

      // Formula verification
      console.log('\n  Formula Check:');
      const calculatedDemand = (result.weeklyETo * parseFloat(result.kcValue.toString())) + result.percolation;
      console.log(`  (${result.weeklyETo.toFixed(2)} × ${result.kcValue}) + ${result.percolation} = ${calculatedDemand.toFixed(2)} mm`);

      if (etoMatch && weeklyEtoMatch && kcMatch && demandMmMatch && demandM3Match) {
        console.log(chalk.green('\n  ✅ PASS - All values match!'));
        passCount++;
      } else {
        console.log(chalk.red('\n  ❌ FAIL - Some values do not match'));
        failCount++;
      }

    } catch (error) {
      console.error(chalk.red('  ❌ ERROR:'), error);
      failCount++;
    }
  }

  // Summary
  console.log(chalk.blue('\n=== Validation Summary ==='));
  console.log(`Total Tests: ${testCases.length}`);
  console.log(chalk.green(`Passed: ${passCount}`));
  console.log(chalk.red(`Failed: ${failCount}`));
  
  if (failCount === 0) {
    console.log(chalk.green('\n✅ All calculations match Thai Excel values!'));
  } else {
    console.log(chalk.red('\n❌ Some calculations do not match Thai Excel values'));
  }
}

// Run validation
if (require.main === module) {
  validateCalculations()
    .then(() => process.exit(0))
    .catch(error => {
      console.error(chalk.red('Fatal error:'), error);
      process.exit(1);
    });
}