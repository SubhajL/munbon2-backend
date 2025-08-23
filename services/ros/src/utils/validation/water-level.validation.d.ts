import Joi from 'joi';
export declare const waterLevelValidation: {
    getCurrentLevel: {
        params: Joi.ObjectSchema<any>;
    };
    addWaterLevel: {
        body: Joi.ObjectSchema<any>;
    };
    importWaterLevels: {
        body: Joi.ObjectSchema<any>;
    };
    getWaterLevelHistory: {
        params: Joi.ObjectSchema<any>;
        query: Joi.ObjectSchema<any>;
    };
    updateWaterLevel: {
        params: Joi.ObjectSchema<any>;
        body: Joi.ObjectSchema<any>;
    };
    deleteWaterLevel: {
        params: Joi.ObjectSchema<any>;
    };
    getWaterLevelStatistics: {
        params: Joi.ObjectSchema<any>;
        query: Joi.ObjectSchema<any>;
    };
    getWaterLevelTrends: {
        params: Joi.ObjectSchema<any>;
        query: Joi.ObjectSchema<any>;
    };
};
//# sourceMappingURL=water-level.validation.d.ts.map