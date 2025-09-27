import { User } from './user.entity';
export declare enum LoginAttemptStatus {
    SUCCESS = "success",
    FAILED = "failed",
    BLOCKED = "blocked"
}
export declare class LoginAttempt {
    id: string;
    email: string;
    userId?: string;
    user?: User;
    status: LoginAttemptStatus;
    ip: string;
    userAgent?: string;
    reason?: string;
    countryCode?: string;
    city?: string;
    metadata?: Record<string, any>;
    createdAt: Date;
}
//# sourceMappingURL=login-attempt.entity.d.ts.map