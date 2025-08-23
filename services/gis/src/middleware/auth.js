"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.authenticateJWT = exports.authenticate = void 0;
const jsonwebtoken_1 = __importDefault(require("jsonwebtoken"));
const config_1 = require("../config");
const api_error_1 = require("../utils/api-error");
const authenticate = async (req, res, next) => {
    try {
        const token = extractToken(req);
        if (!token) {
            throw new api_error_1.ApiError(401, 'No authentication token provided');
        }
        const decoded = jsonwebtoken_1.default.verify(token, config_1.config.jwt.secret);
        req.user = decoded;
        next();
    }
    catch (error) {
        if (error.name === 'TokenExpiredError') {
            next(new api_error_1.ApiError(401, 'Token expired'));
        }
        else if (error.name === 'JsonWebTokenError') {
            next(new api_error_1.ApiError(401, 'Invalid token'));
        }
        else {
            next(error);
        }
    }
};
exports.authenticate = authenticate;
exports.authenticateJWT = exports.authenticate;
function extractToken(req) {
    if (req.headers.authorization?.startsWith('Bearer ')) {
        return req.headers.authorization.substring(7);
    }
    return null;
}
//# sourceMappingURL=auth.js.map