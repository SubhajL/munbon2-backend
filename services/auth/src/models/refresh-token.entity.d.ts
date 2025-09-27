import { User } from './user.entity';
export declare class RefreshToken {
    id: string;
    token: string;
    userId: string;
    user: User;
    deviceId?: string;
    deviceName?: string;
    userAgent?: string;
    ip?: string;
    isActive: boolean;
    expiresAt: Date;
    revokedAt?: Date;
    revokedBy?: string;
    revokeReason?: string;
    createdAt: Date;
    isExpired(): boolean;
    isValid(): boolean;
    revoke(userId: string, reason?: string): void;
}
//# sourceMappingURL=refresh-token.entity.d.ts.map