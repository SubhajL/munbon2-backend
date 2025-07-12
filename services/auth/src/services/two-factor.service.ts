import { Repository } from 'typeorm';
import { authenticator } from 'otplib';
import QRCode from 'qrcode';
import { AppDataSource } from '../config/database';
import { config } from '../config';
import { TwoFactorSecret } from '../models/two-factor-secret.entity';
import { userService } from './user.service';
import { generateBackupCodes } from '../utils/crypto';
import { BadRequestException, NotFoundException } from '../utils/exceptions';

interface GenerateSecretResult {
  secret: string;
  qrCode: string;
  backupCodes: string[];
}

class TwoFactorService {
  private twoFactorSecretRepository: Repository<TwoFactorSecret>;

  constructor() {
    this.twoFactorSecretRepository = AppDataSource.getRepository(TwoFactorSecret);
    authenticator.options = {
      window: config.totp.window,
    };
  }

  async generateSecret(userId: string): Promise<GenerateSecretResult> {
    const user = await userService.findById(userId);

    // Check if user already has 2FA
    const existing = await this.twoFactorSecretRepository.findOne({
      where: { userId },
    });

    if (existing && existing.verified) {
      throw new BadRequestException('Two-factor authentication is already enabled');
    }

    // Generate new secret
    const secret = authenticator.generateSecret();
    const backupCodes = generateBackupCodes();

    // Generate QR code
    const otpauth = authenticator.keyuri(
      user.email,
      config.totp.issuer,
      secret
    );
    const qrCode = await QRCode.toDataURL(otpauth);

    // Save or update secret
    if (existing) {
      existing.secret = secret;
      existing.backupCodes = backupCodes;
      existing.usedBackupCodes = [];
      existing.verified = false;
      await this.twoFactorSecretRepository.save(existing);
    } else {
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

  async verifyAndEnable(userId: string, token: string): Promise<boolean> {
    const twoFactorSecret = await this.twoFactorSecretRepository.findOne({
      where: { userId },
    });

    if (!twoFactorSecret) {
      throw new NotFoundException('Two-factor secret not found');
    }

    if (twoFactorSecret.verified) {
      throw new BadRequestException('Two-factor authentication is already enabled');
    }

    // Verify token
    const isValid = authenticator.verify({
      token,
      secret: twoFactorSecret.secret,
    });

    if (!isValid) {
      return false;
    }

    // Enable 2FA
    twoFactorSecret.verified = true;
    twoFactorSecret.verifiedAt = new Date();
    await this.twoFactorSecretRepository.save(twoFactorSecret);

    // Update user
    const user = await userService.findById(userId);
    user.twoFactorEnabled = true;
    await userService.update(userId, { twoFactorEnabled: true }, userId);

    return true;
  }

  async verifyToken(userId: string, token: string): Promise<boolean> {
    const twoFactorSecret = await this.twoFactorSecretRepository.findOne({
      where: { userId, verified: true },
    });

    if (!twoFactorSecret) {
      return false;
    }

    // Check if it's a backup code
    if (token.length === 8 && /^[A-Z0-9]+$/.test(token)) {
      const isValid = twoFactorSecret.useBackupCode(token);
      if (isValid) {
        twoFactorSecret.lastUsedAt = new Date();
        await this.twoFactorSecretRepository.save(twoFactorSecret);
        return true;
      }
    }

    // Verify TOTP token
    const isValid = authenticator.verify({
      token,
      secret: twoFactorSecret.secret,
    });

    if (isValid) {
      twoFactorSecret.lastUsedAt = new Date();
      await this.twoFactorSecretRepository.save(twoFactorSecret);
    }

    return isValid;
  }

  async disable(userId: string): Promise<void> {
    const twoFactorSecret = await this.twoFactorSecretRepository.findOne({
      where: { userId },
    });

    if (twoFactorSecret) {
      await this.twoFactorSecretRepository.remove(twoFactorSecret);
    }

    // Update user
    await userService.disable2FA(userId, userId);
  }

  async regenerateBackupCodes(userId: string): Promise<string[]> {
    const twoFactorSecret = await this.twoFactorSecretRepository.findOne({
      where: { userId, verified: true },
    });

    if (!twoFactorSecret) {
      throw new NotFoundException('Two-factor authentication is not enabled');
    }

    const newBackupCodes = generateBackupCodes();
    twoFactorSecret.backupCodes = newBackupCodes;
    twoFactorSecret.usedBackupCodes = [];
    await this.twoFactorSecretRepository.save(twoFactorSecret);

    return newBackupCodes;
  }

  async isEnabled(userId: string): Promise<boolean> {
    const twoFactorSecret = await this.twoFactorSecretRepository.findOne({
      where: { userId, verified: true },
    });
    return !!twoFactorSecret;
  }
}

export const twoFactorService = new TwoFactorService();