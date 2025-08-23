"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.DIRECT_SEEDED_SCHEDULE = exports.TRANSPLANTED_SCHEDULE = void 0;
exports.TRANSPLANTED_SCHEDULE = {
    plantingMethod: 'transplanted',
    totalWeeks: 14,
    phases: [
        { week: 0, phase: 'preparation', targetWaterLevel: 10, duration: 2, description: 'Field Preparation Water Release' },
        { week: 1, phase: 'drying', targetWaterLevel: 0, duration: 7, description: 'First Water Supply Suspension' },
        { week: 2, phase: 'wetting', targetWaterLevel: 10, duration: 14, description: 'First Water Application', requiresFertilizer: true },
        { week: 4, phase: 'drying', targetWaterLevel: 0, duration: 21, description: 'Second Water Supply Suspension' },
        { week: 7, phase: 'wetting', targetWaterLevel: 10, duration: 7, description: 'Second Water Application' },
        { week: 8, phase: 'drying', targetWaterLevel: 0, duration: 14, description: 'Third Water Supply Suspension' },
        { week: 10, phase: 'wetting', targetWaterLevel: 10, duration: 14, description: 'Third Water Application' },
        { week: 12, phase: 'drying', targetWaterLevel: 0, duration: 14, description: 'Fourth Water Supply Suspension' },
        { week: 14, phase: 'harvest', targetWaterLevel: 0, duration: 7, description: 'Harvest Preparation' }
    ]
};
exports.DIRECT_SEEDED_SCHEDULE = {
    plantingMethod: 'direct-seeded',
    totalWeeks: 15,
    phases: [
        { week: 0, phase: 'preparation', targetWaterLevel: 10, duration: 2, description: 'Field Preparation Water Release' },
        { week: 1, phase: 'drying', targetWaterLevel: 0, duration: 14, description: 'First Water Supply Suspension (10-15cm growth)' },
        { week: 3, phase: 'wetting', targetWaterLevel: 10, duration: 14, description: 'First Water Application', requiresFertilizer: true },
        { week: 5, phase: 'drying', targetWaterLevel: 0, duration: 21, description: 'Second Water Supply Suspension' },
        { week: 8, phase: 'wetting', targetWaterLevel: 10, duration: 7, description: 'Second Water Application' },
        { week: 9, phase: 'drying', targetWaterLevel: 0, duration: 14, description: 'Third Water Supply Suspension' },
        { week: 11, phase: 'wetting', targetWaterLevel: 10, duration: 14, description: 'Third Water Application' },
        { week: 13, phase: 'drying', targetWaterLevel: 0, duration: 14, description: 'Fourth Water Supply Suspension' },
        { week: 15, phase: 'harvest', targetWaterLevel: 0, duration: 7, description: 'Harvest Preparation' }
    ]
};
//# sourceMappingURL=awd-control.types.js.map