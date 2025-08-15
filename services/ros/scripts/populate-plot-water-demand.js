#!/usr/bin/env ts-node
"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const database_1 = require("../src/config/database");
const dayjs_1 = __importDefault(require("dayjs"));
const weekOfYear_1 = __importDefault(require("dayjs/plugin/weekOfYear"));
dayjs_1.default.extend(weekOfYear_1.default);
// Configuration
const PLANTING_DATE = '2025-07-04'; // July 4, 2025 (RID week 36 = Crop week 1)
const CROP_TYPE = 'rice';
const CROP_WEEKS = 13; // Corrected to match Excel
const BATCH_SIZE = 100;
async function getWeeklyETo(calendarWeek, calendarYear) {
    // Always use monthly ETo divided by 4 as per requirement
    const date = new Date(calendarYear, 0, 1);
    date.setDate(date.getDate() + (calendarWeek - 1) * 7);
    const month = date.getMonth() + 1;
    const monthlyQuery = `
    SELECT eto_value 
    FROM ros.eto_monthly 
    WHERE aos_station = 'นครราชสีมา' 
      AND province = 'นครราชสีมา'
      AND month = $1
  `;
    const monthlyResult = await database_1.pool.query(monthlyQuery, [month]);
    const monthlyETo = monthlyResult.rows[0] ? parseFloat(monthlyResult.rows[0].eto_value) : 0;
    // Monthly ETo divided by 4 to get weekly
    return monthlyETo / 4;
}
async function getKcValue(cropWeek) {
    const query = `
    SELECT kc_value 
    FROM ros.kc_weekly 
    WHERE crop_type = $1 AND crop_week = $2
  `;
    const result = await database_1.pool.query(query, [CROP_TYPE, cropWeek]);
    return parseFloat(result.rows[0]?.kc_value) || 0;
}
async function getEffectiveRainfall(month) {
    const query = `
    SELECT effective_rainfall_mm 
    FROM ros.effective_rainfall_monthly 
    WHERE aos_station = 'นครราชสีมา' 
      AND province = 'นครราชสีมา'
      AND month = $1
      AND crop_type = $2
  `;
    const result = await database_1.pool.query(query, [month, CROP_TYPE]);
    return parseFloat(result.rows[0]?.effective_rainfall_mm) || 0;
}
async function getLandPreparationWater() {
    const query = `
    SELECT preparation_water_mm 
    FROM ros.land_preparation_water 
    WHERE crop_type = $1
  `;
    const result = await database_1.pool.query(query, [CROP_TYPE]);
    return parseFloat(result.rows[0]?.preparation_water_mm) || 100; // Default 100mm for rice
}
async function calculateWeeklyDemand(cropWeek, plantingDate) {
    const PERCOLATION_MM_PER_WEEK = 14;
    const RAI_TO_M3_FACTOR = 1.6;
    // Calculate date for this crop week
    const weekDate = (0, dayjs_1.default)(plantingDate).add(cropWeek - 1, 'week');
    const month = weekDate.month() + 1;
    const calendarWeek = weekDate.week();
    const calendarYear = weekDate.year();
    // Get data
    const weeklyETo = await getWeeklyETo(calendarWeek, calendarYear);
    const kcValue = await getKcValue(cropWeek);
    const monthlyEffectiveRainfall = await getEffectiveRainfall(month);
    // Calculate weekly effective rainfall correctly (daily × 7)
    const daysInMonth = month === 2 ? 28 : (month === 4 || month === 6 || month === 9 || month === 11) ? 30 : 31;
    const dailyEffectiveRainfall = monthlyEffectiveRainfall / daysInMonth;
    const weeklyEffectiveRainfall = dailyEffectiveRainfall * 7;
    // Calculate water demand
    const cropWaterDemandMm = (weeklyETo * kcValue) + PERCOLATION_MM_PER_WEEK;
    const cropWaterDemandM3PerRai = cropWaterDemandMm * RAI_TO_M3_FACTOR;
    // Calculate net demand
    const netWaterDemandMm = Math.max(0, cropWaterDemandMm - weeklyEffectiveRainfall);
    const netWaterDemandM3PerRai = netWaterDemandMm * RAI_TO_M3_FACTOR;
    return {
        cropWeek,
        calendarWeek,
        calendarYear,
        monthlyETo: weeklyETo * 4, // Calculate monthly for display
        weeklyETo,
        kcValue,
        percolation: PERCOLATION_MM_PER_WEEK,
        cropWaterDemandMm,
        cropWaterDemandM3PerRai,
        effectiveRainfallMm: weeklyEffectiveRainfall,
        netWaterDemandMm,
        netWaterDemandM3PerRai,
    };
}
async function calculateLandPreparation(plantingDate) {
    const RAI_TO_M3_FACTOR = 1.6;
    // Land preparation is week 0 (1 week before planting)
    const prepDate = (0, dayjs_1.default)(plantingDate).subtract(1, 'week');
    const landPrepMm = await getLandPreparationWater();
    return {
        cropWeek: 0,
        calendarWeek: prepDate.week(),
        calendarYear: prepDate.year(),
        monthlyETo: 0,
        weeklyETo: 0,
        kcValue: 0,
        percolation: 0,
        cropWaterDemandMm: landPrepMm,
        cropWaterDemandM3PerRai: landPrepMm * RAI_TO_M3_FACTOR,
        effectiveRainfallMm: 0, // No rainfall reduction for land prep
        netWaterDemandMm: landPrepMm,
        netWaterDemandM3PerRai: landPrepMm * RAI_TO_M3_FACTOR,
    };
}
async function insertWeeklyDemand(plot, calc, plantingDate) {
    const query = `
    INSERT INTO ros.plot_water_demand_weekly (
      plot_id, crop_type, crop_week, calendar_week, calendar_year,
      calculation_date, area_rai, monthly_eto, weekly_eto, kc_value,
      percolation, crop_water_demand_mm, crop_water_demand_m3,
      effective_rainfall_mm, net_water_demand_mm, net_water_demand_m3,
      is_land_preparation
    ) VALUES (
      $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
      $11, $12, $13, $14, $15, $16, $17
    )
    ON CONFLICT (plot_id, crop_type, crop_week, calendar_year, calendar_week)
    DO UPDATE SET
      crop_water_demand_mm = EXCLUDED.crop_water_demand_mm,
      crop_water_demand_m3 = EXCLUDED.crop_water_demand_m3,
      effective_rainfall_mm = EXCLUDED.effective_rainfall_mm,
      net_water_demand_mm = EXCLUDED.net_water_demand_mm,
      net_water_demand_m3 = EXCLUDED.net_water_demand_m3;
  `;
    const values = [
        plot.plot_id,
        CROP_TYPE,
        calc.cropWeek,
        calc.calendarWeek,
        calc.calendarYear,
        new Date(),
        plot.area_rai,
        calc.monthlyETo,
        calc.weeklyETo,
        calc.kcValue,
        calc.percolation,
        calc.cropWaterDemandMm,
        calc.cropWaterDemandM3PerRai * plot.area_rai, // Total for plot
        calc.effectiveRainfallMm,
        calc.netWaterDemandMm,
        calc.netWaterDemandM3PerRai * plot.area_rai, // Total for plot
        calc.cropWeek === 0,
    ];
    await database_1.pool.query(query, values);
}
async function insertSeasonalSummary(plot, calculations, plantingDate) {
    // Calculate totals
    const totalWaterDemandMm = calculations.reduce((sum, calc) => sum + calc.cropWaterDemandMm, 0);
    const totalWaterDemandM3 = calculations.reduce((sum, calc) => sum + calc.cropWaterDemandM3PerRai * plot.area_rai, 0);
    const totalEffectiveRainfallMm = calculations.reduce((sum, calc) => sum + calc.effectiveRainfallMm, 0);
    const totalNetWaterDemandMm = calculations.reduce((sum, calc) => sum + calc.netWaterDemandMm, 0);
    const totalNetWaterDemandM3 = calculations.reduce((sum, calc) => sum + calc.netWaterDemandM3PerRai * plot.area_rai, 0);
    const landPrepCalc = calculations.find(c => c.cropWeek === 0);
    const harvestDate = (0, dayjs_1.default)(plantingDate).add(CROP_WEEKS, 'week').toDate();
    const query = `
    INSERT INTO ros.plot_water_demand_seasonal (
      plot_id, crop_type, planting_date, harvest_date, season, year,
      area_rai, total_crop_weeks, total_water_demand_mm, total_water_demand_m3,
      land_preparation_mm, land_preparation_m3, total_effective_rainfall_mm,
      total_net_water_demand_mm, total_net_water_demand_m3,
      includes_land_preparation, includes_rainfall
    ) VALUES (
      $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
      $11, $12, $13, $14, $15, $16, $17
    )
    ON CONFLICT (plot_id, crop_type, planting_date)
    DO UPDATE SET
      total_water_demand_mm = EXCLUDED.total_water_demand_mm,
      total_water_demand_m3 = EXCLUDED.total_water_demand_m3,
      total_effective_rainfall_mm = EXCLUDED.total_effective_rainfall_mm,
      total_net_water_demand_mm = EXCLUDED.total_net_water_demand_mm,
      total_net_water_demand_m3 = EXCLUDED.total_net_water_demand_m3,
      updated_at = NOW();
  `;
    const values = [
        plot.plot_id,
        CROP_TYPE,
        plantingDate,
        harvestDate,
        'wet', // July is wet season
        (0, dayjs_1.default)(plantingDate).year(),
        plot.area_rai,
        CROP_WEEKS,
        totalWaterDemandMm,
        totalWaterDemandM3,
        landPrepCalc?.cropWaterDemandMm || 0,
        landPrepCalc ? landPrepCalc.cropWaterDemandM3PerRai * plot.area_rai : 0,
        totalEffectiveRainfallMm,
        totalNetWaterDemandMm,
        totalNetWaterDemandM3,
        true, // includes_land_preparation
        true, // includes_rainfall
    ];
    await database_1.pool.query(query, values);
}
async function processPlots() {
    try {
        // Get all plots
        const plotsQuery = `
      SELECT plot_id, area_rai, parent_zone_id 
      FROM ros.plots 
      ORDER BY plot_id
    `;
        const plotsResult = await database_1.pool.query(plotsQuery);
        const plots = plotsResult.rows;
        console.log(`Found ${plots.length} plots to process`);
        const plantingDate = new Date(PLANTING_DATE);
        // Calculate all weeks once (same for all plots)
        console.log('Calculating weekly water demands...');
        const calculations = [];
        // Week 0: Land preparation
        const landPrep = await calculateLandPreparation(plantingDate);
        calculations.push(landPrep);
        // Weeks 1-16: Crop growth
        for (let week = 1; week <= CROP_WEEKS; week++) {
            const weekCalc = await calculateWeeklyDemand(week, plantingDate);
            calculations.push(weekCalc);
        }
        // Display sample calculation
        console.log('\nSample calculation (Week 5):');
        const week5 = calculations.find(c => c.cropWeek === 5);
        if (week5) {
            console.log(`- Monthly ETo: ${week5.monthlyETo.toFixed(2)} mm`);
            console.log(`- Weekly ETo: ${week5.weeklyETo.toFixed(2)} mm`);
            console.log(`- Kc value: ${week5.kcValue}`);
            console.log(`- Crop water demand: ${week5.cropWaterDemandMm.toFixed(2)} mm`);
            console.log(`- Water demand per rai: ${week5.cropWaterDemandM3PerRai.toFixed(2)} m³/rai`);
            console.log(`- Effective rainfall: ${week5.effectiveRainfallMm.toFixed(2)} mm`);
            console.log(`- Net water demand: ${week5.netWaterDemandMm.toFixed(2)} mm`);
            console.log(`- Net demand per rai: ${week5.netWaterDemandM3PerRai.toFixed(2)} m³/rai`);
        }
        // Process plots in batches
        console.log('\nProcessing plots in batches...');
        for (let i = 0; i < plots.length; i += BATCH_SIZE) {
            const batch = plots.slice(i, i + BATCH_SIZE);
            await Promise.all(batch.map(async (plot) => {
                try {
                    // Insert weekly data
                    for (const calc of calculations) {
                        await insertWeeklyDemand(plot, calc, plantingDate);
                    }
                    // Insert seasonal summary
                    await insertSeasonalSummary(plot, calculations, plantingDate);
                }
                catch (error) {
                    console.error(`Error processing plot ${plot.plot_id}:`, error);
                }
            }));
            const progress = Math.min(i + BATCH_SIZE, plots.length);
            console.log(`Processed ${progress}/${plots.length} plots (${(progress / plots.length * 100).toFixed(1)}%)`);
        }
        // Summary statistics
        console.log('\n=== Summary Statistics ===');
        const summaryQuery = `
      SELECT 
        p.parent_zone_id as zone,
        COUNT(*) as plot_count,
        SUM(pwd.area_rai) as total_area_rai,
        SUM(pwd.total_water_demand_m3) as total_water_demand_m3,
        SUM(pwd.total_net_water_demand_m3) as total_net_water_demand_m3,
        AVG(pwd.total_water_demand_m3 / pwd.area_rai) as avg_demand_per_rai
      FROM ros.plot_water_demand_seasonal pwd
      JOIN ros.plots p ON p.plot_id = pwd.plot_id
      WHERE pwd.crop_type = $1 AND pwd.planting_date = $2
      GROUP BY p.parent_zone_id
      ORDER BY p.parent_zone_id;
    `;
        const summaryResult = await database_1.pool.query(summaryQuery, [CROP_TYPE, plantingDate]);
        console.log('\nWater Demand by Zone:');
        console.log('Zone | Plots | Area (rai) | Total Demand (m³) | Net Demand (m³) | Avg/rai');
        console.log('-----|-------|------------|-------------------|-----------------|--------');
        let totalDemand = 0;
        let totalNetDemand = 0;
        summaryResult.rows.forEach(row => {
            console.log(`${row.zone.padEnd(4)} | ` +
                `${row.plot_count.toString().padStart(5)} | ` +
                `${parseFloat(row.total_area_rai).toFixed(0).padStart(10)} | ` +
                `${parseFloat(row.total_water_demand_m3).toFixed(0).padStart(17)} | ` +
                `${parseFloat(row.total_net_water_demand_m3).toFixed(0).padStart(15)} | ` +
                `${parseFloat(row.avg_demand_per_rai).toFixed(0).padStart(7)}`);
            totalDemand += parseFloat(row.total_water_demand_m3);
            totalNetDemand += parseFloat(row.total_net_water_demand_m3);
        });
        console.log('\nTotal water demand (all zones): ' + totalDemand.toFixed(0).toLocaleString() + ' m³');
        console.log('Total net water demand (after rainfall): ' + totalNetDemand.toFixed(0).toLocaleString() + ' m³');
        console.log('Rainfall reduction: ' + ((1 - totalNetDemand / totalDemand) * 100).toFixed(1) + '%');
        console.log('\nCalculation complete!');
    }
    catch (error) {
        console.error('Error processing plots:', error);
        throw error;
    }
}
// Main execution
async function main() {
    try {
        console.log('Plot Water Demand Calculation');
        console.log('=============================');
        console.log(`Crop: ${CROP_TYPE}`);
        console.log(`Planting date: ${PLANTING_DATE}`);
        console.log(`Crop duration: ${CROP_WEEKS} weeks + 1 week land preparation`);
        console.log('');
        await processPlots();
        process.exit(0);
    }
    catch (error) {
        console.error('Fatal error:', error);
        process.exit(1);
    }
}
main();
//# sourceMappingURL=populate-plot-water-demand.js.map