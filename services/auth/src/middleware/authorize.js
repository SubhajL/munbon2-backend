"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.authorizeRoles = exports.authorize = void 0;
const exceptions_1 = require("../utils/exceptions");
const authorize = (...permissions) => {
    return (req, res, next) => {
        if (!req.user) {
            throw new exceptions_1.ForbiddenException('User not authenticated');
        }
        const hasPermission = permissions.some(permission => req.user.hasPermission(permission));
        if (!hasPermission) {
            throw new exceptions_1.ForbiddenException('Insufficient permissions');
        }
        next();
    };
};
exports.authorize = authorize;
const authorizeRoles = (...roles) => {
    return (req, res, next) => {
        if (!req.user) {
            throw new exceptions_1.ForbiddenException('User not authenticated');
        }
        const hasRole = roles.some(role => req.user.hasRole(role));
        if (!hasRole) {
            throw new exceptions_1.ForbiddenException('Insufficient role privileges');
        }
        next();
    };
};
exports.authorizeRoles = authorizeRoles;
//# sourceMappingURL=authorize.js.map