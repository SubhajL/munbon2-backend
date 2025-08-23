"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.calculationService = exports.CalculationService = void 0;
const errorHandler_1 = require("../middleware/errorHandler");
const logger_1 = require("../utils/logger");
const kcService_1 = require("./kcService");
const et0Service_1 = require("./et0Service");
const rainfallService_1 = require("./rainfallService");
const redis_1 = require("../config/redis");
const calculationModel_1 = require("../models/calculationModel");
class CalculationService {
    PERCOLATION_RATE = 2.0; // mm/day
    RAI_TO_M2 = 1600;
    CACHE_TTL = 3600; // 1 hour
    /**
     * Calculate water demand for given inputs
     */
    async calculateWaterDemand(input) {
        try {
            // Try to get from cache first
            const cacheKey = this.generateCacheKey(input);
            const cached = await this.getFromCache(cacheKey);
            if (cached) {
                logger_1.logger.info('Returning cached calculation result');
                return cached;
            }
            // Validate input
            this.validateInput(input);
            // Calculate for each planting
            const plantingCalculations = await this.calculatePlantingDetails(input.plantings, input.cropType, input.calculationDate);
            // Calculate area-weighted Kc
            const totalArea = plantingCalculations.reduce((sum, p) => sum + p.areaRai, 0);
            const weightedKc = this.calculateWeightedKc(plantingCalculations, totalArea);
            // Get ET0 for the period
            const et0 = await et0Service_1.et0Service.getET0(input.calculationDate, input.calculationPeriod);
            // Calculate water requirement
            const waterReq = this.calculateWaterRequirement(weightedKc, et0, totalArea, input.calculationPeriod);
            // Get effective rainfall
            const rainfall = await rainfallService_1.rainfallService.getEffectiveRainfall(input.calculationDate, input.calculationPeriod, totalArea);
            // Calculate net irrigation
            const netIrrigation = this.calculateNetIrrigation(waterReq, rainfall);
            // Calculate non-agricultural demands
            const nonAgDemand = this.calculateNonAgriculturalDemand(input.nonAgriculturalDemands, input.calculationPeriod);
            // Build output
            const output = {
                waterRequirement: waterReq,
                effectiveRainfall: rainfall,
                netIrrigation: netIrrigation,
                cropDetails: {
                    totalAreaRai: totalArea,
                    weightedKc: weightedKc,
                    et0: et0,
                    activeGrowthStages: plantingCalculations
                },
                nonAgriculturalDemand_m3: nonAgDemand,
                totalWaterDemand_m3: netIrrigation.amount_m3 + nonAgDemand,
                calculationDate: input.calculationDate,
                calculationPeriod: input.calculationPeriod,
                calculationMethod: 'Excel-based lookup tables'
            };
            // Cache the result
            await this.saveToCache(cacheKey, output);
            return output;
        }
        catch (error) {
            logger_1.logger.error('Error calculating water demand:', error);
            throw error;
        }
    }
    /**
     * Calculate details for each planting
     */
    async calculatePlantingDetails(plantings, cropType, calculationDate) {
        const results = [];
        for (const planting of plantings) {
            // Calculate days since planting
            const daysSincePlanting = planting.growthDays ||
                this.calculateDaysSincePlanting(planting.plantingDate, calculationDate);
            if (daysSincePlanting < 0)
                continue; // Not yet planted
            // Get growth week
            const growthWeek = Math.ceil(daysSincePlanting / 7);
            // Get crop duration
            const cropDuration = await kcService_1.kcService.getCropDuration(cropType);
            if (growthWeek > cropDuration)
                continue; // Already harvested
            // Get Kc for this growth stage
            const kc = await kcService_1.kcService.getKc(cropType, growthWeek);
            // Determine growth stage name
            const growthStage = this.determineGrowthStage(growthWeek, cropDuration);
            results.push({
                plantingId: `${planting.plantingDate.toISOString()}_${planting.areaRai}`,
                growthWeek,
                kc,
                areaRai: planting.areaRai,
                growthStage
            });
        }
        return results;
    }
    /**
     * Calculate weighted average Kc
     */
    calculateWeightedKc(plantings, totalArea) {
        if (totalArea === 0)
            return 0;
        const weightedSum = plantings.reduce((sum, p) => sum + (p.kc * p.areaRai), 0);
        return weightedSum / totalArea;
    }
    /**
     * Calculate water requirement
     */
    calculateWaterRequirement(kc, et0, areaRai, period) {
        // Calculate ETc
        const etc = kc * et0; // mm
        // Calculate percolation based on period
        const daysInPeriod = period === 'daily' ? 1 : period === 'weekly' ? 7 : 30;
        const percolation = this.PERCOLATION_RATE * daysInPeriod; // mm
        // Total requirement in mm
        const total_mm = etc + percolation;
        // Convert to m³
        const total_m3 = (total_mm / 1000) * areaRai * this.RAI_TO_M2;
        return {
            etc,
            percolation,
            total_mm,
            total_m3
        };
    }
    /**
     * Calculate net irrigation requirement
     */
    calculateNetIrrigation(waterReq, rainfall) {
        const net_mm = Math.max(0, waterReq.total_mm - rainfall.amount_mm);
        const net_m3 = Math.max(0, waterReq.total_m3 - rainfall.amount_m3);
        return {
            amount_mm: net_mm,
            amount_m3: net_m3
        };
    }
    /**
     * Calculate non-agricultural demand
     */
    calculateNonAgriculturalDemand(demands, period) {
        if (!demands)
            return 0;
        const total = (demands.domestic || 0) +
            (demands.industrial || 0) +
            (demands.ecosystem || 0) +
            (demands.other || 0);
        // Convert to appropriate period if needed
        // Assuming input is already in the correct period unit
        return total;
    }
    /**
     * Calculate days since planting
     */
    calculateDaysSincePlanting(plantingDate, currentDate) {
        const diffTime = currentDate.getTime() - plantingDate.getTime();
        const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24));
        return diffDays;
    }
    /**
     * Determine growth stage name
     */
    determineGrowthStage(week, duration) {
        const percentage = (week / duration) * 100;
        if (percentage <= 20)
            return 'initial';
        if (percentage <= 45)
            return 'development';
        if (percentage <= 75)
            return 'mid-season';
        if (percentage <= 90)
            return 'late-season';
        return 'harvest';
    }
    /**
     * Validate input parameters
     */
    validateInput(input) {
        if (!input.cropType) {
            throw new errorHandler_1.AppError('Crop type is required', 400);
        }
        if (!input.plantings || input.plantings.length === 0) {
            throw new errorHandler_1.AppError('At least one planting is required', 400);
        }
        for (const planting of input.plantings) {
            if (planting.areaRai <= 0) {
                throw new errorHandler_1.AppError('Planting area must be positive', 400);
            }
        }
        if (!['daily', 'weekly', 'monthly'].includes(input.calculationPeriod)) {
            throw new errorHandler_1.AppError('Invalid calculation period', 400);
        }
    }
    /**
     * Generate cache key
     */
    generateCacheKey(input) {
        const dateStr = input.calculationDate.toISOString().split('T')[0];
        const plantingKey = input.plantings
            .map(p => `${p.plantingDate.toISOString()}_${p.areaRai}`)
            .sort()
            .join('_');
        return `ros:calc:${input.cropType}:${dateStr}:${input.calculationPeriod}:${plantingKey}`;
    }
    /**
     * Get from cache
     */
    async getFromCache(key) {
        try {
            const redis = (0, redis_1.getRedisClient)();
            const cached = await redis.get(key);
            if (cached) {
                return JSON.parse(cached);
            }
        }
        catch (error) {
            logger_1.logger.warn('Cache get error:', error);
        }
        return null;
    }
    /**
     * Save to cache
     */
    async saveToCache(key, data) {
        try {
            const redis = (0, redis_1.getRedisClient)();
            await redis.setex(key, this.CACHE_TTL, JSON.stringify(data));
        }
        catch (error) {
            logger_1.logger.warn('Cache set error:', error);
        }
    }
    /**
     * Save calculation to database
     */
    async saveCalculation(data) {
        try {
            const calculation = new calculationModel_1.CalculationModel(data);
            await calculation.save();
            return calculation;
        }
        catch (error) {
            logger_1.logger.error('Error saving calculation:', error);
            throw new errorHandler_1.AppError('Failed to save calculation', 500);
        }
    }
    /**
     * Get calculation by ID
     */
    async getCalculationById(id) {
        try {
            return await calculationModel_1.CalculationModel.findById(id);
        }
        catch (error) {
            logger_1.logger.error('Error getting calculation:', error);
            throw new errorHandler_1.AppError('Failed to retrieve calculation', 500);
        }
    }
    /**
     * Get calculation history
     */
    async getCalculationHistory(params) {
        try {
            const query = {};
            if (params.startDate && params.endDate) {
                query.calculationDate = {
                    $gte: params.startDate,
                    $lte: params.endDate
                };
            }
            if (params.cropType) {
                query.cropType = params.cropType;
            }
            const skip = (params.page - 1) * params.limit;
            const [calculations, total] = await Promise.all([
                calculationModel_1.CalculationModel.find(query)
                    .sort({ calculationDate: -1 })
                    .skip(skip)
                    .limit(params.limit),
                calculationModel_1.CalculationModel.countDocuments(query)
            ]);
            return {
                calculations,
                total,
                page: params.page,
                limit: params.limit,
                totalPages: Math.ceil(total / params.limit)
            };
        }
        catch (error) {
            logger_1.logger.error('Error getting calculation history:', error);
            throw new errorHandler_1.AppError('Failed to retrieve calculation history', 500);
        }
    }
    /**
     * Get demand pattern for visualization
     */
    async getDemandPattern(params) {
        try {
            const startDate = new Date(params.year, 0, 1);
            const endDate = new Date(params.year, 11, 31);
            const calculations = await calculationModel_1.CalculationModel.find({
                cropType: params.cropType,
                calculationDate: { $gte: startDate, $lte: endDate },
                calculationPeriod: params.period
            }).sort({ calculationDate: 1 });
            const labels = [];
            const demandData = [];
            const rainfallData = [];
            calculations.forEach(calc => {
                const date = new Date(calc.calculationDate);
                const label = params.period === 'monthly'
                    ? date.toLocaleDateString('en', { month: 'short' })
                    : date.toLocaleDateString();
                labels.push(label);
                demandData.push(calc.results.netIrrigation.amount_m3);
                rainfallData.push(calc.results.effectiveRainfall.amount_m3);
            });
            return {
                labels,
                datasets: [{
                        label: 'Net Irrigation Demand',
                        data: demandData,
                        backgroundColor: 'rgba(54, 162, 235, 0.2)',
                        borderColor: 'rgba(54, 162, 235, 1)'
                    }, {
                        label: 'Effective Rainfall',
                        data: rainfallData,
                        backgroundColor: 'rgba(75, 192, 192, 0.2)',
                        borderColor: 'rgba(75, 192, 192, 1)'
                    }],
                type: 'line'
            };
        }
        catch (error) {
            logger_1.logger.error('Error getting demand pattern:', error);
            throw new errorHandler_1.AppError('Failed to retrieve demand pattern', 500);
        }
    }
    /**
     * Get seasonal analysis
     */
    async getSeasonalAnalysis(year) {
        try {
            const seasons = [
                { name: 'Cool', months: [11, 12, 1, 2] },
                { name: 'Hot', months: [3, 4, 5] },
                { name: 'Rainy', months: [6, 7, 8, 9, 10] }
            ];
            const seasonalData = await Promise.all(seasons.map(async (season) => {
                const calculations = await calculationModel_1.CalculationModel.find({
                    calculationDate: {
                        $gte: new Date(year, 0, 1),
                        $lte: new Date(year, 11, 31)
                    },
                    $expr: {
                        $in: [{ $month: '$calculationDate' }, season.months]
                    }
                });
                const demands = calculations.map(calc => calc.results.totalWaterDemand_m3);
                const totalDemand = demands.reduce((sum, d) => sum + d, 0);
                const averageDemand = demands.length > 0 ? totalDemand / demands.length : 0;
                const peakDemand = Math.max(...demands, 0);
                return {
                    name: season.name,
                    months: season.months,
                    totalDemand,
                    averageDemand,
                    peakDemand
                };
            }));
            const annualTotal = seasonalData.reduce((sum, s) => sum + s.totalDemand, 0);
            return {
                seasons: seasonalData,
                annualTotal
            };
        }
        catch (error) {
            logger_1.logger.error('Error getting seasonal analysis:', error);
            throw new errorHandler_1.AppError('Failed to retrieve seasonal analysis', 500);
        }
    }
}
exports.CalculationService = CalculationService;
exports.calculationService = new CalculationService();
//# sourceMappingURL=calculationService.js.map