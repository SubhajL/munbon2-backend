"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.authenticateOptional = exports.authenticate = void 0;
const passport_1 = __importDefault(require("passport"));
const exceptions_1 = require("../utils/exceptions");
const authenticate = (req, res, next) => {
    passport_1.default.authenticate('jwt', { session: false }, (err, user, info) => {
        if (err) {
            return next(err);
        }
        if (!user) {
            throw new exceptions_1.UnauthorizedException(info?.message || 'Authentication required');
        }
        req.user = user;
        next();
    })(req, res, next);
};
exports.authenticate = authenticate;
const authenticateOptional = (req, res, next) => {
    passport_1.default.authenticate('jwt', { session: false }, (err, user) => {
        if (err) {
            return next(err);
        }
        req.user = user || null;
        next();
    })(req, res, next);
};
exports.authenticateOptional = authenticateOptional;
//# sourceMappingURL=authenticate.js.map