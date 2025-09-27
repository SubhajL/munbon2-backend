"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.updateProfileSchema = exports.verify2FASchema = exports.changePasswordSchema = exports.resetPasswordSchema = exports.forgotPasswordSchema = exports.refreshTokenSchema = exports.registerSchema = exports.loginSchema = void 0;
const joi_1 = __importDefault(require("joi"));
const user_entity_1 = require("../models/user.entity");
exports.loginSchema = joi_1.default.object({
    email: joi_1.default.string().email().required(),
    password: joi_1.default.string().required(),
});
exports.registerSchema = joi_1.default.object({
    email: joi_1.default.string().email().required(),
    password: joi_1.default.string()
        .min(8)
        .pattern(/^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]/)
        .required()
        .messages({
        'string.pattern.base': 'Password must contain at least one uppercase letter, one lowercase letter, one number, and one special character',
    }),
    confirmPassword: joi_1.default.string().valid(joi_1.default.ref('password')).required(),
    firstName: joi_1.default.string().min(2).max(50).required(),
    lastName: joi_1.default.string().min(2).max(50).required(),
    citizenId: joi_1.default.string().pattern(/^\d{13}$/).optional(),
    phoneNumber: joi_1.default.string().pattern(/^(\+66|0)\d{9}$/).optional(),
    userType: joi_1.default.string().valid(...Object.values(user_entity_1.UserType)).default(user_entity_1.UserType.FARMER),
    organizationId: joi_1.default.string().uuid().optional(),
    zoneId: joi_1.default.string().optional(),
});
exports.refreshTokenSchema = joi_1.default.object({
    refreshToken: joi_1.default.string().optional(),
});
exports.forgotPasswordSchema = joi_1.default.object({
    email: joi_1.default.string().email().required(),
});
exports.resetPasswordSchema = joi_1.default.object({
    token: joi_1.default.string().required(),
    password: joi_1.default.string()
        .min(8)
        .pattern(/^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]/)
        .required(),
    confirmPassword: joi_1.default.string().valid(joi_1.default.ref('password')).required(),
});
exports.changePasswordSchema = joi_1.default.object({
    currentPassword: joi_1.default.string().required(),
    newPassword: joi_1.default.string()
        .min(8)
        .pattern(/^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]/)
        .required()
        .invalid(joi_1.default.ref('currentPassword'))
        .messages({
        'any.invalid': 'New password must be different from current password',
    }),
    confirmPassword: joi_1.default.string().valid(joi_1.default.ref('newPassword')).required(),
});
exports.verify2FASchema = joi_1.default.object({
    code: joi_1.default.string().pattern(/^\d{6}$/).required(),
});
exports.updateProfileSchema = joi_1.default.object({
    firstName: joi_1.default.string().min(2).max(50).optional(),
    lastName: joi_1.default.string().min(2).max(50).optional(),
    phoneNumber: joi_1.default.string().pattern(/^(\+66|0)\d{9}$/).optional(),
    organizationId: joi_1.default.string().uuid().optional(),
    zoneId: joi_1.default.string().optional(),
});
//# sourceMappingURL=auth.validator.js.map