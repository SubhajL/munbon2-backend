import { User } from './user.entity';
export declare class PasswordReset {
    id: string;
    email: string;
    userId: string;
    user: User;
    token: string;
    expiresAt: Date;
    used: boolean;
    usedAt?: Date;
    ip?: string;
    userAgent?: string;
    createdAt: Date;
    isExpired(): boolean;
    isValid(): boolean;
    markAsUsed(): void;
}
//# sourceMappingURL=password-reset.entity.d.ts.map