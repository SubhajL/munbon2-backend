#!/usr/bin/env ts-node

import { pool } from '../src/config/database';
import { readFileSync } from 'fs';
import { resolve } from 'path';
import chalk from 'chalk';

async function runMigration() {
  console.log(chalk.blue('🔄 Running effective rainfall migration...'));
  
  try {
    // Read SQL file
    const sqlPath = resolve(__dirname, 'add-effective-rainfall-table.sql');
    const sql = readFileSync(sqlPath, 'utf8');
    
    // Execute the entire SQL file as one transaction
    console.log(chalk.yellow('📝 Executing SQL migration...'));
    
    try {
      await pool.query(sql);
      console.log(chalk.green('✅ Migration executed successfully'));
    } catch (error: any) {
      if (error.code === '42P07') { // Duplicate table
        console.log(chalk.yellow('⚠️  Some objects already exist, continuing...'));
      } else {
        console.error(chalk.red('❌ Error executing migration:'), error.message);
        throw error;
      }
    }
    
    // Verify the data was inserted
    console.log(chalk.blue('\n🔍 Verifying data...'));
    
    const result = await pool.query(`
      SELECT 
        crop_type,
        COUNT(*) as months,
        SUM(effective_rainfall_mm) as annual_total,
        ROUND(AVG(effective_rainfall_mm), 2) as monthly_avg
      FROM ros.effective_rainfall_monthly
      WHERE aos_station = 'นครราชสีมา'
      GROUP BY crop_type
      ORDER BY crop_type
    `);
    
    console.log(chalk.green('\n✅ Effective Rainfall Data Summary:'));
    console.table(result.rows);
    
    console.log(chalk.green('\n✅ Migration completed successfully!'));
    
  } catch (error) {
    console.error(chalk.red('❌ Migration failed:'), error);
  } finally {
    await pool.end();
  }
}

runMigration().catch(console.error);