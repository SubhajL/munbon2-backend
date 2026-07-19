"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.authService = void 0;
const jsonwebtoken_1 = __importDefault(require("jsonwebtoken"));
const axios_1 = __importDefault(require("axios"));
const database_1 = require("../config/database");
const config_1 = require("../config");
const user_entity_1 = require("../models/user.entity");
const refresh_token_entity_1 = require("../models/refresh-token.entity");
const login_attempt_entity_1 = require("../models/login-attempt.entity");
const password_reset_entity_1 = require("../models/password-reset.entity");
const audit_log_entity_1 = require("../models/audit-log.entity");
const user_service_1 = require("./user.service");
const token_signer_1 = require("./token-signer");
const email_service_1 = require("./email.service");
const audit_service_1 = require("./audit.service");
const logger_1 = require("../utils/logger");
const exceptions_1 = require("../utils/exceptions");
const crypto_1 = require("../utils/crypto");
class AuthService {
    userRepository;
    refreshTokenRepository;
    loginAttemptRepository;
    passwordResetRepository;
    constructor() {
        this.userRepository = database_1.AppDataSource.getRepository(user_entity_1.User);
        this.refreshTokenRepository = database_1.AppDataSource.getRepository(refresh_token_entity_1.RefreshToken);
        this.loginAttemptRepository = database_1.AppDataSource.getRepository(login_attempt_entity_1.LoginAttempt);
        this.passwordResetRepository = database_1.AppDataSource.getRepository(password_reset_entity_1.PasswordReset);
    }
    async register(data) {
        const existingUser = await this.userRepository.findOne({
            where: [
                { email: data.email },
                { citizenId: data.citizenId },
                { phoneNumber: data.phoneNumber },
            ].filter(condition => Object.values(condition)[0]),
        });
        if (existingUser) {
            throw new exceptions_1.ConflictException('User already exists');
        }
        const user = this.userRepository.create({
            ...data,
            status: user_entity_1.UserStatus.ACTIVE,
            emailVerified: false,
        });
        const defaultRole = await user_service_1.userService.getDefaultRoleForUserType(user.userType);
        if (defaultRole) {
            user.roles = [defaultRole];
        }
        await this.userRepository.save(user);
        await email_service_1.emailService.sendVerificationEmail(user);
        await audit_service_1.auditService.log({
            userId: user.id,
            action: audit_log_entity_1.AuditAction.USER_CREATE,
            resource: `user:${user.id}`,
            description: 'User registered',
            success: true,
        });
        return user;
    }
    async login(email, password, ip, userAgent) {
        const loginAttempt = this.loginAttemptRepository.create({
            email,
            ip,
            userAgent,
        });
        try {
            const user = await this.validateUser(email, password);
            if (!user) {
                loginAttempt.status = login_attempt_entity_1.LoginAttemptStatus.FAILED;
                loginAttempt.reason = 'Invalid credentials';
                await this.loginAttemptRepository.save(loginAttempt);
                throw new exceptions_1.UnauthorizedException('Invalid credentials');
            }
            if (user.isLocked()) {
                loginAttempt.status = login_attempt_entity_1.LoginAttemptStatus.BLOCKED;
                loginAttempt.reason = 'Account locked';
                loginAttempt.userId = user.id;
                await this.loginAttemptRepository.save(loginAttempt);
                throw new exceptions_1.ForbiddenException('Account is locked');
            }
            const { accessToken, refreshToken, expiresIn } = await this.generateTokens(user);
            const refreshTokenEntity = this.refreshTokenRepository.create({
                token: refreshToken,
                userId: user.id,
                deviceName: userAgent,
                userAgent,
                ip,
                expiresAt: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000),
            });
            await this.refreshTokenRepository.save(refreshTokenEntity);
            user.lastLoginAt = new Date();
            user.lastLoginIp = ip;
            user.failedLoginAttempts = 0;
            user.lockedUntil = null;
            await this.userRepository.save(user);
            loginAttempt.status = login_attempt_entity_1.LoginAttemptStatus.SUCCESS;
            loginAttempt.userId = user.id;
            await this.loginAttemptRepository.save(loginAttempt);
            await audit_service_1.auditService.log({
                userId: user.id,
                action: audit_log_entity_1.AuditAction.LOGIN,
                resource: `user:${user.id}`,
                description: 'User logged in',
                ip,
                userAgent,
                success: true,
            });
            return {
                user,
                accessToken,
                refreshToken,
                expiresIn,
                tokenType: 'Bearer',
            };
        }
        catch (error) {
            const user = await this.userRepository.findOne({ where: { email } });
            if (user) {
                user.failedLoginAttempts += 1;
                if (user.failedLoginAttempts >= config_1.config.security.maxLoginAttempts) {
                    user.lockedUntil = new Date(Date.now() + config_1.config.security.lockoutDuration * 60 * 1000);
                    user.status = user_entity_1.UserStatus.LOCKED;
                }
                await this.userRepository.save(user);
            }
            throw error;
        }
    }
    async validateUser(email, password) {
        const user = await this.userRepository.findOne({
            where: { email },
            select: ['id', 'email', 'password', 'status', 'lockedUntil', 'failedLoginAttempts'],
            relations: ['roles', 'roles.permissions'],
        });
        if (!user || !(await user.comparePassword(password))) {
            return null;
        }
        return user;
    }
    async refreshAccessToken(refreshToken) {
        const payload = jsonwebtoken_1.default.verify(refreshToken, config_1.config.jwt.secret);
        if (payload.type !== 'refresh') {
            throw new exceptions_1.UnauthorizedException('Invalid token type');
        }
        const tokenEntity = await this.refreshTokenRepository.findOne({
            where: { token: refreshToken },
            relations: ['user', 'user.roles', 'user.roles.permissions'],
        });
        if (!tokenEntity || !tokenEntity.isValid()) {
            throw new exceptions_1.UnauthorizedException('Invalid refresh token');
        }
        const user = tokenEntity.user;
        const { accessToken, refreshToken: newRefreshToken, expiresIn } = await this.generateTokens(user);
        tokenEntity.revoke(user.id, 'Token refresh');
        await this.refreshTokenRepository.save(tokenEntity);
        const newTokenEntity = this.refreshTokenRepository.create({
            token: newRefreshToken,
            userId: user.id,
            deviceName: tokenEntity.deviceName,
            userAgent: tokenEntity.userAgent,
            ip: tokenEntity.ip,
            expiresAt: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000),
        });
        await this.refreshTokenRepository.save(newTokenEntity);
        await audit_service_1.auditService.log({
            userId: user.id,
            action: audit_log_entity_1.AuditAction.TOKEN_REFRESH,
            resource: `user:${user.id}`,
            description: 'Access token refreshed',
            success: true,
        });
        return {
            user,
            accessToken,
            refreshToken: newRefreshToken,
            expiresIn,
            tokenType: 'Bearer',
        };
    }
    async logout(userId, refreshToken) {
        if (refreshToken) {
            const token = await this.refreshTokenRepository.findOne({
                where: { token: refreshToken, userId },
            });
            if (token) {
                token.revoke(userId, 'User logout');
                await this.refreshTokenRepository.save(token);
            }
        }
        else {
            await this.refreshTokenRepository.update({ userId, isActive: true }, { isActive: false, revokedAt: new Date(), revokedBy: userId });
        }
        await audit_service_1.auditService.log({
            userId,
            action: audit_log_entity_1.AuditAction.LOGOUT,
            resource: `user:${userId}`,
            description: 'User logged out',
            success: true,
        });
    }
    async requestPasswordReset(email, ip) {
        const user = await this.userRepository.findOne({ where: { email } });
        if (!user) {
            logger_1.logger.info(`Password reset requested for non-existent email: ${email}`);
            return;
        }
        const token = (0, crypto_1.generateRandomString)(32);
        const expiresAt = new Date(Date.now() + 60 * 60 * 1000);
        const passwordReset = this.passwordResetRepository.create({
            email,
            userId: user.id,
            token,
            expiresAt,
            ip,
        });
        await this.passwordResetRepository.save(passwordReset);
        await email_service_1.emailService.sendPasswordResetEmail(user, token);
        await audit_service_1.auditService.log({
            userId: user.id,
            action: audit_log_entity_1.AuditAction.PASSWORD_RESET_REQUEST,
            resource: `user:${user.id}`,
            description: 'Password reset requested',
            ip,
            success: true,
        });
    }
    async resetPassword(token, newPassword, ip) {
        const resetToken = await this.passwordResetRepository.findOne({
            where: { token },
            relations: ['user'],
        });
        if (!resetToken || !resetToken.isValid()) {
            throw new exceptions_1.BadRequestException('Invalid or expired reset token');
        }
        const user = resetToken.user;
        user.password = newPassword;
        user.failedLoginAttempts = 0;
        user.lockedUntil = null;
        user.status = user_entity_1.UserStatus.ACTIVE;
        await this.userRepository.save(user);
        resetToken.markAsUsed();
        resetToken.ip = ip;
        await this.passwordResetRepository.save(resetToken);
        await this.refreshTokenRepository.update({ userId: user.id, isActive: true }, { isActive: false, revokedAt: new Date(), revokeReason: 'Password reset' });
        await email_service_1.emailService.sendPasswordResetConfirmation(user);
        await audit_service_1.auditService.log({
            userId: user.id,
            action: audit_log_entity_1.AuditAction.PASSWORD_RESET_COMPLETE,
            resource: `user:${user.id}`,
            description: 'Password reset completed',
            ip,
            success: true,
        });
    }
    async getThaiDigitalIdUserInfo(accessToken) {
        try {
            const response = await axios_1.default.get(config_1.config.thaiDigitalId.userinfoUrl, {
                headers: {
                    Authorization: `Bearer ${accessToken}`,
                },
            });
            return response.data;
        }
        catch (error) {
            logger_1.logger.error('Failed to get Thai Digital ID user info:', error);
            throw new Error('Failed to get user information from Thai Digital ID');
        }
    }
    async findOrCreateFromThaiDigitalId(userInfo) {
        let user = await this.userRepository.findOne({
            where: [
                { thaiDigitalId: userInfo.sub },
                { citizenId: userInfo.citizen_id },
                { email: userInfo.email },
            ].filter(condition => Object.values(condition)[0]),
            relations: ['roles', 'roles.permissions'],
        });
        if (user) {
            if (!user.thaiDigitalId) {
                user.thaiDigitalId = userInfo.sub;
                user.emailVerified = true;
                user.emailVerifiedAt = new Date();
                await this.userRepository.save(user);
            }
        }
        else {
            user = await this.register({
                email: userInfo.email,
                password: (0, crypto_1.generateRandomString)(16),
                firstName: userInfo.given_name || userInfo.name?.split(' ')[0] || '',
                lastName: userInfo.family_name || userInfo.name?.split(' ').slice(1).join(' ') || '',
                citizenId: userInfo.citizen_id,
                phoneNumber: userInfo.phone_number,
                userType: userInfo.user_type || 'farmer',
            });
            user.thaiDigitalId = userInfo.sub;
            user.emailVerified = true;
            user.emailVerifiedAt = new Date();
            await this.userRepository.save(user);
        }
        return user;
    }
    async generateTokens(user) {
        const roles = user.roles.map(role => role.name);
        return (0, token_signer_1.signAuthTokenPair)({ sub: user.id, email: user.email, roles }, config_1.config.jwt);
    }
}
exports.authService = new AuthService();
//# sourceMappingURL=auth.service.js.map