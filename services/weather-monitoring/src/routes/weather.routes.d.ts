import { Router } from 'express';
import { DatabaseService } from '../services/database.service';
import { CacheService } from '../services/cache.service';
import { AlertService } from '../services/alert.service';
import { AnalyticsService } from '../services/analytics.service';
import { IrrigationService } from '../services/irrigation.service';
export declare function createWeatherRoutes(databaseService: DatabaseService, cacheService: CacheService, alertService: AlertService, analyticsService: AnalyticsService, irrigationService: IrrigationService): Router;
//# sourceMappingURL=weather.routes.d.ts.map