"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.emailService = void 0;
const nodemailer_1 = __importDefault(require("nodemailer"));
const config_1 = require("../config");
const logger_1 = require("../utils/logger");
class EmailService {
    transporter;
    constructor() {
        this.transporter = nodemailer_1.default.createTransport({
            host: config_1.config.email.host,
            port: config_1.config.email.port,
            secure: config_1.config.email.secure,
            auth: {
                user: config_1.config.email.user,
                pass: config_1.config.email.pass,
            },
        });
    }
    async sendVerificationEmail(user) {
        const verificationUrl = `${config_1.config.oauth.callbackUrl}/verify-email/${user.id}`;
        const mailOptions = {
            from: config_1.config.email.from,
            to: user.email,
            subject: 'Verify Your Email - Munbon Irrigation System',
            html: `
        <h1>Welcome to Munbon Irrigation System</h1>
        <p>Hi ${user.firstName},</p>
        <p>Please verify your email address by clicking the link below:</p>
        <a href="${verificationUrl}" style="padding: 10px 20px; background-color: #007bff; color: white; text-decoration: none; border-radius: 5px;">Verify Email</a>
        <p>Or copy and paste this link: ${verificationUrl}</p>
        <p>This link will expire in 24 hours.</p>
        <p>Best regards,<br>Munbon Team</p>
      `,
        };
        try {
            await this.transporter.sendMail(mailOptions);
            logger_1.logger.info(`Verification email sent to ${user.email}`);
        }
        catch (error) {
            logger_1.logger.error('Failed to send verification email:', error);
            throw new Error('Failed to send verification email');
        }
    }
    async sendPasswordResetEmail(user, token) {
        const resetUrl = `${config_1.config.oauth.callbackUrl}/reset-password?token=${token}`;
        const mailOptions = {
            from: config_1.config.email.from,
            to: user.email,
            subject: 'Password Reset - Munbon Irrigation System',
            html: `
        <h1>Password Reset Request</h1>
        <p>Hi ${user.firstName},</p>
        <p>You requested to reset your password. Click the link below to proceed:</p>
        <a href="${resetUrl}" style="padding: 10px 20px; background-color: #dc3545; color: white; text-decoration: none; border-radius: 5px;">Reset Password</a>
        <p>Or copy and paste this link: ${resetUrl}</p>
        <p>This link will expire in 1 hour.</p>
        <p>If you didn't request this, please ignore this email.</p>
        <p>Best regards,<br>Munbon Team</p>
      `,
        };
        try {
            await this.transporter.sendMail(mailOptions);
            logger_1.logger.info(`Password reset email sent to ${user.email}`);
        }
        catch (error) {
            logger_1.logger.error('Failed to send password reset email:', error);
            throw new Error('Failed to send password reset email');
        }
    }
    async sendPasswordResetConfirmation(user) {
        const mailOptions = {
            from: config_1.config.email.from,
            to: user.email,
            subject: 'Password Reset Successful - Munbon Irrigation System',
            html: `
        <h1>Password Reset Successful</h1>
        <p>Hi ${user.firstName},</p>
        <p>Your password has been successfully reset.</p>
        <p>If you didn't make this change, please contact support immediately.</p>
        <p>Best regards,<br>Munbon Team</p>
      `,
        };
        try {
            await this.transporter.sendMail(mailOptions);
            logger_1.logger.info(`Password reset confirmation sent to ${user.email}`);
        }
        catch (error) {
            logger_1.logger.error('Failed to send password reset confirmation:', error);
        }
    }
    async send2FAEnabledEmail(user) {
        const mailOptions = {
            from: config_1.config.email.from,
            to: user.email,
            subject: 'Two-Factor Authentication Enabled - Munbon Irrigation System',
            html: `
        <h1>Two-Factor Authentication Enabled</h1>
        <p>Hi ${user.firstName},</p>
        <p>Two-factor authentication has been successfully enabled on your account.</p>
        <p>You'll now need to enter a verification code from your authenticator app when logging in.</p>
        <p>If you didn't make this change, please contact support immediately.</p>
        <p>Best regards,<br>Munbon Team</p>
      `,
        };
        try {
            await this.transporter.sendMail(mailOptions);
            logger_1.logger.info(`2FA enabled notification sent to ${user.email}`);
        }
        catch (error) {
            logger_1.logger.error('Failed to send 2FA enabled email:', error);
        }
    }
    async sendLoginAlertEmail(user, ip, location) {
        const mailOptions = {
            from: config_1.config.email.from,
            to: user.email,
            subject: 'New Login Alert - Munbon Irrigation System',
            html: `
        <h1>New Login Detected</h1>
        <p>Hi ${user.firstName},</p>
        <p>A new login to your account was detected:</p>
        <ul>
          <li>Time: ${new Date().toLocaleString()}</li>
          <li>IP Address: ${ip}</li>
          ${location ? `<li>Location: ${location}</li>` : ''}
        </ul>
        <p>If this wasn't you, please change your password immediately.</p>
        <p>Best regards,<br>Munbon Team</p>
      `,
        };
        try {
            await this.transporter.sendMail(mailOptions);
            logger_1.logger.info(`Login alert sent to ${user.email}`);
        }
        catch (error) {
            logger_1.logger.error('Failed to send login alert email:', error);
        }
    }
}
exports.emailService = new EmailService();
//# sourceMappingURL=email.service.js.map