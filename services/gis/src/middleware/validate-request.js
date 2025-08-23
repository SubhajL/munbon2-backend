"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.validateRequest = void 0;
const api_error_1 = require("../utils/api-error");
const validateRequest = (schema) => {
    return async (req, res, next) => {
        try {
            await schema.parseAsync({
                body: req.body,
                query: req.query,
                params: req.params,
            });
            next();
        }
        catch (error) {
            const errorMessage = error.errors?.map((e) => ({
                field: e.path.join('.'),
                message: e.message,
            }));
            next(new api_error_1.ApiError(400, 'Validation error', errorMessage));
        }
    };
};
exports.validateRequest = validateRequest;
//# sourceMappingURL=validate-request.js.map