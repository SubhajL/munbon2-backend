"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.authorize = void 0;
const api_error_1 = require("../utils/api-error");
const authorize = (allowedRoles) => {
    return (req, res, next) => {
        if (!req.user) {
            next(new api_error_1.ApiError(401, 'Authentication required'));
            return;
        }
        const userRoles = req.user.roles || [];
        const hasPermission = userRoles.some(role => allowedRoles.includes(role));
        if (!hasPermission) {
            next(new api_error_1.ApiError(403, 'Insufficient permissions'));
            return;
        }
        next();
    };
};
exports.authorize = authorize;
//# sourceMappingURL=authorize.js.map