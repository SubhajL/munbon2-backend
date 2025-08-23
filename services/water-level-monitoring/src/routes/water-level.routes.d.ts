import { Router } from 'express';
import { TimescaleService } from '../services/timescale.service';
import { CacheService } from '../services/cache.service';
import { AlertService } from '../services/alert.service';
import { GateControlService } from '../services/gate-control.service';
export declare function createWaterLevelRoutes(timescaleService: TimescaleService, cacheService: CacheService, alertService: AlertService, gateControlService: GateControlService): Router;
//# sourceMappingURL=water-level.routes.d.ts.map