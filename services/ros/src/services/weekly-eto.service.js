"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.weeklyEToService = exports.WeeklyEToService = void 0;
const database_1 = require("@config/database");
const logger_1 = require("@utils/logger");
class WeeklyEToService {
    /**
     * Get weekly ETo value from the weekly table
     * Falls back to monthly average if weekly not found
     */
    async getWeeklyETo(calendarWeek, calendarYear, aosStation = 'นครราชสีมา', province = 'นครราชสีมา') {
        try {
            // First try to get from weekly table
            const weeklyQuery = `
        SELECT eto_value 
        FROM ros.eto_weekly 
        WHERE aos_station = $1 
          AND province = $2
          AND calendar_week = $3
          AND calendar_year = $4
      `;
            const weeklyResult = await database_1.pool.query(weeklyQuery, [
                aosStation,
                province,
                calendarWeek,
                calendarYear
            ]);
            if (weeklyResult.rows.length > 0) {
                return parseFloat(weeklyResult.rows[0].eto_value);
            }
            // Fall back to monthly average
            logger_1.logger.warn(`No weekly ETo found for week ${calendarWeek} of ${calendarYear}, falling back to monthly average`);
            // Determine month from week number
            const date = new Date(calendarYear, 0, 1);
            date.setDate(date.getDate() + (calendarWeek - 1) * 7);
            const month = date.getMonth() + 1;
            const monthlyQuery = `
        SELECT eto_value 
        FROM ros.eto_monthly 
        WHERE aos_station = $1 
          AND province = $2
          AND month = $3
      `;
            const monthlyResult = await database_1.pool.query(monthlyQuery, [
                aosStation,
                province,
                month
            ]);
            if (monthlyResult.rows.length > 0) {
                // Return monthly value divided by 4 for weekly average
                return parseFloat(monthlyResult.rows[0].eto_value) / 4;
            }
            throw new Error(`No ETo data found for week ${calendarWeek} of ${calendarYear}`);
        }
        catch (error) {
            logger_1.logger.error('Failed to get weekly ETo', error);
            throw error;
        }
    }
    /**
     * Populate weekly ETo values from Excel data
     * This is for importing weekly-specific values
     */
    async importWeeklyEToData(data) {
        const client = await database_1.pool.connect();
        try {
            await client.query('BEGIN');
            for (const record of data) {
                const query = `
          INSERT INTO ros.eto_weekly (
            aos_station, province, calendar_week, calendar_year, month, eto_value
          ) VALUES ($1, $2, $3, $4, $5, $6)
          ON CONFLICT (aos_station, province, calendar_week, calendar_year)
          DO UPDATE SET 
            eto_value = EXCLUDED.eto_value,
            month = EXCLUDED.month,
            updated_at = NOW()
        `;
                await client.query(query, [
                    record.aosStation || 'นครราชสีมา',
                    record.province || 'นครราชสีมา',
                    record.calendarWeek,
                    record.calendarYear,
                    record.month,
                    record.etoValue
                ]);
            }
            await client.query('COMMIT');
            logger_1.logger.info(`Imported ${data.length} weekly ETo records`);
        }
        catch (error) {
            await client.query('ROLLBACK');
            logger_1.logger.error('Failed to import weekly ETo data', error);
            throw error;
        }
        finally {
            client.release();
        }
    }
}
exports.WeeklyEToService = WeeklyEToService;
exports.weeklyEToService = new WeeklyEToService();
//# sourceMappingURL=weekly-eto.service.js.map