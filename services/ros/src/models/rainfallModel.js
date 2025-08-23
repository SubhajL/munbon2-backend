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
exports.RainfallModel = void 0;
const mongoose_1 = __importStar(require("mongoose"));
const RainfallSchema = new mongoose_1.Schema({
    location: {
        type: String,
        default: 'Munbon'
    },
    year: {
        type: Number,
        required: true
    },
    month: {
        type: Number,
        required: true,
        min: 1,
        max: 12
    },
    totalRainfall: {
        type: Number,
        required: true,
        min: 0
    },
    effectiveRainfall: {
        type: Number,
        required: true,
        min: 0
    },
    numberOfRainyDays: {
        type: Number,
        min: 0,
        max: 31
    },
    maxDailyRainfall: Number,
    probabilityOfRain: {
        type: Number,
        min: 0,
        max: 100
    },
    source: {
        type: String,
        default: 'Excel lookup table'
    }
}, {
    timestamps: true
});
// Compound index for efficient lookups
RainfallSchema.index({ year: 1, month: 1, location: 1 }, { unique: true });
exports.RainfallModel = mongoose_1.default.model('Rainfall', RainfallSchema);
//# sourceMappingURL=rainfallModel.js.map