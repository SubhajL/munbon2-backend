"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.etoDataService = exports.EToDataService = void 0;
const database_1 = require("@config/database");
const logger_1 = require("@utils/logger");
class EToDataService {
    /**
     * Get monthly ETo value
     */
    async getMonthlyETo(aosStation = 'นครราชสีมา', province = 'นครราชสีมา', month) {
        try {
            const query = `
        SELECT eto_value 
        FROM eto_monthly 
        WHERE aos_station = $1 
          AND province = $2
          AND month = $3
      `;
            const result = await database_1.pool.query(query, [aosStation, province, month]);
            if (result.rows.length === 0) {
                throw new Error(`No ETo data found for ${aosStation}/${province} month ${month}`);
            }
            return parseFloat(result.rows[0].eto_value);
        }
        catch (error) {
            logger_1.logger.error('Failed to get monthly ETo', error);
            throw error;
        }
    }
    /**
     * Get all monthly ETo values for a station
     */
    async getAllMonthlyETo(aosStation = 'นครราชสีมา', province = 'นครราชสีมา') {
        try {
            const query = `
        SELECT month, eto_value 
        FROM eto_monthly 
        WHERE aos_station = $1 AND province = $2
        ORDER BY month
      `;
            const result = await database_1.pool.query(query, [aosStation, province]);
            return result.rows.map(row => ({
                month: row.month,
                etoValue: parseFloat(row.eto_value),
            }));
        }
        catch (error) {
            logger_1.logger.error('Failed to get all monthly ETo', error);
            throw error;
        }
    }
    /**
     * Calculate daily ETo from monthly value
     */
    calculateDailyETo(monthlyETo) {
        return monthlyETo / 30;
    }
    /**
     * Calculate weekly ETo from monthly value
     * Special handling for weeks that span months
     */
    calculateWeeklyETo(currentMonthETo, nextMonthETo, weekSpansMonths) {
        if (weekSpansMonths && nextMonthETo !== null) {
            return nextMonthETo / 4;
        }
        return currentMonthETo / 4;
    }
    /**
     * Upload ETo data from Excel (to be implemented)
     */
    async uploadEToData(data) {
        try {
            const query = `
        INSERT INTO eto_monthly (aos_station, province, month, eto_value)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (aos_station, province, month)
        DO UPDATE SET 
          eto_value = EXCLUDED.eto_value,
          updated_at = NOW()
      `;
            for (const row of data) {
                await database_1.pool.query(query, [
                    row.aosStation,
                    row.province,
                    row.month,
                    row.etoValue,
                ]);
            }
            logger_1.logger.info(`Uploaded ${data.length} ETo records`);
        }
        catch (error) {
            logger_1.logger.error('Failed to upload ETo data', error);
            throw error;
        }
    }
}
exports.EToDataService = EToDataService;
exports.etoDataService = new EToDataService();
//# sourceMappingURL=eto-data.service.js.map