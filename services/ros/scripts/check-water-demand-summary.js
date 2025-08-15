#!/usr/bin/env ts-node
"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const database_1 = require("../src/config/database");
async function checkSummary() {
    try {
        // First check if data was inserted
        const countQuery = `
      SELECT COUNT(*) as count
      FROM ros.plot_water_demand_seasonal
      WHERE planting_date = '2025-07-04';
    `;
        const countResult = await database_1.pool.query(countQuery);
        console.log('Plots with seasonal data:', countResult.rows[0].count);
        // Check for any NULL or zero area_rai values
        const checkAreaQuery = `
      SELECT COUNT(*) as null_area_count
      FROM ros.plot_water_demand_seasonal
      WHERE planting_date = '2025-07-04' AND (area_rai IS NULL OR area_rai = 0);
    `;
        const checkAreaResult = await database_1.pool.query(checkAreaQuery);
        console.log('Plots with NULL or zero area:', checkAreaResult.rows[0].null_area_count);
        // Get total summary without division
        const totalQuery = `
      SELECT 
        SUM(area_rai) as total_area_rai,
        SUM(total_water_demand_m3) as total_water_demand_m3,
        SUM(total_net_water_demand_m3) as total_net_water_demand_m3
      FROM ros.plot_water_demand_seasonal
      WHERE crop_type = 'rice' AND planting_date = '2025-07-04';
    `;
        const totalResult = await database_1.pool.query(totalQuery);
        const totals = totalResult.rows[0];
        console.log('\nOverall Totals:');
        console.log('Total area:', parseFloat(totals.total_area_rai).toFixed(2), 'rai');
        console.log('Total water demand:', (parseFloat(totals.total_water_demand_m3) / 1000000).toFixed(2), 'million m³');
        console.log('Total net water demand:', (parseFloat(totals.total_net_water_demand_m3) / 1000000).toFixed(2), 'million m³');
        // Calculate average per rai manually
        if (totals.total_area_rai > 0) {
            const avgPerRai = totals.total_water_demand_m3 / totals.total_area_rai;
            console.log('Average demand per rai:', avgPerRai.toFixed(2), 'm³/rai');
        }
        process.exit(0);
    }
    catch (error) {
        console.error('Error:', error);
        process.exit(1);
    }
}
checkSummary();
//# sourceMappingURL=check-water-demand-summary.js.map