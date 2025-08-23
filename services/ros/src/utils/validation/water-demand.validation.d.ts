import Joi from 'joi';
export declare const waterDemandValidation: {
    calculateWaterDemand: {
        body: Joi.ObjectSchema<any>;
    };
    calculateSeasonalWaterDemand: {
        body: Joi.ObjectSchema<any>;
    };
    getWaterDemandByCropWeek: {
        params: Joi.ObjectSchema<any>;
        query: Joi.ObjectSchema<any>;
    };
    getSeasonalWaterDemandByWeek: {
        params: Joi.ObjectSchema<any>;
        query: Joi.ObjectSchema<any>;
    };
    getWaterDemandSummary: {
        params: Joi.ObjectSchema<any>;
        query: Joi.ObjectSchema<any>;
    };
};
//# sourceMappingURL=water-demand.validation.d.ts.map