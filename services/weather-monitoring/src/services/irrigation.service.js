"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.IrrigationService = void 0;
class IrrigationService {
    constructor(databaseService, analyticsService, cacheService) {
        this.databaseService = databaseService;
        this.analyticsService = analyticsService;
        this.cacheService = cacheService;
        this.cropDatabase = new Map();
        this.initializeCropDatabase();
    }
    initializeCropDatabase() {
        // Common crops in Thailand
        this.cropDatabase.set('rice-seedling', {
            type: 'rice',
            growthStage: 'seedling',
            kc: 1.05,
            criticalMoisture: 80,
            fieldCapacity: 85,
            wiltingPoint: 60,
            rootDepth: 20,
        });
        this.cropDatabase.set('rice-vegetative', {
            type: 'rice',
            growthStage: 'vegetative',
            kc: 1.20,
            criticalMoisture: 75,
            fieldCapacity: 85,
            wiltingPoint: 60,
            rootDepth: 30,
        });
        this.cropDatabase.set('rice-reproductive', {
            type: 'rice',
            growthStage: 'reproductive',
            kc: 1.35,
            criticalMoisture: 80,
            fieldCapacity: 85,
            wiltingPoint: 60,
            rootDepth: 40,
        });
        this.cropDatabase.set('rice-maturity', {
            type: 'rice',
            growthStage: 'maturity',
            kc: 0.95,
            criticalMoisture: 65,
            fieldCapacity: 85,
            wiltingPoint: 60,
            rootDepth: 40,
        });
        this.cropDatabase.set('sugarcane-initial', {
            type: 'sugarcane',
            growthStage: 'initial',
            kc: 0.40,
            criticalMoisture: 55,
            fieldCapacity: 70,
            wiltingPoint: 40,
            rootDepth: 30,
        });
        this.cropDatabase.set('sugarcane-development', {
            type: 'sugarcane',
            growthStage: 'development',
            kc: 0.75,
            criticalMoisture: 60,
            fieldCapacity: 70,
            wiltingPoint: 40,
            rootDepth: 60,
        });
        this.cropDatabase.set('sugarcane-peak', {
            type: 'sugarcane',
            growthStage: 'peak',
            kc: 1.25,
            criticalMoisture: 65,
            fieldCapacity: 70,
            wiltingPoint: 40,
            rootDepth: 120,
        });
        this.cropDatabase.set('sugarcane-maturity', {
            type: 'sugarcane',
            growthStage: 'maturity',
            kc: 0.75,
            criticalMoisture: 50,
            fieldCapacity: 70,
            wiltingPoint: 40,
            rootDepth: 120,
        });
        this.cropDatabase.set('cassava-initial', {
            type: 'cassava',
            growthStage: 'initial',
            kc: 0.30,
            criticalMoisture: 45,
            fieldCapacity: 65,
            wiltingPoint: 35,
            rootDepth: 30,
        });
        this.cropDatabase.set('cassava-development', {
            type: 'cassava',
            growthStage: 'development',
            kc: 0.60,
            criticalMoisture: 50,
            fieldCapacity: 65,
            wiltingPoint: 35,
            rootDepth: 60,
        });
        this.cropDatabase.set('cassava-peak', {
            type: 'cassava',
            growthStage: 'peak',
            kc: 1.10,
            criticalMoisture: 55,
            fieldCapacity: 65,
            wiltingPoint: 35,
            rootDepth: 100,
        });
        this.cropDatabase.set('cassava-maturity', {
            type: 'cassava',
            growthStage: 'maturity',
            kc: 0.50,
            criticalMoisture: 40,
            fieldCapacity: 65,
            wiltingPoint: 35,
            rootDepth: 100,
        });
    }
    async getIrrigationRecommendation(location, cropType = 'rice', growthStage = 'vegetative', currentSoilMoisture) {
        const cacheKey = `irrigation:${location.lat}:${location.lng}:${cropType}:${growthStage}`;
        // Check cache first
        const cached = await this.cacheService.get(cacheKey);
        if (cached && this.isRecommendationValid(cached)) {
            return cached;
        }
        // Get crop data
        const cropKey = `${cropType}-${growthStage}`.toLowerCase();
        const cropData = this.cropDatabase.get(cropKey) || this.getDefaultCropData();
        // Get current weather
        const currentWeather = await this.databaseService.getCurrentWeather(location);
        if (currentWeather.length === 0) {
            throw new Error('No weather data available for location');
        }
        // Get weather forecast
        const forecasts = await this.databaseService.getWeatherForecasts(location, 7);
        // Calculate ET for today
        const et = await this.analyticsService.calculateEvapotranspiration(location, new Date(), cropData.kc);
        // Analyze forecast
        const forecastAnalysis = this.analyzeForecast(forecasts);
        // Generate recommendation
        const recommendation = this.generateRecommendation(cropData, currentWeather[0], forecastAnalysis, et, currentSoilMoisture);
        // Cache the recommendation
        await this.cacheService.set(cacheKey, recommendation, 3600); // Cache for 1 hour
        return recommendation;
    }
    async getIrrigationSchedule(location, cropType, growthStage, fieldSize, // hectares
    irrigationSystem = 'flood') {
        const recommendation = await this.getIrrigationRecommendation(location, cropType, growthStage);
        if (recommendation.recommendation === 'postpone') {
            return {
                schedule: [],
                reason: 'Irrigation postponed due to weather conditions',
                nextEvaluation: recommendation.nextEvaluation,
            };
        }
        const cropKey = `${cropType}-${growthStage}`.toLowerCase();
        const cropData = this.cropDatabase.get(cropKey) || this.getDefaultCropData();
        // Calculate water requirements
        const waterRequirement = this.calculateWaterRequirement(recommendation.suggestedAmount || 0, fieldSize, irrigationSystem);
        // Generate schedule based on system capacity
        const schedule = this.generateIrrigationSchedule(waterRequirement, irrigationSystem, recommendation.suggestedTime);
        return {
            location,
            cropType,
            growthStage,
            fieldSize,
            irrigationSystem,
            waterRequirement,
            schedule,
            recommendation: recommendation.recommendation,
            confidence: recommendation.confidence,
        };
    }
    async getWaterBalanceAnalysis(location, cropType, growthStage, period = '30d') {
        const { startTime, endTime } = this.getTimeRange(period);
        // Get historical weather data
        const historicalWeather = await this.databaseService.getHistoricalWeather(startTime, endTime, location);
        // Get crop data
        const cropKey = `${cropType}-${growthStage}`.toLowerCase();
        const cropData = this.cropDatabase.get(cropKey) || this.getDefaultCropData();
        // Calculate daily water balance
        const dailyBalance = await this.calculateDailyWaterBalance(historicalWeather, location, cropData);
        // Calculate statistics
        const totalRainfall = dailyBalance.reduce((sum, day) => sum + day.rainfall, 0);
        const totalET = dailyBalance.reduce((sum, day) => sum + day.et, 0);
        const totalIrrigation = dailyBalance.reduce((sum, day) => sum + day.irrigationNeeded, 0);
        const deficitDays = dailyBalance.filter(day => day.balance < 0).length;
        const surplusDays = dailyBalance.filter(day => day.balance > 0).length;
        return {
            location,
            cropType,
            growthStage,
            period,
            startDate: startTime,
            endDate: endTime,
            summary: {
                totalRainfall,
                totalET,
                totalIrrigation,
                netBalance: totalRainfall - totalET,
                deficitDays,
                surplusDays,
                averageDailyET: totalET / dailyBalance.length,
                averageDailyRainfall: totalRainfall / dailyBalance.length,
            },
            dailyBalance,
            recommendations: {
                irrigationEfficiency: this.calculateIrrigationEfficiency(dailyBalance),
                waterUseEfficiency: totalET > 0 ? (totalRainfall / totalET) : 0,
                suggestedAdjustments: this.suggestAdjustments(dailyBalance, cropData),
            },
        };
    }
    analyzeForecast(forecasts) {
        const next7Days = forecasts.slice(0, 7);
        const totalRainfall = next7Days.reduce((sum, f) => sum + f.rainfall.amount, 0);
        const avgRainfallProbability = next7Days.reduce((sum, f) => sum + f.rainfall.probability, 0) / next7Days.length;
        const maxTemp = Math.max(...next7Days.map(f => f.temperature.max));
        const minTemp = Math.min(...next7Days.map(f => f.temperature.min));
        const avgHumidity = next7Days.reduce((sum, f) => sum + f.humidity.avg, 0) / next7Days.length;
        const avgWindSpeed = next7Days.reduce((sum, f) => sum + f.windSpeed, 0) / next7Days.length;
        const hasHeavyRain = next7Days.some(f => f.rainfall.amount > 50);
        const hasExtendedDryPeriod = this.checkExtendedDryPeriod(next7Days);
        const hasExtremeTemp = maxTemp > 40 || minTemp < 10;
        return {
            totalRainfall,
            avgRainfallProbability,
            maxTemp,
            minTemp,
            avgHumidity,
            avgWindSpeed,
            hasHeavyRain,
            hasExtendedDryPeriod,
            hasExtremeTemp,
            rainDays: next7Days.filter(f => f.rainfall.amount > 0.1).length,
        };
    }
    generateRecommendation(cropData, currentWeather, forecastAnalysis, et, currentSoilMoisture) {
        const location = currentWeather.location || { lat: 0, lng: 0 };
        const timestamp = new Date();
        // Default soil moisture if not provided
        const soilMoisture = currentSoilMoisture ?? 70;
        // Calculate water deficit
        const moistureDeficit = cropData.fieldCapacity - soilMoisture;
        const criticalDeficit = soilMoisture < cropData.criticalMoisture;
        // Decision logic
        let recommendation = 'maintain';
        let suggestedAmount = 0;
        let confidence = 0.8;
        let reasoning = {
            currentSoilMoisture: soilMoisture,
            forecastedRainfall: forecastAnalysis.totalRainfall,
            evapotranspiration: et.et0,
            temperature: currentWeather.temperature,
            windSpeed: currentWeather.windSpeed,
            humidity: currentWeather.humidity,
        };
        // Heavy rain expected - postpone irrigation
        if (forecastAnalysis.hasHeavyRain ||
            (forecastAnalysis.totalRainfall > 30 && forecastAnalysis.avgRainfallProbability > 0.7)) {
            recommendation = 'postpone';
            reasoning.decision = 'Heavy rainfall expected in the next 7 days';
            confidence = 0.9;
        }
        // Critical moisture deficit - irrigate immediately
        else if (criticalDeficit) {
            recommendation = 'irrigate';
            suggestedAmount = this.calculateIrrigationAmount(moistureDeficit, cropData.rootDepth);
            reasoning.decision = 'Soil moisture below critical level';
            confidence = 0.95;
        }
        // High ET and low expected rainfall - irrigate
        else if (et.et0 > 5 && forecastAnalysis.totalRainfall < 10) {
            recommendation = 'irrigate';
            suggestedAmount = this.calculateIrrigationAmount(et.et0 * 7 - forecastAnalysis.totalRainfall, cropData.rootDepth);
            reasoning.decision = 'High evapotranspiration with low expected rainfall';
            confidence = 0.85;
        }
        // Moderate conditions - maintain or reduce
        else if (moistureDeficit < 10 && forecastAnalysis.totalRainfall > 20) {
            recommendation = 'reduce';
            suggestedAmount = this.calculateIrrigationAmount(moistureDeficit / 2, cropData.rootDepth);
            reasoning.decision = 'Adequate soil moisture with moderate rainfall expected';
            confidence = 0.8;
        }
        // Extended dry period expected - irrigate preventively
        else if (forecastAnalysis.hasExtendedDryPeriod) {
            recommendation = 'irrigate';
            suggestedAmount = this.calculateIrrigationAmount(et.et0 * forecastAnalysis.rainDays, cropData.rootDepth);
            reasoning.decision = 'Extended dry period expected';
            confidence = 0.75;
        }
        // Adjust for extreme temperatures
        if (forecastAnalysis.hasExtremeTemp) {
            if (forecastAnalysis.maxTemp > 40 && recommendation !== 'postpone') {
                suggestedAmount *= 1.2; // Increase by 20% for extreme heat
                reasoning.tempAdjustment = 'Increased due to extreme heat';
            }
            else if (forecastAnalysis.minTemp < 10) {
                suggestedAmount *= 0.8; // Reduce by 20% for cold weather
                reasoning.tempAdjustment = 'Reduced due to cold weather';
            }
        }
        // Calculate suggested time
        const suggestedTime = this.calculateOptimalIrrigationTime(currentWeather, forecastAnalysis);
        // Next evaluation time
        const nextEvaluation = new Date();
        if (recommendation === 'irrigate') {
            nextEvaluation.setDate(nextEvaluation.getDate() + 3); // Re-evaluate after 3 days
        }
        else if (recommendation === 'postpone') {
            nextEvaluation.setDate(nextEvaluation.getDate() + 1); // Re-evaluate next day
        }
        else {
            nextEvaluation.setDate(nextEvaluation.getDate() + 2); // Re-evaluate after 2 days
        }
        return {
            location,
            timestamp,
            recommendation,
            confidence,
            reasoning,
            suggestedAmount: Math.round(suggestedAmount * 10) / 10, // Round to 1 decimal
            suggestedTime,
            nextEvaluation,
            cropType: cropData.type,
            growthStage: cropData.growthStage,
        };
    }
    calculateIrrigationAmount(deficit, rootDepth) {
        // Convert deficit percentage to mm of water
        // Assuming soil water holding capacity of 150mm/m
        const waterHoldingCapacity = 150; // mm/m
        const rootDepthM = rootDepth / 100; // Convert cm to m
        return (deficit / 100) * waterHoldingCapacity * rootDepthM;
    }
    calculateOptimalIrrigationTime(currentWeather, forecastAnalysis) {
        const now = new Date();
        const currentHour = now.getHours();
        // Optimal irrigation times to minimize evaporation
        const optimalHours = [5, 6, 18, 19]; // Early morning or evening
        // Find next optimal hour
        let targetHour = optimalHours[0];
        for (const hour of optimalHours) {
            if (hour > currentHour) {
                targetHour = hour;
                break;
            }
        }
        const suggestedTime = new Date(now);
        if (targetHour <= currentHour) {
            // Next day
            suggestedTime.setDate(suggestedTime.getDate() + 1);
        }
        suggestedTime.setHours(targetHour, 0, 0, 0);
        // Adjust for weather conditions
        if (currentWeather.windSpeed > 30) {
            // High wind - prefer early morning
            suggestedTime.setHours(5, 0, 0, 0);
        }
        else if (currentWeather.temperature > 35) {
            // High temperature - prefer late evening
            suggestedTime.setHours(19, 0, 0, 0);
        }
        return suggestedTime;
    }
    calculateWaterRequirement(amountMm, fieldSizeHa, system) {
        // Convert mm to liters per hectare
        const litersPerHa = amountMm * 10000; // 1mm = 10,000 L/ha
        const totalLiters = litersPerHa * fieldSizeHa;
        // System efficiency
        const efficiency = {
            drip: 0.90,
            sprinkler: 0.75,
            flood: 0.60,
        }[system];
        const actualRequired = totalLiters / efficiency;
        return {
            netRequirement: totalLiters,
            grossRequirement: actualRequired,
            efficiency: efficiency * 100,
            amountMm,
            fieldSizeHa,
            system,
        };
    }
    generateIrrigationSchedule(waterRequirement, system, suggestedTime) {
        const schedule = [];
        const startTime = suggestedTime || new Date();
        // System flow rates (liters per hour)
        const flowRates = {
            drip: 5000,
            sprinkler: 20000,
            flood: 50000,
        };
        const flowRate = flowRates[system];
        const durationHours = waterRequirement.grossRequirement / flowRate;
        if (durationHours <= 8) {
            // Single session
            schedule.push({
                startTime,
                endTime: new Date(startTime.getTime() + durationHours * 60 * 60 * 1000),
                duration: durationHours,
                waterAmount: waterRequirement.grossRequirement,
            });
        }
        else {
            // Multiple sessions
            const sessions = Math.ceil(durationHours / 6); // Max 6 hours per session
            const waterPerSession = waterRequirement.grossRequirement / sessions;
            for (let i = 0; i < sessions; i++) {
                const sessionStart = new Date(startTime);
                sessionStart.setDate(sessionStart.getDate() + i);
                schedule.push({
                    startTime: sessionStart,
                    endTime: new Date(sessionStart.getTime() + 6 * 60 * 60 * 1000),
                    duration: 6,
                    waterAmount: waterPerSession,
                });
            }
        }
        return schedule;
    }
    async calculateDailyWaterBalance(weatherData, location, cropData) {
        const dailyData = this.groupByDay(weatherData);
        const dailyBalance = [];
        for (const [date, readings] of dailyData.entries()) {
            // Calculate daily ET
            const et = await this.analyticsService.calculateEvapotranspiration(location, new Date(date), cropData.kc);
            // Calculate daily rainfall
            const rainfall = readings
                .map(r => r.rainfall || 0)
                .reduce((sum, r) => sum + r, 0);
            // Calculate balance
            const balance = rainfall - et.etc;
            const irrigationNeeded = balance < 0 ? Math.abs(balance) : 0;
            dailyBalance.push({
                date,
                rainfall,
                et: et.etc,
                balance,
                irrigationNeeded,
                soilMoisture: this.estimateSoilMoisture(balance, cropData),
            });
        }
        return dailyBalance;
    }
    groupByDay(readings) {
        const grouped = new Map();
        readings.forEach(reading => {
            const date = reading.timestamp.toISOString().split('T')[0];
            if (!grouped.has(date)) {
                grouped.set(date, []);
            }
            grouped.get(date).push(reading);
        });
        return grouped;
    }
    estimateSoilMoisture(waterBalance, cropData) {
        // Simple estimation - in production, this would use soil water balance models
        const baselineMoisture = (cropData.fieldCapacity + cropData.wiltingPoint) / 2;
        const adjustment = (waterBalance / 10) * 5; // 5% change per 10mm water balance
        return Math.max(cropData.wiltingPoint, Math.min(cropData.fieldCapacity, baselineMoisture + adjustment));
    }
    calculateIrrigationEfficiency(dailyBalance) {
        const totalIrrigation = dailyBalance.reduce((sum, day) => sum + day.irrigationNeeded, 0);
        const totalET = dailyBalance.reduce((sum, day) => sum + day.et, 0);
        if (totalIrrigation === 0)
            return 100;
        return Math.min(100, (totalET / totalIrrigation) * 100);
    }
    suggestAdjustments(dailyBalance, cropData) {
        const suggestions = [];
        const avgBalance = dailyBalance.reduce((sum, day) => sum + day.balance, 0) / dailyBalance.length;
        const deficitDays = dailyBalance.filter(day => day.balance < 0).length;
        const consecutiveDryDays = this.findConsecutiveDryDays(dailyBalance);
        if (avgBalance < -5) {
            suggestions.push('Consider increasing irrigation frequency');
        }
        if (avgBalance > 10) {
            suggestions.push('Consider reducing irrigation to prevent waterlogging');
        }
        if (deficitDays > dailyBalance.length * 0.4) {
            suggestions.push('High number of deficit days - review irrigation schedule');
        }
        if (consecutiveDryDays > 5) {
            suggestions.push(`Found ${consecutiveDryDays} consecutive dry days - implement deficit irrigation strategy`);
        }
        if (cropData.growthStage === 'maturity' && avgBalance > 0) {
            suggestions.push('Consider reducing irrigation during maturity stage');
        }
        return suggestions;
    }
    findConsecutiveDryDays(dailyBalance) {
        let maxConsecutive = 0;
        let currentConsecutive = 0;
        dailyBalance.forEach(day => {
            if (day.balance < 0) {
                currentConsecutive++;
                maxConsecutive = Math.max(maxConsecutive, currentConsecutive);
            }
            else {
                currentConsecutive = 0;
            }
        });
        return maxConsecutive;
    }
    checkExtendedDryPeriod(forecasts) {
        let consecutiveDryDays = 0;
        for (const forecast of forecasts) {
            if (forecast.rainfall.amount < 1 && forecast.rainfall.probability < 0.3) {
                consecutiveDryDays++;
                if (consecutiveDryDays >= 5) {
                    return true;
                }
            }
            else {
                consecutiveDryDays = 0;
            }
        }
        return false;
    }
    getTimeRange(period) {
        const endTime = new Date();
        const startTime = new Date();
        const match = period.match(/(\d+)([hdwmy])/);
        if (!match) {
            throw new Error('Invalid period format');
        }
        const [, value, unit] = match;
        const num = parseInt(value);
        switch (unit) {
            case 'h':
                startTime.setHours(startTime.getHours() - num);
                break;
            case 'd':
                startTime.setDate(startTime.getDate() - num);
                break;
            case 'w':
                startTime.setDate(startTime.getDate() - num * 7);
                break;
            case 'm':
                startTime.setMonth(startTime.getMonth() - num);
                break;
            case 'y':
                startTime.setFullYear(startTime.getFullYear() - num);
                break;
        }
        return { startTime, endTime };
    }
    getDefaultCropData() {
        return {
            type: 'generic',
            growthStage: 'vegetative',
            kc: 1.0,
            criticalMoisture: 60,
            fieldCapacity: 75,
            wiltingPoint: 45,
            rootDepth: 50,
        };
    }
    isRecommendationValid(recommendation) {
        const now = new Date();
        const age = now.getTime() - recommendation.timestamp.getTime();
        return age < 60 * 60 * 1000; // Valid for 1 hour
    }
}
exports.IrrigationService = IrrigationService;
//# sourceMappingURL=irrigation.service.js.map