#!/usr/bin/env ts-node
"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const database_1 = require("../src/config/database");
const fs_1 = require("fs");
const path_1 = require("path");
const chalk_1 = __importDefault(require("chalk"));
async function runMigration() {
    console.log(chalk_1.default.blue('🔄 Running effective rainfall migration...'));
    try {
        // Read SQL file
        const sqlPath = (0, path_1.resolve)(__dirname, 'add-effective-rainfall-table.sql');
        const sql = (0, fs_1.readFileSync)(sqlPath, 'utf8');
        // Execute the entire SQL file as one transaction
        console.log(chalk_1.default.yellow('📝 Executing SQL migration...'));
        try {
            await database_1.pool.query(sql);
            console.log(chalk_1.default.green('✅ Migration executed successfully'));
        }
        catch (error) {
            if (error.code === '42P07') { // Duplicate table
                console.log(chalk_1.default.yellow('⚠️  Some objects already exist, continuing...'));
            }
            else {
                console.error(chalk_1.default.red('❌ Error executing migration:'), error.message);
                throw error;
            }
        }
        // Verify the data was inserted
        console.log(chalk_1.default.blue('\n🔍 Verifying data...'));
        const result = await database_1.pool.query(`
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
        console.log(chalk_1.default.green('\n✅ Effective Rainfall Data Summary:'));
        console.table(result.rows);
        console.log(chalk_1.default.green('\n✅ Migration completed successfully!'));
    }
    catch (error) {
        console.error(chalk_1.default.red('❌ Migration failed:'), error);
    }
    finally {
        await database_1.pool.end();
    }
}
runMigration().catch(console.error);
//# sourceMappingURL=run-effective-rainfall-migration.js.map