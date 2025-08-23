import Joi from 'joi';
export declare const rainfallValidation: {
    getWeeklyRainfall: {
        params: Joi.ObjectSchema<any>;
        query: Joi.ObjectSchema<any>;
    };
    addRainfall: {
        body: Joi.ObjectSchema<any>;
    };
    importRainfall: {
        body: Joi.ObjectSchema<any>;
    };
    getRainfallHistory: {
        params: Joi.ObjectSchema<any>;
        query: Joi.ObjectSchema<any>;
    };
    updateRainfall: {
        params: Joi.ObjectSchema<any>;
        body: Joi.ObjectSchema<any>;
    };
    deleteRainfall: {
        params: Joi.ObjectSchema<any>;
    };
    getRainfallStatistics: {
        params: Joi.ObjectSchema<any>;
        query: Joi.ObjectSchema<any>;
    };
};
//# sourceMappingURL=rainfall.validation.d.ts.map