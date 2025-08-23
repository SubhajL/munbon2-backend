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
exports.CalculationModel = void 0;
const mongoose_1 = __importStar(require("mongoose"));
const CalculationSchema = new mongoose_1.Schema({
    cropType: {
        type: String,
        required: true,
        index: true
    },
    plantings: [{
            plantingDate: {
                type: Date,
                required: true
            },
            areaRai: {
                type: Number,
                required: true
            },
            growthDays: Number
        }],
    calculationDate: {
        type: Date,
        required: true,
        index: true
    },
    calculationPeriod: {
        type: String,
        enum: ['daily', 'weekly', 'monthly'],
        required: true
    },
    results: {
        type: mongoose_1.Schema.Types.Mixed,
        required: true
    },
    metadata: {
        calculatedBy: String,
        sourceFile: String,
        parameters: mongoose_1.Schema.Types.Mixed,
        processingTime: Number,
        version: String
    },
    tags: [String]
}, {
    timestamps: true
});
// Indexes for efficient queries
CalculationSchema.index({ cropType: 1, calculationDate: -1 });
CalculationSchema.index({ 'metadata.calculatedBy': 1, createdAt: -1 });
CalculationSchema.index({ tags: 1 });
// Virtual for total area
CalculationSchema.virtual('totalArea').get(function () {
    return this.plantings.reduce((sum, p) => sum + p.areaRai, 0);
});
exports.CalculationModel = mongoose_1.default.model('Calculation', CalculationSchema);
//# sourceMappingURL=calculationModel.js.map