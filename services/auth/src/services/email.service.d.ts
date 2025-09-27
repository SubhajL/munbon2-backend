import { User } from '../models/user.entity';
declare class EmailService {
    private transporter;
    constructor();
    sendVerificationEmail(user: User): Promise<void>;
    sendPasswordResetEmail(user: User, token: string): Promise<void>;
    sendPasswordResetConfirmation(user: User): Promise<void>;
    send2FAEnabledEmail(user: User): Promise<void>;
    sendLoginAlertEmail(user: User, ip: string, location?: string): Promise<void>;
}
export declare const emailService: EmailService;
export {};
//# sourceMappingURL=email.service.d.ts.map