"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.AnalyticsService = void 0;
class AnalyticsService {
    constructor(databaseService, cacheService) {
        this.databaseService = databaseService;
        this.cacheService = cacheService;
    }
    async getWeatherAnalytics(location, period = '7d') {
        const cacheKey = `analytics:${location.lat}:${location.lng}:${period}`;
        // Check cache first
        const cached = await this.cacheService.get(cacheKey);
        if (cached) {
            return cached;
        }
        // Calculate time range
        const { startTime, endTime } = this.getTimeRange(period);
        // Get historical data
        const readings = await this.databaseService.getHistoricalWeather(startTime, endTime, location);
        if (readings.length === 0) {
            throw new Error('No weather data available for the specified location and period');
        }
        // Calculate statistics
        const analytics = this.calculateAnalytics(readings, location, period, startTime, endTime);
        // Cache results
        await this.cacheService.set(cacheKey, analytics, 3600); // Cache for 1 hour
        return analytics;
    }
    async getComparativeAnalytics(locations, period = '30d') {
        const analytics = await Promise.all(locations.map(location => this.getWeatherAnalytics(location, period)));
        // Calculate comparative metrics
        const comparison = {
            period,
            locations: locations.map((loc, index) => ({
                location: loc,
                analytics: analytics[index],
            })),
            comparison: {
                temperature: {
                    highest: this.findExtreme(analytics, 'temperature', 'max', true),
                    lowest: this.findExtreme(analytics, 'temperature', 'min', false),
                    mostStable: this.findMostStable(analytics, 'temperature'),
                },
                rainfall: {
                    highest: this.findExtreme(analytics, 'rainfall', 'total', true),
                    lowest: this.findExtreme(analytics, 'rainfall', 'total', false),
                    mostRainyDays: this.findExtreme(analytics, 'rainfall', 'rainDays', true),
                },
            },
        };
        return comparison;
    }
    async calculateEvapotranspiration(location, date = new Date(), cropCoefficient = 1.0) {
        // Get weather data for the date
        const startTime = new Date(date);
        startTime.setHours(0, 0, 0, 0);
        const endTime = new Date(date);
        endTime.setHours(23, 59, 59, 999);
        const readings = await this.databaseService.getHistoricalWeather(startTime, endTime, location);
        if (readings.length === 0) {
            throw new Error('No weather data available for ET calculation');
        }
        // Calculate daily averages
        const avgTemp = this.average(readings.map(r => r.temperature).filter(Boolean));
        const avgHumidity = this.average(readings.map(r => r.humidity).filter(Boolean));
        const avgWindSpeed = this.average(readings.map(r => r.windSpeed).filter(Boolean));
        const avgSolarRadiation = this.average(readings.map(r => r.solarRadiation).filter(Boolean)) || 200; // Default if not available
        const avgPressure = this.average(readings.map(r => r.pressure).filter(Boolean)) || 101.3; // Default sea level pressure
        // Calculate ET0 using Penman-Monteith equation (simplified version)
        const et0 = this.calculatePenmanMonteith(avgTemp, avgHumidity, avgWindSpeed, avgSolarRadiation, avgPressure, location.lat);
        // Calculate crop ET
        const etc = et0 * cropCoefficient;
        const result = {
            location,
            timestamp: date,
            et0,
            etc,
            method: 'penman-monteith',
            inputs: {
                temperature: avgTemp,
                humidity: avgHumidity,
                windSpeed: avgWindSpeed,
                solarRadiation: avgSolarRadiation,
                pressure: avgPressure,
            },
            cropCoefficient,
        };
        return result;
    }
    async getWeatherTrends(location, metric, period = '30d') {
        const { startTime, endTime } = this.getTimeRange(period);
        const interval = this.getAggregationInterval(period);
        const aggregated = await this.databaseService.getAggregatedWeather(startTime, endTime, interval, location);
        if (aggregated.length === 0) {
            throw new Error('No data available for trend analysis');
        }
        // Extract metric values
        const values = aggregated.map(row => ({
            timestamp: row.bucket,
            value: row[`avg_${metric}`] || row[`total_${metric}`],
        }));
        // Calculate trend
        const trend = this.calculateTrend(values);
        // Calculate moving averages
        const movingAvg7 = this.calculateMovingAverage(values, 7);
        const movingAvg30 = this.calculateMovingAverage(values, 30);
        return {
            location,
            metric,
            period,
            data: values,
            trend: {
                direction: trend.slope > 0.1 ? 'increasing' : trend.slope < -0.1 ? 'decreasing' : 'stable',
                slope: trend.slope,
                correlation: trend.correlation,
            },
            movingAverages: {
                ma7: movingAvg7,
                ma30: movingAvg30,
            },
            statistics: {
                mean: this.average(values.map(v => v.value)),
                stdDev: this.standardDeviation(values.map(v => v.value)),
                min: Math.min(...values.map(v => v.value)),
                max: Math.max(...values.map(v => v.value)),
            },
        };
    }
    async detectAnomalies(location, threshold = 2.5 // Standard deviations
    ) {
        const period = '90d'; // Use 90 days for baseline
        const { startTime, endTime } = this.getTimeRange(period);
        const readings = await this.databaseService.getHistoricalWeather(startTime, endTime, location);
        const anomalies = {
            temperature: [],
            rainfall: [],
            pressure: [],
            windSpeed: [],
        };
        // Calculate baselines
        const baselines = {
            temperature: this.calculateBaseline(readings.map(r => r.temperature).filter(Boolean)),
            rainfall: this.calculateBaseline(readings.map(r => r.rainfall).filter(Boolean)),
            pressure: this.calculateBaseline(readings.map(r => r.pressure).filter(Boolean)),
            windSpeed: this.calculateBaseline(readings.map(r => r.windSpeed).filter(Boolean)),
        };
        // Detect anomalies
        readings.forEach(reading => {
            if (reading.temperature && Math.abs(reading.temperature - baselines.temperature.mean) > threshold * baselines.temperature.stdDev) {
                anomalies.temperature.push({
                    timestamp: reading.timestamp,
                    value: reading.temperature,
                    deviation: (reading.temperature - baselines.temperature.mean) / baselines.temperature.stdDev,
                });
            }
            if (reading.rainfall && reading.rainfall > baselines.rainfall.mean + threshold * baselines.rainfall.stdDev) {
                anomalies.rainfall.push({
                    timestamp: reading.timestamp,
                    value: reading.rainfall,
                    deviation: (reading.rainfall - baselines.rainfall.mean) / baselines.rainfall.stdDev,
                });
            }
            if (reading.pressure && Math.abs(reading.pressure - baselines.pressure.mean) > threshold * baselines.pressure.stdDev) {
                anomalies.pressure.push({
                    timestamp: reading.timestamp,
                    value: reading.pressure,
                    deviation: (reading.pressure - baselines.pressure.mean) / baselines.pressure.stdDev,
                });
            }
            if (reading.windSpeed && reading.windSpeed > baselines.windSpeed.mean + threshold * baselines.windSpeed.stdDev) {
                anomalies.windSpeed.push({
                    timestamp: reading.timestamp,
                    value: reading.windSpeed,
                    deviation: (reading.windSpeed - baselines.windSpeed.mean) / baselines.windSpeed.stdDev,
                });
            }
        });
        return {
            location,
            period,
            threshold,
            baselines,
            anomalies,
            summary: {
                totalAnomalies: Object.values(anomalies).reduce((sum, arr) => sum + arr.length, 0),
                byType: {
                    temperature: anomalies.temperature.length,
                    rainfall: anomalies.rainfall.length,
                    pressure: anomalies.pressure.length,
                    windSpeed: anomalies.windSpeed.length,
                },
            },
        };
    }
    calculateAnalytics(readings, location, period, startTime, endTime) {
        // Temperature statistics
        const temperatures = readings.map(r => r.temperature).filter(Boolean);
        const tempStats = {
            avg: this.average(temperatures),
            min: Math.min(...temperatures),
            max: Math.max(...temperatures),
            stdDev: this.standardDeviation(temperatures),
        };
        // Humidity statistics
        const humidities = readings.map(r => r.humidity).filter(Boolean);
        const humidityStats = {
            avg: this.average(humidities),
            min: Math.min(...humidities),
            max: Math.max(...humidities),
        };
        // Rainfall statistics
        const rainfalls = readings.map(r => r.rainfall || 0);
        const dailyRainfalls = this.aggregateDaily(readings, 'rainfall');
        const rainfallStats = {
            total: rainfalls.reduce((sum, r) => sum + r, 0),
            dailyAvg: this.average(dailyRainfalls),
            maxDaily: Math.max(...dailyRainfalls),
            rainDays: dailyRainfalls.filter(r => r > 0.1).length,
        };
        // Wind statistics
        const windSpeeds = readings.map(r => r.windSpeed).filter(Boolean);
        const windDirections = readings.map(r => r.windDirection).filter(Boolean);
        const windStats = {
            avg: this.average(windSpeeds),
            max: Math.max(...windSpeeds),
            prevailingDirection: this.calculatePrevailingDirection(windDirections),
        };
        // Pressure statistics
        const pressures = readings.map(r => r.pressure).filter(Boolean);
        const pressureStats = {
            avg: this.average(pressures),
            min: Math.min(...pressures),
            max: Math.max(...pressures),
        };
        // Calculate trends
        const tempTrend = this.calculateSimpleTrend(readings, 'temperature');
        const rainfallTrend = this.calculateSimpleTrend(readings, 'rainfall');
        const pressureTrend = this.calculateSimpleTrend(readings, 'pressure');
        // Detect anomalies
        const anomalies = this.detectSimpleAnomalies(readings);
        return {
            location,
            period,
            startTime,
            endTime,
            stats: {
                temperature: tempStats,
                humidity: humidityStats,
                rainfall: rainfallStats,
                windSpeed: windStats,
                pressure: pressureStats,
            },
            trends: {
                temperatureTrend: tempTrend,
                rainfallTrend: rainfallTrend,
                pressureTrend: pressureTrend,
            },
            anomalies,
        };
    }
    calculatePenmanMonteith(temp, humidity, windSpeed, solarRadiation, pressure, latitude) {
        // Simplified Penman-Monteith equation
        // This is a basic implementation - full version requires more parameters
        const T = temp; // Temperature in Celsius
        const RH = humidity; // Relative humidity in %
        const u2 = windSpeed * 0.277778; // Convert km/h to m/s
        const Rs = solarRadiation; // Solar radiation in W/m²
        const P = pressure; // Atmospheric pressure in kPa
        // Constants
        const sigma = 5.67e-8; // Stefan-Boltzmann constant
        const Gsc = 0.082; // Solar constant
        const albedo = 0.23; // Albedo for grass
        // Saturation vapor pressure
        const es = 0.6108 * Math.exp((17.27 * T) / (T + 237.3));
        const ea = es * RH / 100;
        // Slope of saturation vapor pressure curve
        const delta = (4098 * es) / Math.pow(T + 237.3, 2);
        // Psychrometric constant
        const gamma = 0.665e-3 * P;
        // Net radiation (simplified)
        const Rn = Rs * (1 - albedo) * 0.0864; // Convert to MJ/m²/day
        // Reference ET (simplified FAO-56 equation)
        const numerator = 0.408 * delta * Rn + gamma * (900 / (T + 273)) * u2 * (es - ea);
        const denominator = delta + gamma * (1 + 0.34 * u2);
        const ET0 = numerator / denominator;
        return Math.max(0, ET0); // mm/day
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
    getAggregationInterval(period) {
        const match = period.match(/(\d+)([hdwmy])/);
        if (!match)
            return '1 hour';
        const [, value, unit] = match;
        const num = parseInt(value);
        if (unit === 'h' || (unit === 'd' && num <= 1)) {
            return '1 hour';
        }
        else if (unit === 'd' && num <= 7) {
            return '6 hours';
        }
        else if (unit === 'd' && num <= 30) {
            return '1 day';
        }
        else {
            return '1 week';
        }
    }
    average(values) {
        if (values.length === 0)
            return 0;
        return values.reduce((sum, val) => sum + val, 0) / values.length;
    }
    standardDeviation(values) {
        if (values.length === 0)
            return 0;
        const avg = this.average(values);
        const squaredDiffs = values.map(val => Math.pow(val - avg, 2));
        return Math.sqrt(this.average(squaredDiffs));
    }
    calculatePrevailingDirection(directions) {
        if (directions.length === 0)
            return 0;
        // Convert to vectors and sum
        let sumX = 0;
        let sumY = 0;
        directions.forEach(dir => {
            const rad = (dir * Math.PI) / 180;
            sumX += Math.cos(rad);
            sumY += Math.sin(rad);
        });
        // Calculate average direction
        let avgDir = (Math.atan2(sumY, sumX) * 180) / Math.PI;
        if (avgDir < 0)
            avgDir += 360;
        return Math.round(avgDir);
    }
    aggregateDaily(readings, metric) {
        const dailyMap = new Map();
        readings.forEach(reading => {
            const date = reading.timestamp.toISOString().split('T')[0];
            if (!dailyMap.has(date)) {
                dailyMap.set(date, []);
            }
            const value = reading[metric];
            if (value !== undefined && value !== null) {
                dailyMap.get(date).push(value);
            }
        });
        const dailyValues = [];
        dailyMap.forEach(values => {
            if (metric === 'rainfall') {
                // Sum for rainfall
                dailyValues.push(values.reduce((sum, val) => sum + val, 0));
            }
            else {
                // Average for other metrics
                dailyValues.push(this.average(values));
            }
        });
        return dailyValues;
    }
    calculateSimpleTrend(readings, metric) {
        const values = readings
            .map(r => ({ timestamp: r.timestamp.getTime(), value: r[metric] }))
            .filter(v => v.value !== undefined && v.value !== null);
        if (values.length < 2)
            return 'stable';
        const trend = this.calculateTrend(values);
        if (trend.slope > 0.1)
            return 'increasing';
        if (trend.slope < -0.1)
            return 'decreasing';
        return 'stable';
    }
    calculateTrend(values) {
        const n = values.length;
        if (n < 2)
            return { slope: 0, correlation: 0 };
        // Convert timestamps to numbers
        const data = values.map(v => ({
            x: v.timestamp instanceof Date ? v.timestamp.getTime() : v.timestamp,
            y: v.value,
        }));
        // Calculate means
        const meanX = data.reduce((sum, d) => sum + d.x, 0) / n;
        const meanY = data.reduce((sum, d) => sum + d.y, 0) / n;
        // Calculate slope and correlation
        let numerator = 0;
        let denominatorX = 0;
        let denominatorY = 0;
        data.forEach(d => {
            const dx = d.x - meanX;
            const dy = d.y - meanY;
            numerator += dx * dy;
            denominatorX += dx * dx;
            denominatorY += dy * dy;
        });
        const slope = denominatorX !== 0 ? numerator / denominatorX : 0;
        const correlation = denominatorX !== 0 && denominatorY !== 0
            ? numerator / Math.sqrt(denominatorX * denominatorY)
            : 0;
        return { slope, correlation };
    }
    calculateMovingAverage(values, window) {
        if (values.length < window)
            return [];
        const result = [];
        for (let i = window - 1; i < values.length; i++) {
            const windowValues = values.slice(i - window + 1, i + 1).map(v => v.value);
            result.push({
                timestamp: values[i].timestamp,
                value: this.average(windowValues),
            });
        }
        return result;
    }
    detectSimpleAnomalies(readings) {
        const anomalies = [];
        const threshold = 2.5; // Standard deviations
        // Calculate baselines for each metric
        const temps = readings.map(r => r.temperature).filter(Boolean);
        const tempMean = this.average(temps);
        const tempStdDev = this.standardDeviation(temps);
        // Check each reading for anomalies
        readings.forEach(reading => {
            if (reading.temperature && Math.abs(reading.temperature - tempMean) > threshold * tempStdDev) {
                anomalies.push({
                    date: reading.timestamp,
                    type: 'temperature',
                    value: reading.temperature,
                    deviation: (reading.temperature - tempMean) / tempStdDev,
                });
            }
        });
        return {
            count: anomalies.length,
            events: anomalies.slice(0, 10), // Return top 10 anomalies
        };
    }
    calculateBaseline(values) {
        return {
            mean: this.average(values),
            stdDev: this.standardDeviation(values),
        };
    }
    findExtreme(analytics, metric, subMetric, highest) {
        let extremeIndex = 0;
        let extremeValue = highest ? -Infinity : Infinity;
        analytics.forEach((a, index) => {
            const value = a.stats[metric]?.[subMetric];
            if (value !== undefined) {
                if ((highest && value > extremeValue) || (!highest && value < extremeValue)) {
                    extremeValue = value;
                    extremeIndex = index;
                }
            }
        });
        return extremeIndex;
    }
    findMostStable(analytics, metric) {
        let mostStableIndex = 0;
        let lowestStdDev = Infinity;
        analytics.forEach((a, index) => {
            const stdDev = a.stats[metric]?.stdDev;
            if (stdDev !== undefined && stdDev < lowestStdDev) {
                lowestStdDev = stdDev;
                mostStableIndex = index;
            }
        });
        return mostStableIndex;
    }
}
exports.AnalyticsService = AnalyticsService;
//# sourceMappingURL=analytics.service.js.map