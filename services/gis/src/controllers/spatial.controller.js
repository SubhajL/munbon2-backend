"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.spatialController = void 0;
const spatial_service_1 = require("../services/spatial.service");
const turf = __importStar(require("@turf/turf"));
class SpatialController {
    async queryByBounds(req, res, next) {
        try {
            const { tableName, bounds, properties } = req.body;
            const features = await spatial_service_1.spatialService.findWithinBounds(tableName, bounds, properties);
            res.json({
                success: true,
                data: features,
                count: features.features.length,
            });
        }
        catch (error) {
            next(error);
        }
    }
    async queryByDistance(req, res, next) {
        try {
            const { tableName, center, distance, unit, properties } = req.body;
            const features = await spatial_service_1.spatialService.findWithinDistance(tableName, center, distance, unit, properties);
            res.json({
                success: true,
                data: features,
                count: features.features.length,
            });
        }
        catch (error) {
            next(error);
        }
    }
    async queryByIntersection(req, res, next) {
        try {
            const { tableName, geometry, properties } = req.body;
            const features = await spatial_service_1.spatialService.findIntersecting(tableName, geometry, properties);
            res.json({
                success: true,
                data: features,
                count: features.features.length,
            });
        }
        catch (error) {
            next(error);
        }
    }
    async buffer(req, res, next) {
        try {
            const { geometry, distance, unit, options } = req.body;
            const buffered = await spatial_service_1.spatialService.buffer(geometry, { distance, unit, ...options });
            res.json({
                success: true,
                data: buffered,
            });
        }
        catch (error) {
            next(error);
        }
    }
    async union(req, res, next) {
        try {
            const { geometries } = req.body;
            const unioned = await spatial_service_1.spatialService.union(geometries);
            res.json({
                success: true,
                data: unioned,
            });
        }
        catch (error) {
            next(error);
        }
    }
    async intersection(req, res, next) {
        try {
            const { geometry1, geometry2 } = req.body;
            const intersection = await spatial_service_1.spatialService.intersection(geometry1, geometry2);
            res.json({
                success: true,
                data: intersection,
            });
        }
        catch (error) {
            next(error);
        }
    }
    async simplify(req, res, next) {
        try {
            const { geometry, tolerance, highQuality } = req.body;
            const simplified = await spatial_service_1.spatialService.simplify(geometry, tolerance || 0.01, highQuality !== false);
            res.json({
                success: true,
                data: simplified,
            });
        }
        catch (error) {
            next(error);
        }
    }
    async transform(req, res, next) {
        try {
            const { geometry, fromSrid, toSrid } = req.body;
            const transformed = await spatial_service_1.spatialService.transform(geometry, fromSrid || 4326, toSrid || 32647);
            res.json({
                success: true,
                data: transformed,
            });
        }
        catch (error) {
            next(error);
        }
    }
    async calculateArea(req, res, next) {
        try {
            const { geometry, unit } = req.body;
            const area = await spatial_service_1.spatialService.calculateArea(geometry, unit);
            res.json({
                success: true,
                data: {
                    area,
                    unit: unit || 'hectares',
                },
            });
        }
        catch (error) {
            next(error);
        }
    }
    async calculateLength(req, res, next) {
        try {
            const { geometry, unit } = req.body;
            const length = await spatial_service_1.spatialService.calculateLength(geometry, unit);
            res.json({
                success: true,
                data: {
                    length,
                    unit: unit || 'meters',
                },
            });
        }
        catch (error) {
            next(error);
        }
    }
    async calculateDistance(req, res, next) {
        try {
            const { point1, point2, unit } = req.body;
            const distance = turf.distance(turf.point(point1), turf.point(point2), { units: unit || 'meters' });
            res.json({
                success: true,
                data: {
                    distance,
                    unit: unit || 'meters',
                },
            });
        }
        catch (error) {
            next(error);
        }
    }
    async getElevation(req, res, next) {
        try {
            const { lng, lat } = req.params;
            const elevation = await spatial_service_1.spatialService.getElevation(Number(lng), Number(lat));
            res.json({
                success: true,
                data: {
                    longitude: Number(lng),
                    latitude: Number(lat),
                    elevation,
                    unit: 'meters',
                },
            });
        }
        catch (error) {
            next(error);
        }
    }
}
exports.spatialController = new SpatialController();
//# sourceMappingURL=spatial.controller.js.map