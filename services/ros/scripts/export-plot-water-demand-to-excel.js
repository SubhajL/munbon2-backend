"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
const pg_1 = require("pg");
const XLSX = __importStar(require("xlsx"));
const fs = __importStar(require("fs"));
const path = __importStar(require("path"));
// Database connection
const pool = new pg_1.Pool({
    host: 'localhost',
    port: 5434,
    database: 'munbon_dev',
    user: 'postgres',
    password: 'postgres'
});
async function exportPlotWaterDemandToExcel() {
    try {
        console.log('Connecting to database...');
        // Query to get all water demand data with meaningful columns
        const query = `
      SELECT 
        plot_id,
        crop_type,
        crop_week,
        calendar_week,
        calendar_year,
        calculation_date,
        area_rai,
        monthly_eto,
        weekly_eto,
        kc_value,
        percolation,
        crop_water_demand_mm,
        crop_water_demand_m3,
        crop_water_demand_m3_per_rai,
        effective_rainfall_mm,
        net_water_demand_mm,
        net_water_demand_m3,
        net_water_demand_m3_per_rai,
        is_land_preparation
      FROM ros.plot_water_demand_weekly
      ORDER BY plot_id, crop_week
    `;
        console.log('Fetching data from ros.plot_water_demand_weekly...');
        const result = await pool.query(query);
        console.log(`Found ${result.rows.length} records`);
        // Convert to Excel format
        const workbook = XLSX.utils.book_new();
        // Main data sheet
        const worksheet = XLSX.utils.json_to_sheet(result.rows);
        XLSX.utils.book_append_sheet(workbook, worksheet, 'Plot Water Demand Weekly');
        // Add summary sheet
        const summaryQuery = `
      SELECT 
        COUNT(DISTINCT plot_id) as total_plots,
        COUNT(*) as total_records,
        MIN(calculation_date) as earliest_date,
        MAX(calculation_date) as latest_date,
        SUM(area_rai) as total_area_rai,
        SUM(crop_water_demand_m3) as total_crop_water_demand_m3,
        SUM(net_water_demand_m3) as total_net_water_demand_m3,
        AVG(crop_water_demand_m3_per_rai) as avg_crop_water_demand_per_rai,
        AVG(net_water_demand_m3_per_rai) as avg_net_water_demand_per_rai
      FROM ros.plot_water_demand_weekly
    `;
        const summaryResult = await pool.query(summaryQuery);
        const summarySheet = XLSX.utils.json_to_sheet(summaryResult.rows);
        XLSX.utils.book_append_sheet(workbook, summarySheet, 'Summary');
        // Add weekly summary
        const weeklyQuery = `
      SELECT 
        calendar_year,
        calendar_week,
        COUNT(DISTINCT plot_id) as plot_count,
        SUM(area_rai) as total_area_rai,
        SUM(crop_water_demand_m3) as total_water_demand_m3,
        SUM(net_water_demand_m3) as total_net_demand_m3,
        AVG(effective_rainfall_mm) as avg_rainfall_mm
      FROM ros.plot_water_demand_weekly
      GROUP BY calendar_year, calendar_week
      ORDER BY calendar_year, calendar_week
    `;
        const weeklyResult = await pool.query(weeklyQuery);
        const weeklySheet = XLSX.utils.json_to_sheet(weeklyResult.rows);
        XLSX.utils.book_append_sheet(workbook, weeklySheet, 'Weekly Summary');
        // Save the file
        const outputDir = path.join(__dirname, '../output');
        if (!fs.existsSync(outputDir)) {
            fs.mkdirSync(outputDir, { recursive: true });
        }
        const timestamp = new Date().toISOString().slice(0, 10);
        const filename = `plot_water_demand_weekly_${timestamp}.xlsx`;
        const filepath = path.join(outputDir, filename);
        XLSX.writeFile(workbook, filepath);
        console.log(`Excel file saved to: ${filepath}`);
        console.log(`Total records exported: ${result.rows.length}`);
    }
    catch (error) {
        console.error('Error exporting data:', error);
    }
    finally {
        await pool.end();
    }
}
// Run the export
exportPlotWaterDemandToExcel();
//# sourceMappingURL=export-plot-water-demand-to-excel.js.map