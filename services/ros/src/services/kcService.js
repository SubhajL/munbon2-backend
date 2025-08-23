"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.kcService = exports.KcService = void 0;
const logger_1 = require("../utils/logger");
const errorHandler_1 = require("../middleware/errorHandler");
const kcModel_1 = require("../models/kcModel");
class KcService {
    /**
     * Get Kc value for a specific crop and growth week
     */
    async getKc(cropType, growthWeek) {
        try {
            // First try to get from database
            const kcData = await kcModel_1.KcModel.findOne({
                cropType: cropType,
                growthWeek: growthWeek
            });
            if (kcData) {
                return kcData.kcValue;
            }
            // If not found, use default values
            return this.getDefaultKc(cropType, growthWeek);
        }
        catch (error) {
            logger_1.logger.error('Error getting Kc value:', error);
            throw new errorHandler_1.AppError('Failed to retrieve Kc value', 500);
        }
    }
    /**
     * Get crop duration in weeks
     */
    async getCropDuration(cropType) {
        try {
            const cropData = await kcModel_1.KcModel.findOne({ cropType }).sort({ growthWeek: -1 });
            if (cropData) {
                return cropData.growthWeek;
            }
            // Default durations
            const defaultDurations = {
                'ข้าว กข.(นาดำ)': 17,
                'ข้าวหอมมะลิ': 18,
                'ข้าวเหนียว': 16,
                'ข้าวโพด': 12,
                'อ้อย': 52,
                'มันสำปะหลัง': 40
            };
            return defaultDurations[cropType] || 16;
        }
        catch (error) {
            logger_1.logger.error('Error getting crop duration:', error);
            return 16; // Default
        }
    }
    /**
     * Import Kc data from Excel structure
     */
    async importKcData(data) {
        try {
            // Clear existing data for these crops
            const cropTypes = [...new Set(data.map(d => d.cropType))];
            await kcModel_1.KcModel.deleteMany({ cropType: { $in: cropTypes } });
            // Insert new data
            await kcModel_1.KcModel.insertMany(data);
            logger_1.logger.info(`Imported ${data.length} Kc records for ${cropTypes.length} crops`);
        }
        catch (error) {
            logger_1.logger.error('Error importing Kc data:', error);
            throw new errorHandler_1.AppError('Failed to import Kc data', 500);
        }
    }
    /**
     * Get default Kc values based on typical patterns
     */
    getDefaultKc(cropType, growthWeek) {
        // Default Kc curve for rice (most common crop)
        if (cropType.includes('ข้าว')) {
            if (growthWeek <= 2)
                return 1.10; // Initial stage
            if (growthWeek <= 5)
                return 1.15; // Development
            if (growthWeek <= 12)
                return 1.20; // Mid-season
            if (growthWeek <= 15)
                return 1.00; // Late season
            return 0.90; // Harvest
        }
        // Default for other crops
        if (growthWeek <= 2)
            return 0.40;
        if (growthWeek <= 6)
            return 0.80;
        if (growthWeek <= 12)
            return 1.15;
        return 0.70;
    }
    /**
     * Get all Kc values for a crop
     */
    async getKcCurve(cropType) {
        try {
            const kcData = await kcModel_1.KcModel.find({ cropType })
                .sort({ growthWeek: 1 });
            if (kcData.length === 0) {
                // Return default curve
                const duration = await this.getCropDuration(cropType);
                const curve = [];
                for (let week = 1; week <= duration; week++) {
                    curve.push({
                        week,
                        kc: this.getDefaultKc(cropType, week),
                        stage: this.getGrowthStageName(week, duration)
                    });
                }
                return curve;
            }
            return kcData.map(d => ({
                week: d.growthWeek,
                kc: d.kcValue,
                stage: d.growthStage || this.getGrowthStageName(d.growthWeek, kcData.length)
            }));
        }
        catch (error) {
            logger_1.logger.error('Error getting Kc curve:', error);
            throw new errorHandler_1.AppError('Failed to retrieve Kc curve', 500);
        }
    }
    /**
     * Get growth stage name based on week and duration
     */
    getGrowthStageName(week, duration) {
        const percentage = (week / duration) * 100;
        if (percentage <= 20)
            return 'Initial';
        if (percentage <= 45)
            return 'Development';
        if (percentage <= 75)
            return 'Mid-season';
        if (percentage <= 90)
            return 'Late season';
        return 'Harvest';
    }
    /**
     * Get available crops
     */
    async getAvailableCrops() {
        try {
            const crops = await kcModel_1.KcModel.distinct('cropType');
            if (crops.length === 0) {
                // Return default crops
                return [
                    'ข้าว กข.(นาดำ)',
                    'ข้าวหอมมะลิ',
                    'ข้าวเหนียว',
                    'ข้าวโพด',
                    'อ้อย',
                    'มันสำปะหลัง'
                ];
            }
            return crops.sort();
        }
        catch (error) {
            logger_1.logger.error('Error getting available crops:', error);
            throw new errorHandler_1.AppError('Failed to retrieve crop list', 500);
        }
    }
    /**
     * Get crop information
     */
    async getCropInfo(cropType) {
        try {
            const duration = await this.getCropDuration(cropType);
            const kcCurve = await this.getKcCurve(cropType);
            // Group by stages
            const stages = [
                { stage: 'Initial', weeks: [], kcs: [] },
                { stage: 'Development', weeks: [], kcs: [] },
                { stage: 'Mid-season', weeks: [], kcs: [] },
                { stage: 'Late season', weeks: [], kcs: [] },
                { stage: 'Harvest', weeks: [], kcs: [] }
            ];
            kcCurve.forEach(item => {
                const stageIndex = stages.findIndex(s => s.stage === item.stage);
                if (stageIndex >= 0) {
                    stages[stageIndex].weeks.push(item.week);
                    stages[stageIndex].kcs.push(item.kc);
                }
            });
            const stageInfo = stages
                .filter(s => s.weeks.length > 0)
                .map(s => ({
                stage: s.stage,
                weeks: s.weeks,
                averageKc: s.kcs.reduce((sum, kc) => sum + kc, 0) / s.kcs.length
            }));
            return {
                cropType,
                duration,
                stages: stageInfo
            };
        }
        catch (error) {
            logger_1.logger.error('Error getting crop info:', error);
            throw new errorHandler_1.AppError('Failed to retrieve crop information', 500);
        }
    }
}
exports.KcService = KcService;
exports.kcService = new KcService();
//# sourceMappingURL=kcService.js.map