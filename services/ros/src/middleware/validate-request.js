"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.validateRequest = validateRequest;
const logger_1 = require("@utils/logger");
function validateRequest(schema) {
    return (req, res, next) => {
        const errors = [];
        // Validate body
        if (schema.body) {
            const { error } = schema.body.validate(req.body);
            if (error) {
                errors.push(...error.details.map(detail => detail.message));
            }
        }
        // Validate query
        if (schema.query) {
            const { error } = schema.query.validate(req.query);
            if (error) {
                errors.push(...error.details.map(detail => detail.message));
            }
        }
        // Validate params
        if (schema.params) {
            const { error } = schema.params.validate(req.params);
            if (error) {
                errors.push(...error.details.map(detail => detail.message));
            }
        }
        if (errors.length > 0) {
            logger_1.logger.warn('Validation error', { errors, url: req.url });
            res.status(400).json({
                success: false,
                message: 'Validation error',
                errors,
            });
            return;
        }
        next();
    };
}
//# sourceMappingURL=validate-request.js.map