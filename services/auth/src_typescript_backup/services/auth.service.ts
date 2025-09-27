import { Repository } from 'typeorm';
import jwt from 'jsonwebtoken';
import { v4 as uuidv4 } from 'uuid';
import axios from 'axios';
import { AppDataSource } from '../config/database';
import { config } from '../config';
import { User, UserStatus } from '../models/user.entity';
import { RefreshToken } from '../models/refresh-token.entity';
import { LoginAttempt, LoginAttemptStatus } from '../models/login-attempt.entity';
import { PasswordReset } from '../models/password-reset.entity';
import { AuditLog, AuditAction } from '../models/audit-log.entity';
import { userService } from './user.service';
import { emailService } from './email.service';
import { auditService } from './audit.service';
import { logger } from '../utils/logger';
import { 
  UnauthorizedException, 
  BadRequestException, 
  ConflictException,
  ForbiddenException 
} from '../utils/exceptions';
import { generateRandomString } from '../utils/crypto';

interface TokenPayload {
  sub: string;
  email: string;
  roles: string[];
  type: 'access' | 'refresh';
  iat?: number;
  exp?: number;
  iss?: string;
  aud?: string;
}

interface LoginResult {
  user: User;
  accessToken: string;
  refreshToken: string;
  expiresIn: number;
  tokenType: string;
}

interface RegisterData {
  email: string;
  password: string;
  firstName: string;
  lastName: string;
  citizenId?: string;
  phoneNumber?: string;
  userType?: string;
  organizationId?: string;
  zoneId?: string;
}

class AuthService {
  private userRepository: Repository<User>;
  private refreshTokenRepository: Repository<RefreshToken>;
  private loginAttemptRepository: Repository<LoginAttempt>;
  private passwordResetRepository: Repository<PasswordReset>;

  constructor() {
    this.userRepository = AppDataSource.getRepository(User);
    this.refreshTokenRepository = AppDataSource.getRepository(RefreshToken);
    this.loginAttemptRepository = AppDataSource.getRepository(LoginAttempt);
    this.passwordResetRepository = AppDataSource.getRepository(PasswordReset);
  }

  async register(data: RegisterData): Promise<User> {
    // Check if user already exists
    const existingUser = await this.userRepository.findOne({
      where: [
        { email: data.email },
        { citizenId: data.citizenId },
        { phoneNumber: data.phoneNumber },
      ].filter(condition => Object.values(condition)[0]),
    });

    if (existingUser) {
      throw new ConflictException('User already exists');
    }

    // Create new user
    const user = this.userRepository.create({
      ...data,
      status: UserStatus.ACTIVE,
      emailVerified: false,
    });

    // Assign default role based on user type
    const defaultRole = await userService.getDefaultRoleForUserType(user.userType);
    if (defaultRole) {
      user.roles = [defaultRole];
    }

    await this.userRepository.save(user);

    // Send verification email
    await emailService.sendVerificationEmail(user);

    // Audit log
    await auditService.log({
      userId: user.id,
      action: AuditAction.USER_CREATE,
      resource: `user:${user.id}`,
      description: 'User registered',
      success: true,
    });

    return user;
  }

  async login(
    email: string, 
    password: string, 
    ip: string, 
    userAgent?: string
  ): Promise<LoginResult> {
    // Record login attempt
    const loginAttempt = this.loginAttemptRepository.create({
      email,
      ip,
      userAgent,
    });

    try {
      // Validate user credentials
      const user = await this.validateUser(email, password);
      
      if (!user) {
        loginAttempt.status = LoginAttemptStatus.FAILED;
        loginAttempt.reason = 'Invalid credentials';
        await this.loginAttemptRepository.save(loginAttempt);
        
        throw new UnauthorizedException('Invalid credentials');
      }

      // Check if user is locked
      if (user.isLocked()) {
        loginAttempt.status = LoginAttemptStatus.BLOCKED;
        loginAttempt.reason = 'Account locked';
        loginAttempt.userId = user.id;
        await this.loginAttemptRepository.save(loginAttempt);
        
        throw new ForbiddenException('Account is locked');
      }

      // Generate tokens
      const { accessToken, refreshToken, expiresIn } = await this.generateTokens(user);

      // Save refresh token
      const refreshTokenEntity = this.refreshTokenRepository.create({
        token: refreshToken,
        userId: user.id,
        deviceName: userAgent,
        userAgent,
        ip,
        expiresAt: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000), // 7 days
      });
      await this.refreshTokenRepository.save(refreshTokenEntity);

      // Update user login info
      user.lastLoginAt = new Date();
      user.lastLoginIp = ip;
      user.failedLoginAttempts = 0;
      user.lockedUntil = null;
      await this.userRepository.save(user);

      // Record successful login
      loginAttempt.status = LoginAttemptStatus.SUCCESS;
      loginAttempt.userId = user.id;
      await this.loginAttemptRepository.save(loginAttempt);

      // Audit log
      await auditService.log({
        userId: user.id,
        action: AuditAction.LOGIN,
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
    } catch (error) {
      // Update failed login attempts
      const user = await this.userRepository.findOne({ where: { email } });
      if (user) {
        user.failedLoginAttempts += 1;
        
        // Lock account if too many failed attempts
        if (user.failedLoginAttempts >= config.security.maxLoginAttempts) {
          user.lockedUntil = new Date(
            Date.now() + config.security.lockoutDuration * 60 * 1000
          );
          user.status = UserStatus.LOCKED;
        }
        
        await this.userRepository.save(user);
      }

      throw error;
    }
  }

  async validateUser(email: string, password: string): Promise<User | null> {
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

  async refreshAccessToken(refreshToken: string): Promise<LoginResult> {
    // Verify refresh token
    const payload = jwt.verify(refreshToken, config.jwt.secret) as TokenPayload;
    
    if (payload.type !== 'refresh') {
      throw new UnauthorizedException('Invalid token type');
    }

    // Check if refresh token exists and is valid
    const tokenEntity = await this.refreshTokenRepository.findOne({
      where: { token: refreshToken },
      relations: ['user', 'user.roles', 'user.roles.permissions'],
    });

    if (!tokenEntity || !tokenEntity.isValid()) {
      throw new UnauthorizedException('Invalid refresh token');
    }

    const user = tokenEntity.user;

    // Generate new tokens
    const { accessToken, refreshToken: newRefreshToken, expiresIn } = 
      await this.generateTokens(user);

    // Revoke old refresh token
    tokenEntity.revoke(user.id, 'Token refresh');
    await this.refreshTokenRepository.save(tokenEntity);

    // Save new refresh token
    const newTokenEntity = this.refreshTokenRepository.create({
      token: newRefreshToken,
      userId: user.id,
      deviceName: tokenEntity.deviceName,
      userAgent: tokenEntity.userAgent,
      ip: tokenEntity.ip,
      expiresAt: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000),
    });
    await this.refreshTokenRepository.save(newTokenEntity);

    // Audit log
    await auditService.log({
      userId: user.id,
      action: AuditAction.TOKEN_REFRESH,
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

  async logout(userId: string, refreshToken?: string): Promise<void> {
    if (refreshToken) {
      // Revoke specific refresh token
      const token = await this.refreshTokenRepository.findOne({
        where: { token: refreshToken, userId },
      });
      
      if (token) {
        token.revoke(userId, 'User logout');
        await this.refreshTokenRepository.save(token);
      }
    } else {
      // Revoke all user's refresh tokens
      await this.refreshTokenRepository.update(
        { userId, isActive: true },
        { isActive: false, revokedAt: new Date(), revokedBy: userId }
      );
    }

    // Audit log
    await auditService.log({
      userId,
      action: AuditAction.LOGOUT,
      resource: `user:${userId}`,
      description: 'User logged out',
      success: true,
    });
  }

  async requestPasswordReset(email: string, ip: string): Promise<void> {
    const user = await this.userRepository.findOne({ where: { email } });
    
    if (!user) {
      // Don't reveal if user exists
      logger.info(`Password reset requested for non-existent email: ${email}`);
      return;
    }

    // Generate reset token
    const token = generateRandomString(32);
    const expiresAt = new Date(Date.now() + 60 * 60 * 1000); // 1 hour

    // Save reset token
    const passwordReset = this.passwordResetRepository.create({
      email,
      userId: user.id,
      token,
      expiresAt,
      ip,
    });
    await this.passwordResetRepository.save(passwordReset);

    // Send reset email
    await emailService.sendPasswordResetEmail(user, token);

    // Audit log
    await auditService.log({
      userId: user.id,
      action: AuditAction.PASSWORD_RESET_REQUEST,
      resource: `user:${user.id}`,
      description: 'Password reset requested',
      ip,
      success: true,
    });
  }

  async resetPassword(token: string, newPassword: string, ip: string): Promise<void> {
    const resetToken = await this.passwordResetRepository.findOne({
      where: { token },
      relations: ['user'],
    });

    if (!resetToken || !resetToken.isValid()) {
      throw new BadRequestException('Invalid or expired reset token');
    }

    const user = resetToken.user;

    // Update password
    user.password = newPassword;
    user.failedLoginAttempts = 0;
    user.lockedUntil = null;
    user.status = UserStatus.ACTIVE;
    await this.userRepository.save(user);

    // Mark token as used
    resetToken.markAsUsed();
    resetToken.ip = ip;
    await this.passwordResetRepository.save(resetToken);

    // Revoke all refresh tokens
    await this.refreshTokenRepository.update(
      { userId: user.id, isActive: true },
      { isActive: false, revokedAt: new Date(), revokeReason: 'Password reset' }
    );

    // Send confirmation email
    await emailService.sendPasswordResetConfirmation(user);

    // Audit log
    await auditService.log({
      userId: user.id,
      action: AuditAction.PASSWORD_RESET_COMPLETE,
      resource: `user:${user.id}`,
      description: 'Password reset completed',
      ip,
      success: true,
    });
  }

  async getThaiDigitalIdUserInfo(accessToken: string): Promise<any> {
    try {
      const response = await axios.get(config.thaiDigitalId.userinfoUrl, {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      });

      return response.data;
    } catch (error) {
      logger.error('Failed to get Thai Digital ID user info:', error);
      throw new Error('Failed to get user information from Thai Digital ID');
    }
  }

  async findOrCreateFromThaiDigitalId(userInfo: any): Promise<User> {
    // Try to find existing user
    let user = await this.userRepository.findOne({
      where: [
        { thaiDigitalId: userInfo.sub },
        { citizenId: userInfo.citizen_id },
        { email: userInfo.email },
      ].filter(condition => Object.values(condition)[0]),
      relations: ['roles', 'roles.permissions'],
    });

    if (user) {
      // Update Thai Digital ID if not set
      if (!user.thaiDigitalId) {
        user.thaiDigitalId = userInfo.sub;
        user.emailVerified = true;
        user.emailVerifiedAt = new Date();
        await this.userRepository.save(user);
      }
    } else {
      // Create new user from Thai Digital ID
      user = await this.register({
        email: userInfo.email,
        password: generateRandomString(16), // Random password
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

  private async generateTokens(user: User): Promise<{
    accessToken: string;
    refreshToken: string;
    expiresIn: number;
  }> {
    const roles = user.roles.map(role => role.name);
    
    // Access token payload
    const accessTokenPayload: TokenPayload = {
      sub: user.id,
      email: user.email,
      roles,
      type: 'access',
    };

    // Refresh token payload
    const refreshTokenPayload: TokenPayload = {
      sub: user.id,
      email: user.email,
      roles,
      type: 'refresh',
    };

    // Generate tokens
    const accessToken = jwt.sign(
      accessTokenPayload,
      config.jwt.secret,
      {
        expiresIn: config.jwt.accessTokenExpiresIn,
        issuer: config.jwt.issuer,
        audience: config.jwt.audience,
      }
    );

    const refreshToken = jwt.sign(
      refreshTokenPayload,
      config.jwt.secret,
      {
        expiresIn: config.jwt.refreshTokenExpiresIn,
        issuer: config.jwt.issuer,
        audience: config.jwt.audience,
      }
    );

    // Calculate expiration time in seconds
    const expiresIn = 15 * 60; // 15 minutes

    return { accessToken, refreshToken, expiresIn };
  }
}

export const authService = new AuthService();