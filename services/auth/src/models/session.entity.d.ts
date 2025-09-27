import { User } from './user.entity';
export declare class Session {
    id: string;
    sessionId: string;
    userId: string;
    user: User;
    data: Record<string, any>;
    ip?: string;
    userAgent?: string;
    isActive: boolean;
    expiresAt: Date;
    lastAccessedAt?: Date;
    createdAt: Date;
    updatedAt: Date;
    isExpired(): boolean;
    isValid(): boolean;
}
//# sourceMappingURL=session.entity.d.ts.map