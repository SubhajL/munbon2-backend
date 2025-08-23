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
exports.ReportModel = void 0;
const mongoose_1 = __importStar(require("mongoose"));
const ReportSchema = new mongoose_1.Schema({
    calculationId: {
        type: String,
        required: true,
        index: true
    },
    format: {
        type: String,
        enum: ['pdf', 'excel', 'csv'],
        required: true
    },
    filename: {
        type: String,
        required: true
    },
    filePath: {
        type: String,
        required: true
    },
    status: {
        type: String,
        enum: ['pending', 'generating', 'completed', 'failed'],
        default: 'pending'
    },
    metadata: {
        generatedBy: String,
        options: mongoose_1.Schema.Types.Mixed,
        error: String
    },
    generatedAt: {
        type: Date,
        default: Date.now
    },
    expiresAt: Date
}, {
    timestamps: true
});
// Index for cleanup queries
ReportSchema.index({ generatedAt: 1 });
ReportSchema.index({ status: 1, generatedAt: 1 });
exports.ReportModel = mongoose_1.default.model('Report', ReportSchema);
//# sourceMappingURL=reportModel.js.map