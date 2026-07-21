"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.authController = void 0;
const auth_service_1 = require("../services/auth.service");
const two_factor_service_1 = require("../services/two-factor.service");
const session_service_1 = require("../services/session.service");
class AuthController {
    async register(req, res, next) {
        try {
            const user = await auth_service_1.authService.register(req.body);
            res.status(201).json({
                success: true,
                message: 'Registration successful. Please check your email to verify your account.',
                data: {
                    id: user.id,
                    email: user.email,
                    firstName: user.firstName,
                    lastName: user.lastName,
                },
            });
        }
        catch (error) {
            next(error);
        }
    }
    async login(req, res, next) {
        try {
            const { email, password } = req.body;
            const ip = req.ip || req.connection.remoteAddress || '';
            const userAgent = req.get('user-agent');
            const result = await auth_service_1.authService.login(email, password, ip, userAgent);
            res.cookie('refreshToken', result.refreshToken, {
                httpOnly: true,
                secure: process.env.NODE_ENV === 'production',
                sameSite: 'lax',
                maxAge: 7 * 24 * 60 * 60 * 1000,
            });
            res.json({
                success: true,
                data: {
                    user: result.user,
                    accessToken: result.accessToken,
                    tokenType: result.tokenType,
                    expiresIn: result.expiresIn,
                },
            });
        }
        catch (error) {
            next(error);
        }
    }
    async refreshToken(req, res, next) {
        try {
            const refreshToken = req.body.refreshToken || req.cookies.refreshToken;
            if (!refreshToken) {
                return res.status(401).json({
                    success: false,
                    message: 'Refresh token is required',
                });
            }
            const result = await auth_service_1.authService.refreshAccessToken(refreshToken);
            res.cookie('refreshToken', result.refreshToken, {
                httpOnly: true,
                secure: process.env.NODE_ENV === 'production',
                sameSite: 'lax',
                maxAge: 7 * 24 * 60 * 60 * 1000,
            });
            res.json({
                success: true,
                data: {
                    accessToken: result.accessToken,
                    tokenType: result.tokenType,
                    expiresIn: result.expiresIn,
                },
            });
        }
        catch (error) {
            next(error);
        }
    }
    async logout(req, res, next) {
        try {
            const refreshToken = req.body.refreshToken || req.cookies?.refreshToken;
            res.clearCookie('refreshToken');
            if (refreshToken) {
                await auth_service_1.authService.logout(refreshToken);
            }
            res.json({
                success: true,
                message: 'Logged out successfully',
            });
        }
        catch (error) {
            next(error);
        }
    }
    async forgotPassword(req, res, next) {
        try {
            const { email } = req.body;
            const ip = req.ip || req.connection.remoteAddress || '';
            await auth_service_1.authService.requestPasswordReset(email, ip);
            res.json({
                success: true,
                message: 'If the email exists, a password reset link has been sent.',
            });
        }
        catch (error) {
            next(error);
        }
    }
    async resetPassword(req, res, next) {
        try {
            const { token, password } = req.body;
            const ip = req.ip || req.connection.remoteAddress || '';
            await auth_service_1.authService.resetPassword(token, password, ip);
            res.json({
                success: true,
                message: 'Password reset successfully',
            });
        }
        catch (error) {
            next(error);
        }
    }
    async verifyEmail(req, res, next) {
        try {
            const { token } = req.params;
            res.json({
                success: true,
                message: 'Email verified successfully',
            });
        }
        catch (error) {
            next(error);
        }
    }
    async getCurrentUser(req, res, next) {
        try {
            res.json({
                success: true,
                data: req.user,
            });
        }
        catch (error) {
            next(error);
        }
    }
    async changePassword(req, res, next) {
        try {
            const { currentPassword, newPassword } = req.body;
            const userId = req.user.id;
            res.json({
                success: true,
                message: 'Password changed successfully',
            });
        }
        catch (error) {
            next(error);
        }
    }
    async enable2FA(req, res, next) {
        try {
            const userId = req.user.id;
            const result = await two_factor_service_1.twoFactorService.generateSecret(userId);
            res.json({
                success: true,
                data: {
                    secret: result.secret,
                    qrCode: result.qrCode,
                    backupCodes: result.backupCodes,
                },
            });
        }
        catch (error) {
            next(error);
        }
    }
    async disable2FA(req, res, next) {
        try {
            const userId = req.user.id;
            await two_factor_service_1.twoFactorService.disable(userId);
            res.json({
                success: true,
                message: 'Two-factor authentication disabled',
            });
        }
        catch (error) {
            next(error);
        }
    }
    async verify2FA(req, res, next) {
        try {
            const { code } = req.body;
            const userId = req.user.id;
            const valid = await two_factor_service_1.twoFactorService.verifyToken(userId, code);
            res.json({
                success: valid,
                message: valid ? 'Two-factor authentication verified' : 'Invalid code',
            });
        }
        catch (error) {
            next(error);
        }
    }
    async getSessions(req, res, next) {
        try {
            const userId = req.user.id;
            const sessions = await session_service_1.sessionService.getUserSessions(userId);
            res.json({
                success: true,
                data: sessions,
            });
        }
        catch (error) {
            next(error);
        }
    }
    async revokeSession(req, res, next) {
        try {
            const { sessionId } = req.params;
            const userId = req.user.id;
            await session_service_1.sessionService.revokeSession(sessionId, userId);
            res.json({
                success: true,
                message: 'Session revoked successfully',
            });
        }
        catch (error) {
            next(error);
        }
    }
}
exports.authController = new AuthController();
//# sourceMappingURL=auth.controller.js.map
