"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.twoFactorService = void 0;
const otplib_1 = require("otplib");
const qrcode_1 = __importDefault(require("qrcode"));
const database_1 = require("../config/database");
const config_1 = require("../config");
const two_factor_secret_entity_1 = require("../models/two-factor-secret.entity");
const user_service_1 = require("./user.service");
const crypto_1 = require("../utils/crypto");
const exceptions_1 = require("../utils/exceptions");
class TwoFactorService {
    twoFactorSecretRepository;
    constructor() {
        this.twoFactorSecretRepository = database_1.AppDataSource.getRepository(two_factor_secret_entity_1.TwoFactorSecret);
        otplib_1.authenticator.options = {
            window: config_1.config.totp.window,
        };
    }
    async generateSecret(userId) {
        const user = await user_service_1.userService.findById(userId);
        const existing = await this.twoFactorSecretRepository.findOne({
            where: { userId },
        });
        if (existing && existing.verified) {
            throw new exceptions_1.BadRequestException('Two-factor authentication is already enabled');
        }
        const secret = otplib_1.authenticator.generateSecret();
        const backupCodes = (0, crypto_1.generateBackupCodes)();
        const otpauth = otplib_1.authenticator.keyuri(user.email, config_1.config.totp.issuer, secret);
        const qrCode = await qrcode_1.default.toDataURL(otpauth);
        if (existing) {
            existing.secret = secret;
            existing.backupCodes = backupCodes;
            existing.usedBackupCodes = [];
            existing.verified = false;
            await this.twoFactorSecretRepository.save(existing);
        }
        else {
            const twoFactorSecret = this.twoFactorSecretRepository.create({
                userId,
                secret,
                backupCodes,
                verified: false,
            });
            await this.twoFactorSecretRepository.save(twoFactorSecret);
        }
        return {
            secret,
            qrCode,
            backupCodes,
        };
    }
    async verifyAndEnable(userId, token) {
        const twoFactorSecret = await this.twoFactorSecretRepository.findOne({
            where: { userId },
        });
        if (!twoFactorSecret) {
            throw new exceptions_1.NotFoundException('Two-factor secret not found');
        }
        if (twoFactorSecret.verified) {
            throw new exceptions_1.BadRequestException('Two-factor authentication is already enabled');
        }
        const isValid = otplib_1.authenticator.verify({
            token,
            secret: twoFactorSecret.secret,
        });
        if (!isValid) {
            return false;
        }
        twoFactorSecret.verified = true;
        twoFactorSecret.verifiedAt = new Date();
        await this.twoFactorSecretRepository.save(twoFactorSecret);
        const user = await user_service_1.userService.findById(userId);
        user.twoFactorEnabled = true;
        await user_service_1.userService.update(userId, { twoFactorEnabled: true }, userId);
        return true;
    }
    async verifyToken(userId, token) {
        const twoFactorSecret = await this.twoFactorSecretRepository.findOne({
            where: { userId, verified: true },
        });
        if (!twoFactorSecret) {
            return false;
        }
        if (token.length === 8 && /^[A-Z0-9]+$/.test(token)) {
            const isValid = twoFactorSecret.useBackupCode(token);
            if (isValid) {
                twoFactorSecret.lastUsedAt = new Date();
                await this.twoFactorSecretRepository.save(twoFactorSecret);
                return true;
            }
        }
        const isValid = otplib_1.authenticator.verify({
            token,
            secret: twoFactorSecret.secret,
        });
        if (isValid) {
            twoFactorSecret.lastUsedAt = new Date();
            await this.twoFactorSecretRepository.save(twoFactorSecret);
        }
        return isValid;
    }
    async disable(userId) {
        const twoFactorSecret = await this.twoFactorSecretRepository.findOne({
            where: { userId },
        });
        if (twoFactorSecret) {
            await this.twoFactorSecretRepository.remove(twoFactorSecret);
        }
        await user_service_1.userService.disable2FA(userId, userId);
    }
    async regenerateBackupCodes(userId) {
        const twoFactorSecret = await this.twoFactorSecretRepository.findOne({
            where: { userId, verified: true },
        });
        if (!twoFactorSecret) {
            throw new exceptions_1.NotFoundException('Two-factor authentication is not enabled');
        }
        const newBackupCodes = (0, crypto_1.generateBackupCodes)();
        twoFactorSecret.backupCodes = newBackupCodes;
        twoFactorSecret.usedBackupCodes = [];
        await this.twoFactorSecretRepository.save(twoFactorSecret);
        return newBackupCodes;
    }
    async isEnabled(userId) {
        const twoFactorSecret = await this.twoFactorSecretRepository.findOne({
            where: { userId, verified: true },
        });
        return !!twoFactorSecret;
    }
}
exports.twoFactorService = new TwoFactorService();
//# sourceMappingURL=two-factor.service.js.map