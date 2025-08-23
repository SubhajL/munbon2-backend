"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.WaterDemandCalculatorService = void 0;
const logger_1 = require("../utils/logger");
const database_service_1 = require("./database.service");
const kafka_service_1 = require("./kafka.service");
const uuid_1 = require("uuid");
class WaterDemandCalculatorService {
    static instance;
    databaseService;
    kafkaService;
    cropCoefficients = {
        'RICE': { initial: 1.05, mid: 1.20, late: 0.90 },
        'CORN': { initial: 0.30, mid: 1.20, late: 0.60 },
        'SUGARCANE': { initial: 0.40, mid: 1.25, late: 0.75 },
        'CASSAVA': { initial: 0.30, mid: 1.10, late: 0.50 },
        'VEGETABLES': { initial: 0.70, mid: 1.05, late: 0.95 },
        'DEFAULT': { initial: 0.50, mid: 1.00, late: 0.75 },
    };
    irrigationEfficiencies = {
        'RID-MS': 0.65,
        'ROS': 0.75,
        'AWD': 0.85,
    };
    monthlyET0 = [
        4.0,
        4.5,
        5.0,
        5.5,
        5.0,
        4.5,
        4.0,
        4.0,
        4.0,
        4.0,
        3.5,
        3.5,
    ];
    constructor() {
        this.databaseService = database_service_1.DatabaseService.getInstance();
        this.kafkaService = kafka_service_1.KafkaService.getInstance();
    }
    static getInstance() {
        if (!WaterDemandCalculatorService.instance) {
            WaterDemandCalculatorService.instance = new WaterDemandCalculatorService();
        }
        return WaterDemandCalculatorService.instance;
    }
    async calculateWaterDemand(request) {
        const requestId = (0, uuid_1.v4)();
        const parcelWaterDemands = [];
        try {
            const parcels = await this.databaseService.getParcelsByIds(request.parcels);
            for (const parcel of parcels) {
                const waterDemand = await this.calculateParcelWaterDemand(parcel, request.method, request.parameters);
                parcelWaterDemands.push({
                    parcelId: parcel.parcelId,
                    area: parcel.area,
                    method: request.method,
                    waterDemand,
                });
                parcel.waterDemandMethod = request.method;
                parcel.waterDemand = waterDemand;
                await this.databaseService.updateParcel(parcel);
            }
            const totalDailyDemand = parcelWaterDemands.reduce((sum, p) => sum + p.waterDemand.dailyDemand, 0);
            const totalWeeklyDemand = parcelWaterDemands.reduce((sum, p) => sum + p.waterDemand.weeklyDemand, 0);
            const totalMonthlyDemand = parcelWaterDemands.reduce((sum, p) => sum + p.waterDemand.monthlyDemand, 0);
            await this.kafkaService.publishWaterDemandUpdated({
                requestId,
                parcelsCount: parcelWaterDemands.length,
                totalDailyDemand,
                method: request.method,
                calculatedAt: new Date(),
            });
            return {
                requestId,
                parcels: parcelWaterDemands,
                totalDailyDemand,
                totalWeeklyDemand,
                totalMonthlyDemand,
                calculatedAt: new Date(),
            };
        }
        catch (error) {
            logger_1.logger.error('Water demand calculation failed:', error);
            throw error;
        }
    }
    async calculateParcelWaterDemand(parcel, method, parameters) {
        const cropType = parameters?.cropType || parcel.cropType || 'DEFAULT';
        const cropCoeff = this.getCropCoefficient(cropType, parcel.plantingDate);
        const currentMonth = new Date().getMonth();
        const et0 = this.monthlyET0[currentMonth];
        const efficiency = parameters?.irrigationEfficiency ||
            this.irrigationEfficiencies[method];
        const cropET = et0 * cropCoeff;
        const dailyDemand = (cropET * parcel.area) / (efficiency * 1000);
        const weeklyDemand = dailyDemand * 7;
        const monthlyDemand = dailyDemand * 30;
        const seasonalDemand = dailyDemand * 120;
        let adjustedDailyDemand = dailyDemand;
        if (method === 'AWD') {
            adjustedDailyDemand = dailyDemand * 0.7;
        }
        return {
            method,
            dailyDemand: adjustedDailyDemand,
            weeklyDemand: adjustedDailyDemand * 7,
            monthlyDemand: adjustedDailyDemand * 30,
            seasonalDemand: adjustedDailyDemand * 120,
            cropCoefficient: cropCoeff,
            referenceEvapotranspiration: et0,
            irrigationEfficiency: efficiency,
            lastCalculated: new Date(),
            parameters: {
                cropType,
                area: parcel.area,
                method,
                ...parameters,
            },
        };
    }
    getCropCoefficient(cropType, plantingDate) {
        const coefficients = this.cropCoefficients[cropType.toUpperCase()] ||
            this.cropCoefficients['DEFAULT'];
        if (!plantingDate) {
            return coefficients.mid;
        }
        const daysSincePlanting = Math.floor((new Date().getTime() - plantingDate.getTime()) / (1000 * 60 * 60 * 24));
        if (daysSincePlanting < 30) {
            return coefficients.initial;
        }
        else if (daysSincePlanting < 90) {
            return coefficients.mid;
        }
        else {
            return coefficients.late;
        }
    }
    async calculateZoneWaterDemand(zone) {
        const parcels = await this.databaseService.getParcelsByZone(zone);
        const statistics = {
            zone,
            totalArea: 0,
            parcelCount: parcels.length,
            waterDemandByMethod: {
                'RID-MS': { count: 0, dailyDemand: 0 },
                'ROS': { count: 0, dailyDemand: 0 },
                'AWD': { count: 0, dailyDemand: 0 },
            },
            cropTypes: {},
            totalDailyDemand: 0,
            totalWeeklyDemand: 0,
            totalMonthlyDemand: 0,
        };
        for (const parcel of parcels) {
            statistics.totalArea += parcel.area;
            const method = parcel.waterDemandMethod;
            statistics.waterDemandByMethod[method].count++;
            if (!parcel.waterDemand) {
                parcel.waterDemand = await this.calculateParcelWaterDemand(parcel, method, {});
            }
            statistics.waterDemandByMethod[method].dailyDemand += parcel.waterDemand.dailyDemand;
            statistics.totalDailyDemand += parcel.waterDemand.dailyDemand;
            statistics.totalWeeklyDemand += parcel.waterDemand.weeklyDemand;
            statistics.totalMonthlyDemand += parcel.waterDemand.monthlyDemand;
            const cropType = parcel.cropType || 'UNKNOWN';
            statistics.cropTypes[cropType] = (statistics.cropTypes[cropType] || 0) + 1;
        }
        return statistics;
    }
    async updateAllWaterDemands() {
        logger_1.logger.info('Starting scheduled water demand update');
        try {
            const parcels = await this.databaseService.getAllParcels();
            let updated = 0;
            for (const parcel of parcels) {
                try {
                    const waterDemand = await this.calculateParcelWaterDemand(parcel, parcel.waterDemandMethod, {});
                    parcel.waterDemand = waterDemand;
                    await this.databaseService.updateParcel(parcel);
                    updated++;
                    if (updated % 100 === 0) {
                        logger_1.logger.info(`Updated water demand for ${updated} parcels`);
                    }
                }
                catch (error) {
                    logger_1.logger.error(`Failed to update water demand for parcel ${parcel.parcelId}:`, error);
                }
            }
            logger_1.logger.info(`Completed water demand update. Updated ${updated} parcels`);
            await this.kafkaService.publishWaterDemandUpdated({
                requestId: 'scheduled-update',
                parcelsCount: updated,
                totalDailyDemand: 0,
                method: 'MIXED',
                calculatedAt: new Date(),
            });
        }
        catch (error) {
            logger_1.logger.error('Failed to update water demands:', error);
            throw error;
        }
    }
}
exports.WaterDemandCalculatorService = WaterDemandCalculatorService;
//# sourceMappingURL=water-demand-calculator.service.js.map