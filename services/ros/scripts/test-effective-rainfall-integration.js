#!/usr/bin/env ts-node
"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const chalk_1 = __importDefault(require("chalk"));
const water_demand_service_1 = require("../src/services/water-demand.service");
const effective_rainfall_service_1 = require("../src/services/effective-rainfall.service");
const database_1 = require("../src/config/database");
async function testEffectiveRainfallIntegration() {
    console.log(chalk_1.default.blue('🧪 Testing Effective Rainfall Integration\n'));
    try {
        // Test 1: Direct effective rainfall service test
        console.log(chalk_1.default.yellow('Test 1: Direct Effective Rainfall Service'));
        console.log('='.repeat(50));
        // Test rice in May (month 5, high rainfall)
        const riceRainfall = await effective_rainfall_service_1.effectiveRainfallService.getEffectiveRainfall('rice', 20, // Week 20 (mid-May)
        2025);
        console.log('Rice in May:');
        console.log(`  Monthly: ${riceRainfall.monthlyEffectiveRainfall} mm`);
        console.log(`  Weekly: ${riceRainfall.weeklyEffectiveRainfall} mm`);
        console.log(`  Expected: 152.1 mm monthly, 38.03 mm weekly`);
        console.log(chalk_1.default.green(`  ✅ Match: ${Math.abs(riceRainfall.weeklyEffectiveRainfall - 38.03) < 0.1}`));
        // Test sugarcane in May
        const sugarcaneRainfall = await effective_rainfall_service_1.effectiveRainfallService.getEffectiveRainfall('sugarcane', 20, // Week 20 (mid-May)
        2025);
        console.log('\nSugarcane (field crop) in May:');
        console.log(`  Monthly: ${sugarcaneRainfall.monthlyEffectiveRainfall} mm`);
        console.log(`  Weekly: ${sugarcaneRainfall.weeklyEffectiveRainfall} mm`);
        console.log(`  Expected: 67.6 mm monthly, 16.90 mm weekly`);
        console.log(chalk_1.default.green(`  ✅ Match: ${Math.abs(sugarcaneRainfall.weeklyEffectiveRainfall - 16.90) < 0.1}`));
        // Test 2: Water demand calculation with effective rainfall
        console.log(chalk_1.default.yellow('\n\nTest 2: Water Demand with Effective Rainfall'));
        console.log('='.repeat(50));
        // Calculate water demand for rice
        const riceWaterDemand = await water_demand_service_1.waterDemandService.calculateWaterDemand({
            areaId: 'TEST-RICE-001',
            areaType: 'FTO',
            areaRai: 100,
            cropType: 'rice',
            cropWeek: 5,
            calendarWeek: 20,
            calendarYear: 2025
        });
        console.log('\nRice Water Demand (100 rai):');
        console.log(`  Gross demand: ${riceWaterDemand.cropWaterDemandMm.toFixed(2)} mm`);
        console.log(`  Effective rainfall: ${riceWaterDemand.effectiveRainfall?.toFixed(2)} mm`);
        console.log(`  Net demand: ${riceWaterDemand.netWaterDemandMm?.toFixed(2)} mm`);
        console.log(`  Net volume: ${riceWaterDemand.netWaterDemandM3?.toFixed(0)} m³`);
        // Calculate water demand for sugarcane
        const sugarcaneWaterDemand = await water_demand_service_1.waterDemandService.calculateWaterDemand({
            areaId: 'TEST-CANE-001',
            areaType: 'FTO',
            areaRai: 100,
            cropType: 'sugarcane',
            cropWeek: 5,
            calendarWeek: 20,
            calendarYear: 2025
        });
        console.log('\nSugarcane Water Demand (100 rai):');
        console.log(`  Gross demand: ${sugarcaneWaterDemand.cropWaterDemandMm.toFixed(2)} mm`);
        console.log(`  Effective rainfall: ${sugarcaneWaterDemand.effectiveRainfall?.toFixed(2)} mm`);
        console.log(`  Net demand: ${sugarcaneWaterDemand.netWaterDemandMm?.toFixed(2)} mm`);
        console.log(`  Net volume: ${sugarcaneWaterDemand.netWaterDemandM3?.toFixed(0)} m³`);
        // Test 3: Compare with old method
        console.log(chalk_1.default.yellow('\n\nTest 3: Rainfall Difference Analysis'));
        console.log('='.repeat(50));
        const rainfallDiff = riceWaterDemand.effectiveRainfall - sugarcaneWaterDemand.effectiveRainfall;
        console.log(`\nRainfall difference (Rice - Field Crops): ${rainfallDiff.toFixed(2)} mm/week`);
        console.log(`This means rice fields receive ${((rainfallDiff / sugarcaneWaterDemand.effectiveRainfall) * 100).toFixed(0)}% more effective rainfall`);
        // Test 4: Annual comparison
        console.log(chalk_1.default.yellow('\n\nTest 4: Annual Effective Rainfall Summary'));
        console.log('='.repeat(50));
        const annualResult = await database_1.pool.query(`
      SELECT 
        crop_type,
        SUM(effective_rainfall_mm) as annual_total,
        ROUND(SUM(effective_rainfall_mm) / 52, 2) as weekly_avg
      FROM ros.effective_rainfall_monthly
      WHERE aos_station = 'นครราชสีมา'
      GROUP BY crop_type
      ORDER BY crop_type
    `);
        console.table(annualResult.rows);
        console.log(chalk_1.default.green('\n✅ All tests completed successfully!'));
    }
    catch (error) {
        console.error(chalk_1.default.red('❌ Test failed:'), error);
    }
    finally {
        await database_1.pool.end();
    }
}
testEffectiveRainfallIntegration().catch(console.error);
//# sourceMappingURL=test-effective-rainfall-integration.js.map