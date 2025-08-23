import Joi from 'joi';
export declare const areaValidation: {
    createArea: {
        body: Joi.ObjectSchema<any>;
    };
    getAreaById: {
        params: Joi.ObjectSchema<any>;
    };
    updateArea: {
        params: Joi.ObjectSchema<any>;
        body: Joi.ObjectSchema<any>;
    };
    deleteArea: {
        params: Joi.ObjectSchema<any>;
    };
    getAreasByType: {
        params: Joi.ObjectSchema<any>;
    };
    getChildAreas: {
        params: Joi.ObjectSchema<any>;
    };
    getAreaHierarchy: {
        params: Joi.ObjectSchema<any>;
    };
    calculateTotalArea: {
        params: Joi.ObjectSchema<any>;
    };
    importAreas: {
        body: Joi.ObjectSchema<any>;
    };
};
//# sourceMappingURL=area.validation.d.ts.map