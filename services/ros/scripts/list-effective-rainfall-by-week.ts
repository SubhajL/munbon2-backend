#!/usr/bin/env ts-node

import { pool } from '../src/config/database';

async function listEffectiveRainfallByWeek() {
  try {
    console.log('Effective Rainfall by Crop Week');
    console.log('================================');
    console.log('Planting Date: July 4, 2025 (RID Week 36)');
    console.log('');
    
    // Get weekly effective rainfall from our calculations
    const query = `
      SELECT 
        crop_week,
        calendar_week,
        calendar_year,
        AVG(effective_rainfall_mm) as avg_rainfall_mm,
        MIN(effective_rainfall_mm) as min_rainfall_mm,
        MAX(effective_rainfall_mm) as max_rainfall_mm,
        COUNT(DISTINCT effective_rainfall_mm) as unique_values
      FROM ros.plot_water_demand_weekly
      WHERE crop_type = 'rice' 
        AND calendar_year = 2025
        AND crop_week BETWEEN 1 AND 13
      GROUP BY crop_week, calendar_week, calendar_year
      ORDER BY crop_week;
    `;
    
    const result = await pool.query(query);
    
    console.log('Crop | Calendar | Calendar | Effective    | Monthly Source');
    console.log('Week | Week     | Month    | Rainfall(mm) | (mm/month)');
    console.log('-----|----------|----------|--------------|---------------');
    
    for (const row of result.rows) {
      const cropWeek = row.crop_week;
      const calendarWeek = row.calendar_week;
      const effectiveRainfall = parseFloat(row.avg_rainfall_mm);
      
      // Determine which month this week falls in
      const date = new Date(2025, 0, 1);
      date.setDate(date.getDate() + (calendarWeek - 1) * 7);
      const month = date.getMonth() + 1;
      const monthName = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][month - 1];
      
      // Get the monthly value from database
      const monthQuery = `
        SELECT effective_rainfall_mm 
        FROM ros.effective_rainfall_monthly
        WHERE month = $1 AND crop_type = 'rice'
        AND aos_station = 'นครราชสีมา';
      `;
      const monthResult = await pool.query(monthQuery, [month]);
      const monthlyRainfall = parseFloat(monthResult.rows[0]?.effective_rainfall_mm || '0');
      
      console.log(
        `  ${cropWeek.toString().padStart(2)} | ` +
        `    ${calendarWeek.toString().padStart(2)}    | ` +
        `${month.toString().padStart(2)}-${monthName}    | ` +
        `${effectiveRainfall.toFixed(2).padStart(11)} | ` +
        `${monthlyRainfall.toFixed(2).padStart(7)}`
      );
    }
    
    console.log('');
    console.log('Calculation Method:');
    console.log('- Weekly Rainfall = (Monthly Rainfall ÷ Days in Month) × 7');
    console.log('');
    console.log('Monthly Values Used:');
    const monthlyQuery = `
      SELECT month, effective_rainfall_mm
      FROM ros.effective_rainfall_monthly
      WHERE crop_type = 'rice' 
      AND aos_station = 'นครราชสีมา'
      AND month IN (7, 8, 9, 10)
      ORDER BY month;
    `;
    
    const monthlyResult = await pool.query(monthlyQuery);
    console.log('Month | Monthly (mm) | Daily (mm) | Weekly (mm)');
    console.log('------|--------------|------------|------------');
    
    monthlyResult.rows.forEach(row => {
      const month = row.month;
      const monthlyMm = parseFloat(row.effective_rainfall_mm);
      const daysInMonth = month === 2 ? 28 : [4,6,9,11].includes(month) ? 30 : 31;
      const dailyMm = monthlyMm / daysInMonth;
      const weeklyMm = dailyMm * 7;
      
      const monthName = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][month - 1];
      
      console.log(
        `${month.toString().padStart(2)}-${monthName} | ` +
        `${monthlyMm.toFixed(2).padStart(11)} | ` +
        `${dailyMm.toFixed(3).padStart(10)} | ` +
        `${weeklyMm.toFixed(2).padStart(10)}`
      );
    });
    
    process.exit(0);
  } catch (error) {
    console.error('Error:', error);
    process.exit(1);
  }
}

listEffectiveRainfallByWeek();