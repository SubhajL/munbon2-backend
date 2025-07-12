import Joi from 'joi';
import { UserType } from '../models/user.entity';

export const loginSchema = Joi.object({
  email: Joi.string().email().required(),
  password: Joi.string().required(),
});

export const registerSchema = Joi.object({
  email: Joi.string().email().required(),
  password: Joi.string()
    .min(8)
    .pattern(/^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]/)
    .required()
    .messages({
      'string.pattern.base': 'Password must contain at least one uppercase letter, one lowercase letter, one number, and one special character',
    }),
  confirmPassword: Joi.string().valid(Joi.ref('password')).required(),
  firstName: Joi.string().min(2).max(50).required(),
  lastName: Joi.string().min(2).max(50).required(),
  citizenId: Joi.string().pattern(/^\d{13}$/).optional(),
  phoneNumber: Joi.string().pattern(/^(\+66|0)\d{9}$/).optional(),
  userType: Joi.string().valid(...Object.values(UserType)).default(UserType.FARMER),
  organizationId: Joi.string().uuid().optional(),
  zoneId: Joi.string().optional(),
});

export const refreshTokenSchema = Joi.object({
  refreshToken: Joi.string().optional(), // Can come from cookie
});

export const forgotPasswordSchema = Joi.object({
  email: Joi.string().email().required(),
});

export const resetPasswordSchema = Joi.object({
  token: Joi.string().required(),
  password: Joi.string()
    .min(8)
    .pattern(/^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]/)
    .required(),
  confirmPassword: Joi.string().valid(Joi.ref('password')).required(),
});

export const changePasswordSchema = Joi.object({
  currentPassword: Joi.string().required(),
  newPassword: Joi.string()
    .min(8)
    .pattern(/^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]/)
    .required()
    .invalid(Joi.ref('currentPassword'))
    .messages({
      'any.invalid': 'New password must be different from current password',
    }),
  confirmPassword: Joi.string().valid(Joi.ref('newPassword')).required(),
});

export const verify2FASchema = Joi.object({
  code: Joi.string().pattern(/^\d{6}$/).required(),
});

export const updateProfileSchema = Joi.object({
  firstName: Joi.string().min(2).max(50).optional(),
  lastName: Joi.string().min(2).max(50).optional(),
  phoneNumber: Joi.string().pattern(/^(\+66|0)\d{9}$/).optional(),
  organizationId: Joi.string().uuid().optional(),
  zoneId: Joi.string().optional(),
});